"""Exact Dicke-state preparation on calibrated Willow qubits.

Derivation (Bärtschi & Eidenbenz, arXiv:1904.07358, Section 2):
Partition weight-r bitstrings on m qubits by the last bit. Their counts are
C(m-1,r-1) and C(m-1,r), so dividing by C(m,r) gives probabilities r/m and
(m-r)/m. Therefore D(m,r) = sqrt(r/m) D(m-1,r-1)|1> +
sqrt((m-r)/m) D(m-1,r)|0>. A Givens rotation with theta=acos(sqrt(r/m))
retains cos(theta)=sqrt(r/m) and shifts sin(theta)=sqrt((m-r)/m).
The r=0 and r=m limits are unchanged product states; m=2,r=1 is the
positive Bell state. Range bounds in line_gates preserve the reachable
sorted-prefix invariant and avoid unnecessary flagged gates.

For a flagged gate, alpha=(theta+pi/2)/2 and beta=(theta-pi/2)/2.
With control zero, G(beta)G(alpha)=G(theta). With control one, CZ(c,a)
acts as Z(a); the extra Z(c) cancels its sign on the reachable |101>
shift and |111> input. This identity is restricted to the reachable
subspace {000,001,011,101,111}; it is not a general controlled rotation.

For a W tree, a parent holding sqrt(R/N) sends sin(theta)=sqrt(S/R) to
a child subtree of S nodes: its child receives sqrt(S/N), leaving
sqrt((R-S)/N). After all children, the parent keeps 1/sqrt(N); recursion
makes every amplitude equal. A leaf keeps its share; a chain transfers
the decreasing remainder. Finally, X on all qubits bijects weights k
and N-k. Compilation may change only the common global phase.

Known first split (adapted from ryon/dicke_solution.py, upstream d8f148d):
Before the first split the child/left bit a is 0 and parent/right bit b is 1.
Ry_a(2theta)|01> = cos(theta)|01> + sin(theta)|11>.
CNOT(a,b) then gives cos(theta)|01> + sin(theta)|10>.
Since CNOT(a,b)=H_b CZ(a,b) H_b, this needs one CZ instead of a full Givens.
At theta=0 it retains |01>; at theta=pi/2 it transfers to |10>;
at pi/4 it makes the positive Bell state. Only this known-input split is replaced.

Sparse echo uses two X pulses in a qubit's uninterrupted idle window. Every
intervening operation is on other qubits and commutes with X, so the product is
X^2=I for arbitrary input, including entangled states. Short windows are unchanged;
a qualifying window has exactly two pulses. This is an optional noise-model choice.

Optimized synthesis, derived from the user-provided test_sol.py:
Let R(t)=[[cos(t/2),-sin(t/2)],[sin(t/2),cos(t/2)]]. The chronological
sequence R_a(-alpha),R_c(-pi/2),CZ_ab,R_a(alpha),R_b(pi/2),CZ_bc,
R_b(pi/2+beta),R_c(beta),CZ_ab,R_b(-pi/2),CZ_bc,R_b(-pi/2),R_c(pi/2)
has columns U|000>=|000>, U|001>=cos(beta)|001>+sin(beta)|010>,
U|011>=cos(alpha)|011>+sin(alpha)|110>, with one positive phase.
Thus the first Givens and adjacent mux in a sorted-prefix stage can be merged:
alpha=acos(sqrt(r/m)), beta=acos(sqrt((r-1)/m)). Four CZ replace seven.
At alpha=beta=0 both inputs stay; at pi/2 both shift; at pi/4 both split
equally with positive amplitudes. Only m>k stages admit this replacement:
their first three bits are 000,001,011; m<=k may also contain 111.
The remaining pruned gates and one-CZ known first split are retained.
For D(4,2), a separately certified five-CZ square ansatz is available if its
calibration-cost estimate beats the path. Its angles have closed forms;
there are no fits, lookup tables or downloaded-file dependencies. Derivation and
numerical certificate: docs/OPTIMIZED_SYNTHESIS_PLAN.md and associated tests.

Only Python's standard library, Cirq/cirq-google and their NumPy/NetworkX dependencies
are imported. Importing this module performs no simulation or file I/O.
Public circuit functions raise NotImplementedError for unsupported requests.
Calibration values are probabilities with nonnegative uncertainties.
"""

from __future__ import annotations

import functools
import math
import numbers
import time
from dataclasses import dataclass, replace

import cirq
import cirq_google
import networkx as nx
import numpy as np

ErrorRate = tuple[float, float]
QubitErrorMap = dict[cirq.GridQubit, ErrorRate]
PairErrorMap = dict[tuple[cirq.GridQubit, cirq.GridQubit], ErrorRate]
ErrorMap = QubitErrorMap | PairErrorMap
Tree = dict[cirq.GridQubit, list[cirq.GridQubit]]
MAX_MOMENTS = 1750
MAX_CONSTRUCTION_SECONDS = 59.0
BONUS_SEARCH_SECONDS = 10.0
SPARSE_MIN_IDLE_SLOTS = 4
MAX_ROUTING_QUBITS = 15


@dataclass(frozen=True)
class PrepConfig:
    """Tunable constants for layout search and scheduling."""

    beam_width: int = 3000  # paths kept per step in the line search
    search_time_s: float = 20.0  # wall-clock budget for layout search
    idle_error_per_layer: float = 1.5e-3  # est. dephasing per qubit per CZ layer
    default_error: float = 1e-2  # used when a qubit/pair is missing from a map
    use_dynamical_decoupling: bool = True
    dd_strategy: str = "dense"
    sparse_min_idle_slots: int = SPARSE_MIN_IDLE_SLOTS
    max_routing_qubits: int = (
        MAX_ROUTING_QUBITS  # zero disables the bounded connected-patch fallback
    )
    max_moments: int = MAX_MOMENTS
    construction: str = "optimized"

    def __post_init__(self) -> None:
        if self.construction not in {"optimized", "analytic"}:
            raise ValueError("construction must be optimized or analytic")
        if (
            isinstance(self.max_routing_qubits, bool)
            or not isinstance(self.max_routing_qubits, int)
            or self.max_routing_qubits < 0
        ):
            raise ValueError("max_routing_qubits must be a nonnegative integer")
        if self.dd_strategy not in {"dense", "sparse"}:
            raise ValueError("dd_strategy must be dense or sparse")
        if (
            isinstance(self.sparse_min_idle_slots, bool)
            or not isinstance(self.sparse_min_idle_slots, int)
            or self.sparse_min_idle_slots < 2
        ):
            raise ValueError("sparse_min_idle_slots must be an integer >=2")
        if self.beam_width < 1 or self.search_time_s <= 0 or self.max_moments < 1:
            raise ValueError("beam width, search budget, and moment cap must be positive")
        if not all(
            math.isfinite(x) and x >= 0
            for x in (self.search_time_s, self.idle_error_per_layer, self.default_error)
        ):
            raise ValueError("search and error costs must be finite and nonnegative")


CONFIG = PrepConfig()
CZ_PER_GIVENS = 2
CZ_PER_MUX_TARGET_PAIR = 4  # two Givens on (p, p+1)
CZ_PER_MUX_CONTROL_PAIR = 1  # the CZ(c, p)


# %%
@dataclass(frozen=True)
class LineGate:
    """A logical gate on line positions: kind in {'givens', 'mux'}."""

    kind: str
    p: int  # acts on pair (p, p+1); mux also uses control p-1
    theta: float


def line_gates(n_qubits: int, k: int) -> list[LineGate]:
    """Logical nearest-neighbour gates mapping |0^{N-k} 1^k> to |D^N_k> (0-indexed).

    Parameters
    ----------
    n_qubits : int
        Line length N.
    k : int
        Excitation number, 0 <= k <= N.

    Returns
    -------
    list[LineGate]
        Gates in application order.

    Raises
    ------
    ValueError
        For nonintegral or out-of-range counts. The angles follow the
        split/shift recursion in Bärtschi & Eidenbenz (2019), Section 2.
    """
    return [gate for _, gates in _line_stages(n_qubits, k) for gate in gates]


def _line_stages(n_qubits: int, k: int) -> list[tuple[int, list[LineGate]]]:
    """Retain the recursion boundary needed to guard state-specific replacements."""
    if (
        not isinstance(n_qubits, numbers.Integral)
        or not isinstance(k, numbers.Integral)
        or isinstance(n_qubits, (bool, np.bool_))
        or isinstance(k, (bool, np.bool_))
        or n_qubits < 1
        or not 0 <= k <= n_qubits
    ):
        raise ValueError(f"invalid line counts ({n_qubits}, {k})")
    stages: list[tuple[int, list[LineGate]]] = []
    for m in range(n_qubits, 1, -1):  # region = positions 0..m-1
        gates: list[LineGate] = []
        r_min = max(0, k - (n_qubits - m))
        r_max = min(k, m)
        # hole (rightmost 0) sits at index m-1-r; needs 1 <= r <= m-1
        first = {m - 1 - r: r for r in range(max(1, r_min), min(r_max, m - 1) + 1)}
        if not first:
            continue
        h_min = min(first)
        for p in range(h_min, m - 1):
            can_first = p in first
            can_move = p > h_min
            if can_first:
                theta = math.acos(math.sqrt(first[p] / m))
                gates.append(LineGate("mux" if can_move else "givens", p, theta))
            else:
                gates.append(LineGate("givens", p, math.pi / 2))
        stages.append((m, gates))
    return stages


def _line_chunks(n_qubits: int, k: int, construction: str) -> list[tuple[LineGate, ...]]:
    """Plan native chunks; pairs merge only the three proven local input columns."""
    if construction not in {"optimized", "analytic"}:
        raise ValueError("construction must be optimized or analytic")
    chunks: list[tuple[LineGate, ...]] = []
    for m, gates in _line_stages(n_qubits, k):
        if (
            construction == "optimized"
            and m > k
            and len(gates) >= 2
            and gates[0].kind == "givens"
            and gates[1].kind == "mux"
            and gates[1].p == gates[0].p + 1
        ):
            chunks.append(tuple(gates[:2]))
            gates = gates[2:]
        chunks.extend((gate,) for gate in gates)
    return chunks


def line_edge_cz_counts(n_qubits: int, k: int, *, construction: str = "optimized") -> list[int]:
    """Count emitted CZs per line edge for the selected construction.

    Counts include four-CZ pair merges and the known first split discount, and
    exactly match build_line_ops. Invalid sizes/policies raise ValueError.
    """
    counts = [0] * max(n_qubits - 1, 0)
    for index, chunk in enumerate(_line_chunks(n_qubits, k, construction)):
        g = chunk[0]
        if len(chunk) == 2:
            counts[g.p] += 2
            counts[g.p + 1] += 2
            continue
        if g.kind == "givens":
            counts[g.p] += 1 if index == 0 else CZ_PER_GIVENS
        else:
            counts[g.p] += CZ_PER_MUX_TARGET_PAIR
            counts[g.p - 1] += CZ_PER_MUX_CONTROL_PAIR
    return counts


# %%
class Hardware:
    """Working-qubit graph with per-qubit and per-coupler error costs."""

    def __init__(
        self,
        cz_pauli_error_rate: ErrorMap,
        sq_pauli_error_rate: ErrorMap,
        zero_errors: ErrorMap,
        one_errors: ErrorMap,
        config: PrepConfig = CONFIG,
    ) -> None:
        for mapping in (cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors):
            for key, value in mapping.items():
                if (
                    len(value) != 2
                    or not all(isinstance(x, numbers.Real) for x in value)
                    or not all(math.isfinite(x) for x in value)
                    or not 0 <= value[0] <= 1
                    or value[1] < 0
                ):
                    raise ValueError(
                        f"invalid calibration at {key}: {value}; expected probability and uncertainty"
                    )
        self.config = config
        self.qubits = set(sq_pauli_error_rate)
        self.adj: dict[cirq.GridQubit, set[cirq.GridQubit]] = {
            q: set() for q in sorted(self.qubits)
        }
        self.cz: dict[frozenset, float] = {}
        for pair, (err, _) in cz_pauli_error_rate.items():
            a, b = tuple(pair)
            if a in self.qubits and b in self.qubits:
                self.adj[a].add(b)
                self.adj[b].add(a)
                self.cz[frozenset((a, b))] = float(err)
        d = config.default_error
        self.node: dict[cirq.GridQubit, float] = {}
        for q in sorted(self.qubits):
            ro = 0.5 * (zero_errors.get(q, (d, 0))[0] + one_errors.get(q, (d, 0))[0])
            self.node[q] = ro + 2.0 * sq_pauli_error_rate[q][0]

    def edge(self, a: cirq.GridQubit, b: cirq.GridQubit) -> float:
        return self.cz[frozenset((a, b))]


def find_line(hw: Hardware, edge_weights: list[int], deadline: float) -> list[cirq.GridQubit]:
    """Beam search for a simple path minimising sum(w_i * e_cz(i)) + sum(node cost).

    Raises
    ------
    NotImplementedError
        If no simple path of the requested length exists in the working graph.
    """
    n = len(edge_weights) + 1
    beam: list[tuple[float, tuple[cirq.GridQubit, ...]]] = sorted(
        ((hw.node[q], (q,)) for q in sorted(hw.qubits)), key=lambda t: t[0]
    )
    beam = beam[: hw.config.beam_width]
    for i in range(n - 1):
        w = edge_weights[i]
        cand: list[tuple[float, tuple[cirq.GridQubit, ...]]] = []
        for cost, path in beam:
            tail = path[-1]
            for nb in sorted(hw.adj[tail]):
                if nb not in path:
                    cand.append((cost + w * hw.edge(tail, nb) + hw.node[nb], path + (nb,)))
        if not cand:
            raise NotImplementedError(f"beam search found no path of {n} working qubits")
        cand.sort(key=lambda t: t[0])
        width = hw.config.beam_width if time.monotonic() < deadline else 50
        beam = cand[:width]
    return list(beam[0][1])


def find_tree(
    hw: Hardware, n: int, deadline: float
) -> tuple[cirq.GridQubit, dict[cirq.GridQubit, list[cirq.GridQubit]]]:
    """Choose a root and BFS spanning tree of n working qubits for the W state.

    Returns
    -------
    root, children
        children[v] lists v's children, ordered so deeper subtrees are served first.
    """
    best = None
    for root in sorted(hw.qubits, key=lambda q: (hw.node[q], q)):
        if time.monotonic() > deadline and best is not None:
            break
        parent = {root: None}
        layer = [root]
        while layer and len(parent) < n:
            nxt: dict[cirq.GridQubit, tuple[float, cirq.GridQubit]] = {}
            for v in layer:
                for nb in sorted(hw.adj[v]):
                    if nb in parent:
                        continue
                    c = hw.edge(v, nb)
                    if nb not in nxt or c < nxt[nb][0]:
                        nxt[nb] = (c, v)
            ranked = sorted(nxt, key=lambda q: (2 * nxt[q][0] + hw.node[q], q))
            layer = ranked[: n - len(parent)]
            for q in layer:
                parent[q] = nxt[q][1]
        if len(parent) < n:
            continue
        children: dict = {v: [] for v in parent}
        for v, p in parent.items():
            if p is not None:
                children[p].append(v)
        finish = _tree_finish_times(root, children)
        for v in children:
            children[v].sort(key=lambda c: (-finish[c], c))
        depth = finish[root]
        cost = (
            sum(CZ_PER_GIVENS * hw.edge(v, p) for v, p in parent.items() if p is not None)
            + sum(hw.node[v] for v in parent)
            + hw.config.idle_error_per_layer * CZ_PER_GIVENS * depth * n / 2
        )
        if best is None or cost < best[0]:
            best = (cost, root, children)
    if best is None:
        raise NotImplementedError(f"no connected set of {n} working qubits")
    return best[1], best[2]


def _tree_finish_times(root: cirq.GridQubit, children: Tree) -> dict:
    """Givens time-steps until each subtree is fully populated (children served
    one per step, longest first)."""
    finish: dict = {}

    def visit(v: cirq.GridQubit) -> None:
        kids = children[v]
        for c in kids:
            visit(c)
        ts = sorted((finish[c] for c in kids), reverse=True)
        finish[v] = max((i + 1 + t for i, t in enumerate(ts)), default=0)

    visit(root)
    return finish


# %%
_A, _B = cirq.LineQubit.range(2)


@functools.lru_cache(maxsize=4096)
def _givens_template(theta: float) -> tuple[cirq.Operation, ...]:
    """Exact 2-CZ decomposition of cirq.givens(theta) on placeholder qubits."""
    ops = cirq.two_qubit_matrix_to_cz_operations(
        _A, _B, cirq.unitary(cirq.givens(theta)), allow_partial_czs=False, atol=1e-12
    )
    n_cz = sum(1 for op in ops if len(op.qubits) == 2)
    if n_cz > CZ_PER_GIVENS:
        raise RuntimeError(f"givens({theta}) decomposed to {n_cz} CZs (expected <= 2)")
    return tuple(ops)


def givens_ops(a: cirq.Qid, b: cirq.Qid, theta: float) -> list[cirq.Operation]:
    """CZ + single-qubit ops implementing |01> -> cos|01> + sin|10> on (a, b)."""
    mapping = {_A: a, _B: b}
    return [op.transform_qubits(mapping) for op in _givens_template(theta)]


def mux_ops(c: cirq.Qid, a: cirq.Qid, b: cirq.Qid, theta: float) -> list[cirq.Operation]:
    """Five-CZ split/shift gate, exact on the reachable input subspace.

    On c,a,b in {000,001,011,101,111}, implements the split or positive
    full shift required by the Dicke recursion, up to one common global phase.
    It is not a general controlled Givens: input 100 acquires a minus sign.
    The angles satisfy alpha+beta=theta, alpha-beta=pi/2. See module derivation
    and Bärtschi & Eidenbenz (2019), Section 2, for the split/shift invariant."""
    alpha = 0.5 * (theta + math.pi / 2)
    beta = 0.5 * (theta - math.pi / 2)
    return [*givens_ops(a, b, alpha), cirq.CZ(c, a), *givens_ops(a, b, beta), cirq.Z(c)]


# %%
def schedule(
    ops: list[cirq.Operation],
    dynamical_decoupling: bool,
    dd_strategy: str = "dense",
    sparse_min_idle_slots: int = SPARSE_MIN_IDLE_SLOTS,
) -> cirq.Circuit:
    """Pack ops ALAP into alternating single-qubit / CZ moments and fill idles with DD.

    Single-qubit runs between CZs are fused into one PhasedXZGate placed directly
    before the next CZ on that qubit (or after the last CZ). Idle single-qubit slots
    between two operations of a qubit receive X/Y pulses whose net product is
    folded into the following gate, or cancelled inside the gap.
    """
    if (
        dd_strategy not in {"dense", "sparse"}
        or isinstance(sparse_min_idle_slots, bool)
        or not isinstance(sparse_min_idle_slots, int)
        or sparse_min_idle_slots < 2
    ):
        raise ValueError("invalid dynamical-decoupling strategy or minimum idle slots")
    # 1. per-qubit fusion of single-qubit runs into matrices
    pending: dict[cirq.Qid, np.ndarray] = {}
    seq: list = []  # ('1q', q, mat) | ('cz', a, b)
    for op in ops:
        if len(op.qubits) == 1:
            (q,) = op.qubits
            pending[q] = cirq.unitary(op) @ pending.get(q, np.eye(2))
        else:
            a, b = op.qubits
            for q in (a, b):
                if q in pending:
                    seq.append(("1q", q, pending.pop(q)))
            seq.append(("cz", a, b))
    for q, mat in pending.items():
        seq.append(("1q", q, mat))

    # 2. ALAP CZ layers
    rev_last: dict = {}
    rev = {}
    for i in range(len(seq) - 1, -1, -1):
        item = seq[i]
        if item[0] == "cz":
            r = 1 + max(rev_last.get(item[1], -1), rev_last.get(item[2], -1))
            rev[i] = r
            rev_last[item[1]] = rev_last[item[2]] = r
    n_layers = 1 + max(rev.values(), default=-1)
    layer = {i: n_layers - 1 - r for i, r in rev.items()}

    # 3. place single-qubit gates in slot = layer of next CZ, else after previous CZ
    next_cz: dict = {}
    oneq_slot = {}
    for i in range(len(seq) - 1, -1, -1):
        item = seq[i]
        if item[0] == "cz":
            next_cz[item[1]] = next_cz[item[2]] = layer[i]
        else:
            oneq_slot[i] = next_cz.get(item[1], None)
    prev_cz: dict = {}
    for i, item in enumerate(seq):
        if item[0] == "cz":
            prev_cz[item[1]] = prev_cz[item[2]] = layer[i]
        elif oneq_slot[i] is None:
            oneq_slot[i] = prev_cz.get(item[1], -1) + 1

    n_slots = n_layers + 1
    oneq: list[dict] = [dict() for _ in range(n_slots)]
    cz_layers: list[list] = [[] for _ in range(n_layers)]
    for i, item in enumerate(seq):
        if item[0] == "cz":
            cz_layers[layer[i]].append((item[1], item[2]))
        else:
            s, q = oneq_slot[i], item[1]
            oneq[s][q] = item[2] @ oneq[s].get(q, np.eye(2))

    if dynamical_decoupling:
        _add_dd(oneq, cz_layers, dd_strategy, sparse_min_idle_slots)

    moments = []
    for s in range(n_slots):
        mom = [
            cirq.PhasedXZGate.from_matrix(mat).on(q)
            for q, mat in oneq[s].items()
            if not cirq.equal_up_to_global_phase(mat, np.eye(2), atol=1e-10)
        ]
        if mom:
            moments.append(cirq.Moment(mom))
        if s < n_layers:
            moments.append(cirq.Moment(cirq.CZ(a, b) for a, b in cz_layers[s]))
    return cirq.Circuit(moments)


_X = np.array([[0, 1], [1, 0]], dtype=complex)
_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)


def _add_dd(
    oneq: list[dict],
    cz_layers: list[list],
    strategy: str = "dense",
    min_idle_slots: int = SPARSE_MIN_IDLE_SLOTS,
) -> None:
    """In-place XY-style dynamical decoupling on idle single-qubit slots.

    Slot s precedes CZ layer s. A qubit is busy in slot s if it has a 1q gate
    there, and busy in CZ layer s if it is in a CZ there. A gap is a run of idle
    slots between two busy events with no CZ inside it.
    """
    n_slots = len(oneq)
    qubits = {q for slot in oneq for q in slot} | {q for lay in cz_layers for p in lay for q in p}
    in_cz = [{q for p in lay for q in p} for lay in cz_layers]

    def fill(q: cirq.Qid, gap: list[int], fold_into: int | None) -> None:
        if strategy == "sparse":
            _fill_sparse_gap(oneq, q, gap, min_idle_slots)
        else:
            _fill_gap(oneq, q, gap, fold_into)

    for q in qubits:
        started = False
        gap: list[int] = []
        for s in range(n_slots):
            busy_1q = q in oneq[s]
            if busy_1q:
                if gap and started:
                    fill(q, gap, fold_into=s)
                gap = []
                started = True
            elif started:
                gap.append(s)
            if s < len(cz_layers) and q in in_cz[s]:
                if gap and started:
                    fill(q, gap, fold_into=None)
                gap = []
                started = True
        if gap and started:
            fill(q, gap, fold_into=None)


def _fill_sparse_gap(
    oneq: list[dict], q: cirq.Qid, gap: list[int], min_idle_slots: int = SPARSE_MIN_IDLE_SLOTS
) -> None:
    """Insert a canceling X pair near quarter/three-quarter points of idle 1q slots.

    Assumes the owning gap detector has verified no operation on q intervenes.
    Other-qubit operations commute, so the full unitary is unchanged. Windows
    shorter than min_idle_slots are left untouched. No CZ or virtual slot is added,
    but filling a previously empty slot can add an emitted moment. The final
    constructor reapplies the challenge's moment cap.
    """
    if len(gap) >= min_idle_slots:
        oneq[gap[len(gap) // 4]][q] = _X
        oneq[gap[3 * len(gap) // 4]][q] = _X


def _fill_gap(oneq: list[dict], q: cirq.Qid, gap: list[int], fold_into: int | None) -> None:
    """Put alternating X, Y pulses in `gap`; make the net effect the identity."""
    if fold_into is None and len(gap) < 2:
        return
    acc = np.eye(2, dtype=complex)
    slots = gap if fold_into is not None else gap[:-1]
    for i, s in enumerate(slots):
        pulse = _X if i % 2 == 0 else _Y
        oneq[s][q] = pulse
        acc = pulse @ acc
    if fold_into is not None:
        oneq[fold_into][q] = oneq[fold_into][q] @ acc.conj().T
    else:
        oneq[gap[-1]][q] = acc.conj().T


# %%
def _split_pair_ops(
    a: cirq.Qid, b: cirq.Qid, c: cirq.Qid, alpha: float, beta: float
) -> list[cirq.Operation]:
    """Merge Givens(alpha) and mux(beta) on sorted inputs 000,001,011.

    Four native CZs implement the positive columns derived in the module
    docstring. This identity is not a replacement on arbitrary three-qubit input.
    """
    return [
        cirq.ry(-alpha).on(a),
        cirq.ry(-math.pi / 2).on(c),
        cirq.CZ(a, b),
        cirq.ry(alpha).on(a),
        cirq.ry(math.pi / 2).on(b),
        cirq.CZ(b, c),
        cirq.ry(math.pi / 2 + beta).on(b),
        cirq.ry(beta).on(c),
        cirq.CZ(a, b),
        cirq.ry(-math.pi / 2).on(b),
        cirq.CZ(b, c),
        cirq.ry(-math.pi / 2).on(b),
        cirq.ry(math.pi / 2).on(c),
    ]


def build_line_ops(
    qubits: list[cirq.Qid], k: int, *, construction: str = "optimized"
) -> list[cirq.Operation]:
    """Prepare |D^N_k> on a path using optimized or original analytic synthesis.

    Inputs are an ordered path of N qubits and 0<=k<=N; returned native CZ and
    one-qubit operations are unscheduled. The optimized policy merges only
    reachable-state-equivalent pairs. Invalid sizes/policies raise ValueError.
    """
    n = len(qubits)
    ops: list[cirq.Operation] = [cirq.X(q) for q in qubits[n - k :]]
    for index, chunk in enumerate(_line_chunks(n, k, construction)):
        g = chunk[0]
        a, b = qubits[g.p], qubits[g.p + 1]
        if len(chunk) == 2:
            ops += _split_pair_ops(a, b, qubits[g.p + 2], g.theta, chunk[1].theta)
            continue
        if g.kind == "givens":
            ops += _first_split_ops(a, b, g.theta) if index == 0 else givens_ops(a, b, g.theta)
        else:
            ops += mux_ops(qubits[g.p - 1], a, b, g.theta)
    return ops


# User-provided test_sol.py, SHA256 5a9bc743c89a4f5af1e561c8162ba3af2aeb8d795a45d9dc00fd1fbb23c3f245.
# The reference's fitted square has a closed form. With a=atan2(2,1) and
# b=2asin(1/sqrt(6)), the first CZ and Rys prepare, on labels 2,3,
# (sqrt(5)|00>-sqrt(5)|01>-|10>-|11>)/sqrt(12). The remaining skeleton
# maps the product with Ry(a)|0>_0 Ry(-pi/2)|0>_1 to +|D(4,2)>.
# Complete exact intermediate amplitudes are in docs/OPTIMIZED_SYNTHESIS.md.
# Tests certify all square orientations and the complete state, including leakage.
_SQUARE_CZ_PAIRS = ((3, 2), (2, 0), (0, 1), (2, 0), (1, 3))
_SQUARE_ALPHA = math.atan2(2, 1)
_SQUARE_BETA = 2 * math.asin(1 / math.sqrt(6))
_SQUARE_ANGLES = (
    _SQUARE_ALPHA,
    -math.pi / 2,
    _SQUARE_BETA,
    math.pi / 2,
    -math.pi,
    0.0,
    -math.pi / 2,
    _SQUARE_ALPHA,
    math.pi / 2,
    math.pi,
    math.pi,
    -3 * math.pi / 2,
    math.pi / 2,
    -math.pi,
)


def _square_ops(qubits: list[cirq.Qid]) -> list[cirq.Operation]:
    """Five-CZ D(4,2) preparation on square labels 0,1 / 2,3 from |0000>."""
    ops = [cirq.ry(theta).on(q) for q, theta in zip(qubits, _SQUARE_ANGLES[:4])]
    for index, (a, b) in enumerate(_SQUARE_CZ_PAIRS):
        ops += [
            cirq.CZ(qubits[a], qubits[b]),
            cirq.ry(_SQUARE_ANGLES[4 + 2 * index]).on(qubits[a]),
            cirq.ry(_SQUARE_ANGLES[5 + 2 * index]).on(qubits[b]),
        ]
    return ops


def _find_square(hw: Hardware) -> tuple[list[cirq.GridQubit], float] | None:
    """Find the cheapest calibrated square and labeling; missing squares return None."""
    best = None
    for q in sorted(hw.qubits):
        cycle = [
            q,
            cirq.GridQubit(q.row, q.col + 1),
            cirq.GridQubit(q.row + 1, q.col + 1),
            cirq.GridQubit(q.row + 1, q.col),
        ]
        if not all(p in hw.qubits for p in cycle) or not all(
            cycle[(i + 1) % 4] in hw.adj[cycle[i]] for i in range(4)
        ):
            continue
        for rotation in range(4):
            for direction in (1, -1):
                ring = [cycle[(rotation + direction * i) % 4] for i in range(4)]
                labels = [ring[0], ring[1], ring[3], ring[2]]
                cost = sum(hw.node[p] for p in labels) + sum(
                    hw.edge(labels[a], labels[b]) for a, b in _SQUARE_CZ_PAIRS
                )
                candidate = (cost, tuple(labels))
                if best is None or candidate < best:
                    best = candidate
    return (list(best[1]), best[0]) if best is not None else None


def _route_connected(
    hw: Hardware, n: int, k: int, deadline: float
) -> tuple[list[cirq.GridQubit], list[cirq.Operation]]:
    """Route the existing logical preparation onto a connected patch with no full path.

    Inspired by the upstream routed candidate. Routing adds SWAPs, so keep this
    bounded fallback behind the efficient native-path search. The final routing
    permutation is harmless: every weight-k basis string has the same amplitude,
    and a qubit permutation bijects that set. Zero/full weight are invariant too.
    No ancilla is introduced because the graph contains exactly N output nodes.
    Reference: https://quantumai.google/cirq/transform/routing_transformer
    Expected routing failures raise NotImplementedError; physical errors propagate.
    """
    _, children = find_tree(hw, n, deadline)
    region = sorted(children)
    graph = nx.Graph()
    graph.add_nodes_from(region)
    graph.add_edges_from(
        (a, b) for a in region for b in sorted(hw.adj[a]) if b in children and a < b
    )
    logical_qubits = cirq.LineQubit.range(n)
    logical = cirq.Circuit(build_line_ops(logical_qubits, k, construction=hw.config.construction))
    mapper = cirq.HardCodedInitialMapper(dict(zip(logical_qubits, region)))
    try:
        routed, _, _ = cirq.RouteCQC(graph).route_circuit(logical, initial_mapper=mapper)
    except (ValueError, nx.NetworkXException) as exc:
        raise NotImplementedError(f"connected-patch routing failed: {exc}") from exc
    native = cirq.optimize_for_target_gateset(routed, gateset=cirq.CZTargetGateset())
    return region, list(native.all_operations())


def _first_split_ops(a: cirq.Qid, b: cirq.Qid, theta: float) -> list[cirq.Operation]:
    """Prepare cos(theta)|01>+sin(theta)|10> from known |01> with one native CZ.

    This state-specific identity is not a general Givens unitary. See the
    module derivation and the upstream first-W-split construction for provenance.
    """
    return [cirq.ry(2 * theta).on(a), cirq.H(b), cirq.CZ(a, b), cirq.H(b)]


def build_tree_ops(root: cirq.GridQubit, children: Tree) -> list[cirq.Operation]:
    """Ops (before scheduling) preparing the W state on a spanning tree."""
    size: dict = {}

    def subtree(v: cirq.GridQubit) -> int:
        size[v] = 1 + sum(subtree(c) for c in children[v])
        return size[v]

    subtree(root)
    ops: list[cirq.Operation] = [cirq.X(root)]
    first = True
    stack = [root]
    while stack:
        v = stack.pop()
        remaining = size[v]
        for c in children[v]:
            theta = math.asin(math.sqrt(size[c] / remaining))
            ops += _first_split_ops(c, v, theta) if first else givens_ops(c, v, theta)
            first = False
            remaining -= size[c]
        stack.extend(reversed(children[v]))
    return ops


def create_dicke_state(
    num_qubits: int,
    num_excitations: int,
    cz_pauli_error_rate: dict[tuple[cirq.GridQubit, cirq.GridQubit], tuple[float, float]],
    sq_pauli_error_rate: dict[cirq.GridQubit, tuple[float, float]],
    zero_errors: dict[cirq.GridQubit, tuple[float, float]],
    one_errors: dict[cirq.GridQubit, tuple[float, float]],
    config: PrepConfig = CONFIG,
) -> tuple[cirq.Circuit, set[cirq.GridQubit]]:
    """Create a CZ + PhasedXZ circuit preparing |D^N_n> on low-error Willow qubits.

    Parameters
    ----------
    num_qubits : int
        N >= 1.
    num_excitations : int
        n with 0 <= n <= N.
    cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors : dict
        Calibration maps as given by the challenge, (rate, uncertainty) tuples.
    config : PrepConfig
        Search / scheduling knobs.

    Returns
    -------
    circuit, qubits
        Circuit using only CZ on listed pairs and PhasedXZ on listed qubits,
        and the set of N qubits holding the state.

    Raises
    ------
    NotImplementedError
        If (N, n) is out of range or the working graph has no suitable layout.
    """
    started = time.monotonic()
    if (
        isinstance(num_qubits, (bool, np.bool_))
        or isinstance(num_excitations, (bool, np.bool_))
        or not isinstance(num_qubits, numbers.Integral)
        or not isinstance(num_excitations, numbers.Integral)
    ):
        raise NotImplementedError("N and n must be integers (booleans are not valid sizes)")
    n_q, k = int(num_qubits), int(num_excitations)
    if n_q < 1 or not 0 <= k <= n_q:
        raise NotImplementedError(f"invalid (N, n) = ({n_q}, {k})")
    deadline = time.monotonic() + config.search_time_s
    hw = Hardware(cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors, config)
    if not hw.qubits:
        raise NotImplementedError("no usable qubits in the calibration maps")
    if n_q > len(hw.qubits):
        raise NotImplementedError(f"requested {n_q} qubits, only {len(hw.qubits)} usable")
    flip = k > n_q - k
    k_eff = n_q - k if flip else k

    if k_eff == 1 and n_q > 2:
        root, children = find_tree(hw, n_q, deadline)
        qubits = list(children)
        ops = build_tree_ops(root, children)
    elif n_q == 1:
        qubits = [min(hw.qubits, key=lambda q: (hw.node[q], q))]
        ops = []
    else:
        square = (
            _find_square(hw)
            if config.construction == "optimized" and (n_q, k_eff) == (4, 2)
            else None
        )
        try:
            weights = line_edge_cz_counts(n_q, k_eff, construction=config.construction)
            qubits = find_line(hw, weights, deadline)
            ops = build_line_ops(qubits, k_eff, construction=config.construction)
            if square is not None:
                path_cost = sum(hw.node[q] for q in qubits) + sum(
                    w * hw.edge(a, b) for w, a, b in zip(weights, qubits, qubits[1:])
                )
                if square[1] <= path_cost:
                    qubits = square[0]
                    ops = _square_ops(qubits)
        except NotImplementedError:
            if square is not None:
                qubits, ops = square[0], _square_ops(square[0])
            else:
                if n_q > config.max_routing_qubits or time.monotonic() >= deadline:
                    raise
                qubits, ops = _route_connected(hw, n_q, k_eff, deadline)
    if flip:
        ops += [cirq.X(q) for q in qubits]
    # anchor every qubit so untouched ones (k=0) are still part of the circuit
    ops = [cirq.I(q) for q in qubits] + ops
    circuit = schedule(
        ops, config.use_dynamical_decoupling, config.dd_strategy, config.sparse_min_idle_slots
    )
    if len(circuit) > min(config.max_moments, MAX_MOMENTS):
        raise NotImplementedError(
            f"circuit has {len(circuit)} moments; limit is {min(config.max_moments, MAX_MOMENTS)}"
        )
    if time.monotonic() - started >= MAX_CONSTRUCTION_SECONDS:
        raise NotImplementedError("construction exhausted the challenge time budget")
    return circuit, set(qubits)


# %%
def create_dicke_state_adaptive(
    num_qubits: int, num_excitations: int
) -> tuple[cirq.Circuit, set[cirq.GridQubit]]:
    """Bonus: compact non-adaptive circuit on the full Willow105 graph (noise ignored).

    Currently non-adaptive (allowed by the rules): same constructions as
    create_dicke_state, uniform error maps, no DD, and single-qubit gates packed
    into the same moments as CZs on other qubits. Construction/search settings
    inherit CONFIG (including configured standalone exports), with the search
    budget capped at BONUS_SEARCH_SECONDS and dynamical decoupling disabled.

    Raises
    ------
    NotImplementedError
        If (N, n) is out of range.
    """
    dev = cirq_google.Willow105.metadata
    uniform_q = {q: (1e-3, 0.0) for q in dev.qubit_set}
    uniform_p = {tuple(p): (1e-3, 0.0) for p in dev.qubit_pairs}
    cfg = replace(
        CONFIG,
        use_dynamical_decoupling=False,
        search_time_s=min(CONFIG.search_time_s, BONUS_SEARCH_SECONDS),
    )
    circuit, qubits = create_dicke_state(
        num_qubits, num_excitations, uniform_p, uniform_q, uniform_q, uniform_q, cfg
    )
    ops = [op for op in circuit.all_operations()]
    packed = cirq.Circuit(ops)  # EARLIEST packing mixes 1q and CZ moments
    packed = cirq.merge_single_qubit_gates_to_phxz(packed)
    packed = cirq.drop_empty_moments(packed)
    return cirq.Circuit(packed.all_operations()), qubits
