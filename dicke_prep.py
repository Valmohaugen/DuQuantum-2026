"""Hardware-aware Dicke-state preparation for Google Willow (CZ + PhasedXZ only).

Self-contained: imports only cirq, cirq_google, numpy and the standard library, so
the whole file can be pasted into the challenge notebook as one cell.

Derivation (nearest-neighbour split-and-cyclic-shift)
-----------------------------------------------------
Target: |D^N_k> = C(N,k)^{-1/2} sum_{|x|=k} |x>. Recursion on the last qubit:

    |D^m_r> = sqrt(r/m) |D^{m-1}_{r-1}>|1> + sqrt((m-r)/m) |D^{m-1}_r>|0>.

Following Baertschi & Eidenbenz, "Deterministic Preparation of Dicke States"
(FCT 2019, arXiv:1904.07358), start from |0^{N-k} 1^k> on a line of N qubits and
process the line right to left. Before step m, positions 1..m hold |0^{m-r} 1^r>
(r = excitations not yet emitted). Step m must leave qubit m in |1> with
probability r/m; in the |0> branch the remaining ones must sit in positions
m-r..m-1, i.e. the window is cyclically shifted left by one. That shift is the
same as moving the rightmost hole (position h = m-r) right through the block of
ones to position m, which is a chain of *nearest-neighbour* partial swaps.

For pair (p, p+1) the left neighbour c = p-1 tells the gate which case it is in:
  * c = 0: the hole meets this pair for the first time. Apply the Givens
    rotation G(theta_r), |01> -> cos|01> + sin|10>, cos(theta_r) = sqrt(r/m), r = m-p.
  * c = 1: the hole is already moving. Apply a full swap G(pi/2).
Reachable inputs on (c, p, p+1) are {000, 001, 011, 111, 101}; the others are
don't-cares. That makes this 5-CZ multiplexed gate exact on them:

    MUX(theta) = Z_c . G_{p,p+1}(beta) . CZ_{c,p} . G_{p,p+1}(alpha),
    alpha = (theta + pi/2)/2,  beta = (theta - pi/2)/2.

Check: c = 0 gives G(alpha+beta) = G(theta). c = 1 gives, on span{|01>,|10>},
-G(beta) sigma_z G(alpha) = -sigma_z G(alpha-beta) = -sigma_z G(pi/2), which maps
|01> -> |10>. On |11>, CZ and Z_c each give -1, so the net phase is +1.
Pairs that can only see a first encounter use plain G(theta); pairs that can
only see a moving hole use G(pi/2). Bounding r in [max(0, k-(N-m)), min(k, m)]
removes most multiplexed gates near the start.

For k = 1 (W state) a spanning tree is shallower: the root starts in |1> and
hands amplitude sqrt(|S_c| / remaining) to each child subtree S_c with one
Givens rotation (depth ~ tree height instead of N).

For k > N/2 we prepare |D^N_{N-k}> and apply X to every qubit.
"""

from __future__ import annotations

import functools
import math
import time
from dataclasses import dataclass

import cirq
import cirq_google
import numpy as np

ErrorMap = dict  # qubit or qubit-pair -> (error rate, uncertainty)


@dataclass(frozen=True)
class PrepConfig:
    """Tunable constants for layout search and scheduling."""

    beam_width: int = 3000  # paths kept per step in the line search
    search_time_s: float = 20.0  # wall-clock budget for layout search
    idle_error_per_layer: float = 1.5e-3  # est. dephasing per qubit per CZ layer
    default_error: float = 1e-2  # used when a qubit/pair is missing from a map
    use_dynamical_decoupling: bool = True


CONFIG = PrepConfig()
CZ_PER_GIVENS = 2
CZ_PER_MUX_TARGET_PAIR = 4  # two Givens on (p, p+1)
CZ_PER_MUX_CONTROL_PAIR = 1  # the CZ(c, p)


# --------------------------------------------------------------------------- #
# Logical gate lists (positions on an abstract line / tree)
# --------------------------------------------------------------------------- #
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
    """
    gates: list[LineGate] = []
    for m in range(n_qubits, 1, -1):  # region = positions 0..m-1
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
    return gates


def line_edge_cz_counts(n_qubits: int, k: int) -> list[int]:
    """CZ count on each line edge (i, i+1); used to weight the layout search."""
    counts = [0] * max(n_qubits - 1, 0)
    for g in line_gates(n_qubits, k):
        if g.kind == "givens":
            counts[g.p] += CZ_PER_GIVENS
        else:
            counts[g.p] += CZ_PER_MUX_TARGET_PAIR
            counts[g.p - 1] += CZ_PER_MUX_CONTROL_PAIR
    return counts


# --------------------------------------------------------------------------- #
# Hardware graph and costs
# --------------------------------------------------------------------------- #
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
        self.config = config
        self.qubits = set(sq_pauli_error_rate)
        self.adj: dict[cirq.GridQubit, set[cirq.GridQubit]] = {q: set() for q in self.qubits}
        self.cz: dict[frozenset, float] = {}
        for pair, (err, _) in cz_pauli_error_rate.items():
            a, b = tuple(pair)
            if a in self.qubits and b in self.qubits:
                self.adj[a].add(b)
                self.adj[b].add(a)
                self.cz[frozenset((a, b))] = float(err)
        d = config.default_error
        self.node: dict[cirq.GridQubit, float] = {}
        for q in self.qubits:
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
    beam = sorted(((hw.node[q], (q,)) for q in hw.qubits), key=lambda t: t[0])
    beam = beam[: hw.config.beam_width]
    for i in range(n - 1):
        w = edge_weights[i]
        cand = []
        for cost, path in beam:
            tail = path[-1]
            for nb in hw.adj[tail]:
                if nb not in path:
                    cand.append((cost + w * hw.edge(tail, nb) + hw.node[nb], path + (nb,)))
        if not cand:
            raise NotImplementedError(f"no simple path of {n} working qubits")
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
    for root in sorted(hw.qubits, key=lambda q: hw.node[q]):
        if time.monotonic() > deadline and best is not None:
            break
        parent = {root: None}
        layer = [root]
        while layer and len(parent) < n:
            nxt = {}
            for v in layer:
                for nb in hw.adj[v]:
                    if nb in parent:
                        continue
                    c = hw.edge(v, nb)
                    if nb not in nxt or c < nxt[nb][0]:
                        nxt[nb] = (c, v)
            ranked = sorted(nxt, key=lambda q: 2 * nxt[q][0] + hw.node[q])
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
            children[v].sort(key=lambda c: -finish[c])
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


def _tree_finish_times(root, children) -> dict:
    """Givens time-steps until each subtree is fully populated (children served
    one per step, longest first)."""
    finish: dict = {}

    def visit(v):
        kids = children[v]
        for c in kids:
            visit(c)
        ts = sorted((finish[c] for c in kids), reverse=True)
        finish[v] = max((i + 1 + t for i, t in enumerate(ts)), default=0)

    visit(root)
    return finish


# --------------------------------------------------------------------------- #
# Gate synthesis
# --------------------------------------------------------------------------- #
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
    """5-CZ multiplexed Givens: G(theta) on (a,b) if c=0, G(pi/2) if c=1 (see module doc)."""
    alpha = 0.5 * (theta + math.pi / 2)
    beta = 0.5 * (theta - math.pi / 2)
    return [*givens_ops(a, b, alpha), cirq.CZ(c, a), *givens_ops(a, b, beta), cirq.Z(c)]


# --------------------------------------------------------------------------- #
# Scheduling: alternating [1q layer, CZ layer] moments, ALAP, with DD
# --------------------------------------------------------------------------- #
def schedule(ops: list[cirq.Operation], dynamical_decoupling: bool) -> cirq.Circuit:
    """Pack ops ALAP into alternating single-qubit / CZ moments and fill idles with DD.

    Single-qubit runs between CZs are fused into one PhasedXZGate placed directly
    before the next CZ on that qubit (or after the last CZ). Idle single-qubit slots
    between two operations of a qubit receive X/Y pulses whose net product is
    folded into the following gate, or cancelled inside the gap.
    """
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
        _add_dd(oneq, cz_layers)

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


def _add_dd(oneq: list[dict], cz_layers: list[list]) -> None:
    """In-place XY-style dynamical decoupling on idle single-qubit slots.

    Slot s precedes CZ layer s. A qubit is busy in slot s if it has a 1q gate
    there, and busy in CZ layer s if it is in a CZ there. A gap is a run of idle
    slots between two busy events with no CZ inside it.
    """
    n_slots = len(oneq)
    qubits = {q for slot in oneq for q in slot} | {q for lay in cz_layers for p in lay for q in p}
    in_cz = [{q for p in lay for q in p} for lay in cz_layers]
    for q in qubits:
        started = False
        gap: list[int] = []
        for s in range(n_slots):
            busy_1q = q in oneq[s]
            if busy_1q:
                if gap and started:
                    _fill_gap(oneq, q, gap, fold_into=s)
                gap = []
                started = True
            elif started:
                gap.append(s)
            if s < len(cz_layers) and q in in_cz[s]:
                if gap and started:
                    _fill_gap(oneq, q, gap, fold_into=None)
                gap = []
                started = True
        if gap and started:
            _fill_gap(oneq, q, gap, fold_into=None)


def _fill_gap(oneq: list[dict], q, gap: list[int], fold_into: int | None) -> None:
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
        if cirq.equal_up_to_global_phase(acc, np.eye(2), atol=1e-10):
            # last pulse would be identity: make the pattern X..X instead
            oneq[gap[-1]][q] = _X
            oneq[gap[-2]][q] = oneq[gap[-2]][q] @ _X


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def build_line_ops(qubits: list[cirq.GridQubit], k: int) -> list[cirq.Operation]:
    """Ops (before scheduling) preparing |D^N_k> on a nearest-neighbour path."""
    n = len(qubits)
    ops: list[cirq.Operation] = [cirq.X(q) for q in qubits[n - k :]]
    for g in line_gates(n, k):
        a, b = qubits[g.p], qubits[g.p + 1]
        if g.kind == "givens":
            ops += givens_ops(a, b, g.theta)
        else:
            ops += mux_ops(qubits[g.p - 1], a, b, g.theta)
    return ops


def build_tree_ops(root, children) -> list[cirq.Operation]:
    """Ops (before scheduling) preparing the W state on a spanning tree."""
    size: dict = {}

    def subtree(v):
        size[v] = 1 + sum(subtree(c) for c in children[v])
        return size[v]

    subtree(root)
    ops: list[cirq.Operation] = [cirq.X(root)]
    stack = [root]
    while stack:
        v = stack.pop()
        remaining = size[v]
        for c in children[v]:
            theta = math.asin(math.sqrt(size[c] / remaining))
            ops += givens_ops(c, v, theta)  # |0_c 1_v> -> cos|01> + sin|10>
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
    n_q, k = int(num_qubits), int(num_excitations)
    if n_q < 1 or not 0 <= k <= n_q:
        raise NotImplementedError(f"invalid (N, n) = ({n_q}, {k})")
    deadline = time.monotonic() + config.search_time_s
    hw = Hardware(cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors, config)
    flip = k > n_q - k
    k_eff = n_q - k if flip else k

    if k_eff == 1 and n_q > 2:
        root, children = find_tree(hw, n_q, deadline)
        qubits = list(children)
        ops = build_tree_ops(root, children)
    elif n_q == 1:
        qubits = [min(hw.qubits, key=lambda q: hw.node[q])]
        ops = []
    else:
        qubits = find_line(hw, line_edge_cz_counts(n_q, k_eff), deadline)
        ops = build_line_ops(qubits, k_eff)
    if flip:
        ops += [cirq.X(q) for q in qubits]
    # anchor every qubit so untouched ones (k=0) are still part of the circuit
    ops = [cirq.I(q) for q in qubits] + ops
    circuit = schedule(ops, config.use_dynamical_decoupling)
    return circuit, set(qubits)


def create_dicke_state_adaptive(
    num_qubits: int, num_excitations: int
) -> tuple[cirq.Circuit, set[cirq.GridQubit]]:
    """Bonus: minimum-moment circuit on the full Willow105 graph (noise ignored).

    Currently non-adaptive (allowed by the rules): same constructions as
    create_dicke_state, uniform error maps, no DD, and single-qubit gates packed
    into the same moments as CZs on other qubits.

    Raises
    ------
    NotImplementedError
        If (N, n) is out of range.
    """
    dev = cirq_google.Willow105.metadata
    uniform_q = {q: (1e-3, 0.0) for q in dev.qubit_set}
    uniform_p = {tuple(p): (1e-3, 0.0) for p in dev.qubit_pairs}
    cfg = PrepConfig(use_dynamical_decoupling=False, search_time_s=10.0)
    circuit, qubits = create_dicke_state(
        num_qubits, num_excitations, uniform_p, uniform_q, uniform_q, uniform_q, cfg
    )
    ops = [op for op in circuit.all_operations()]
    packed = cirq.Circuit(ops)  # EARLIEST packing mixes 1q and CZ moments
    packed = cirq.merge_single_qubit_gates_to_phxz(packed)
    packed = cirq.drop_empty_moments(packed)
    return cirq.Circuit(packed.all_operations()), qubits
