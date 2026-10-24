"""Dicke-state preparation for the Google Quantum AI / Willow challenge.

Strategy (from the background report):
  * Pick a compact, low-error patch of N qubits from the supplied calibration dicts.
  * n == 1 (W state): native spanning-tree construction on the patch. Each edge of the tree
    is one excitation-preserving Givens rotation (2 CZ; the very first split costs 1 CZ), so a
    W state uses exactly 2N-3 CZs and depth ~ tree depth instead of N.
  * n >= 2: Bärtschi-Eidenbenz split-and-cyclic-shift (SCS) circuit written on logical qubits
    (CNOT + Ry, the doubly-controlled Ry uses an exact 4-CNOT construction), routed onto the
    patch with cirq.RouteCQC. The Dicke state is permutation-symmetric, so the final qubit
    permutation left by routing does not matter.
  * n > N/2: prepare D(N, N-n) and flip every qubit (fewer excitations during the circuit).
  * Compile to CZ + PhasedXZ, right-align (qubits stay in |0> as long as possible), separate CZ
    and single-qubit layers, add dynamical decoupling on idle qubits, and convert every
    single-qubit gate to PhasedXZ without merging away the DD pulses.

Only cirq, cirq_google, numpy and the standard library are used (networkx ships with cirq).
"""
from __future__ import annotations

import math
import time
from collections import deque

import cirq
import networkx as nx
import numpy as np

MAX_MOMENTS = 1750


# ============================================================================ calibration helpers
def _value(entry):
    """Error dict values are (rate, uncertainty) tuples."""
    return float(entry[0]) if isinstance(entry, (tuple, list, np.ndarray)) else float(entry)


def _build_graph(cz_err, sq_err, zero_err, one_err) -> nx.Graph:
    usable = set(sq_err) & set(zero_err) & set(one_err)
    g = nx.Graph()
    for pair, entry in cz_err.items():
        a, b = tuple(pair)  # key order is arbitrary (built from a frozenset)
        if a in usable and b in usable:
            e = _value(entry)
            if not g.has_edge(a, b) or g[a][b]["err"] > e:
                g.add_edge(a, b, err=e)
    return g


def _node_costs(g, n_qubits, n_exc, sq_err, zero_err, one_err):
    w1 = n_exc / n_qubits  # probability a qubit reads 1 in the target state
    return {
        q: w1 * _value(one_err[q]) + (1 - w1) * _value(zero_err[q]) + 4 * _value(sq_err[q])
        for q in g.nodes
    }


def _grow_region(g, root, size, node_cost, lam):
    """Greedy best-first growth from `root`, penalising distance to keep the patch compact."""
    dist = nx.single_source_shortest_path_length(g, root)
    region = [root]
    in_region = {root}
    while len(region) < size:
        best, best_score = None, math.inf
        for r in region:
            for c in g.neighbors(r):
                if c in in_region:
                    continue
                score = node_cost[c] + g[r][c]["err"] + lam * dist[c]
                if score < best_score:
                    best, best_score = c, score
        if best is None:
            return None  # component too small
        region.append(best)
        in_region.add(best)
    return region


def _bfs_tree(g, root, nodes):
    """Shortest-depth spanning tree of g[nodes]; ties broken by lowest CZ error."""
    sub = g.subgraph(nodes)
    depth = nx.single_source_shortest_path_length(sub, root)
    parent = {}
    for v in nodes:
        if v == root:
            continue
        cands = [u for u in sub.neighbors(v) if depth[u] == depth[v] - 1]
        parent[v] = min(cands, key=lambda u: sub[u][v]["err"])
    children = {v: [] for v in nodes}
    for v, p in parent.items():
        children[p].append(v)
    return parent, children, depth


def select_patch(n_qubits, n_exc, cz_err, sq_err, zero_err, one_err, lam=2e-3, top=6):
    """Return up to `top` candidate (cost, root, region) patches, best first.

    Cost model (heuristic): sum of readout+single-qubit costs, plus estimated CZ count times
    the mean CZ error inside the patch, plus an idle-time penalty proportional to tree depth.
    """
    g = _build_graph(cz_err, sq_err, zero_err, one_err)
    node_cost = _node_costs(g, n_qubits, n_exc, sq_err, zero_err, one_err)
    k = min(n_exc, n_qubits - n_exc)
    est_cz = 2 * n_qubits - 3 if k <= 1 else 5 * n_qubits * k - 5 * k * k - 2 * n_qubits
    cands = []
    for root in g.nodes:
        region = _grow_region(g, root, n_qubits, node_cost, lam)
        if region is None:
            continue
        parent, children, depth = _bfs_tree(g, root, region)
        tree_err = sum(g[v][p]["err"] for v, p in parent.items())
        sub = g.subgraph(region)
        mean_err = np.mean([d["err"] for _, _, d in sub.edges(data=True)]) if sub.number_of_edges() else 0
        cz_cost = 2 * tree_err if k <= 1 else est_cz * mean_err
        idle = 1e-3 * max(depth.values()) * (n_qubits if k <= 1 else est_cz / n_qubits)
        cost = sum(node_cost[q] for q in region) + cz_cost + idle
        cands.append((cost, root, region))
    if not cands:
        raise NotImplementedError("no connected patch of the requested size")
    cands.sort(key=lambda t: t[0])
    return g, cands[:top]


# ============================================================================ W state (native tree)
def _givens(theta):
    """|10> -> cos|10> + sin|01>, |01> -> -sin|10> + cos|01>; |00>, |11> untouched."""
    c, s = math.cos(theta), math.sin(theta)
    return cirq.MatrixGate(
        # Cirq basis order on (v, c): |00>, |01>=(v0,c1), |10>=(v1,c0), |11>
        np.array([[1, 0, 0, 0], [0, c, s, 0], [0, -s, c, 0], [0, 0, 0, 1]], dtype=complex)
    )


def w_state_ops(g, root, region):
    """W state on `region` by splitting the excitation down a BFS tree rooted at `root`."""
    if len(region) == 1:
        return [cirq.X(root)]
    _, children, _ = _bfs_tree(g, root, region)
    size = {}

    def subtree_size(v):
        size[v] = 1 + sum(subtree_size(c) for c in children[v])
        return size[v]

    subtree_size(root)
    for v in children:
        children[v].sort(key=lambda c: -size[c])  # biggest subtree first -> shallower

    ops, first = [], True
    stack = [root]
    while stack:
        v = stack.pop()
        remaining = size[v]
        for c in children[v]:
            theta = math.asin(math.sqrt(size[c] / remaining))
            if first:  # |00> -> cos|1_v 0_c> + sin|0_v 1_c> with a single CZ
                ops += [cirq.ry(2 * theta).on(c), cirq.X(v), cirq.CNOT(c, v)]
                first = False
            else:
                ops.append(_givens(theta).on(v, c))  # qubit order (v, c): v holds |1>
            remaining -= size[c]
        stack.extend(reversed(children[v]))
    return ops


# ============================================================================ general Dicke (SCS)
def _cry(theta, c, t):
    return [cirq.ry(theta / 2).on(t), cirq.CNOT(c, t), cirq.ry(-theta / 2).on(t), cirq.CNOT(c, t)]


def _ccry(theta, a, b, t):
    """Exact doubly-controlled Ry with 4 CNOTs (X Ry(b) X = Ry(-b), so only |11> rotates)."""
    p = theta / 4
    return [
        cirq.ry(p).on(t), cirq.CNOT(b, t), cirq.ry(-p).on(t), cirq.CNOT(a, t),
        cirq.ry(p).on(t), cirq.CNOT(b, t), cirq.ry(-p).on(t), cirq.CNOT(a, t),
    ]


def _scs_blocks(m, k):
    """Abstract SCS_{m,k} blocks on 1-indexed qubits: ('cx',c,t) ('cry',th,c,t) ('ccry',th,a,b,t)."""
    blocks = [("cx", m - 1, m), ("cry", 2 * math.acos(math.sqrt(1 / m)), m, m - 1), ("cx", m - 1, m)]
    for l in range(2, k + 1):
        blocks += [
            ("cx", m - l, m),
            ("ccry", 2 * math.acos(math.sqrt(l / m)), m, m - l + 1, m - l),
            ("cx", m - l, m),
        ]
    return blocks


def _propagate_constants(n_qubits, k, blocks):
    """Drop/simplify blocks whose controls are classically known (cf. Mukherjee et al.,
    arXiv:2007.01681). Tracks which qubits are still in a known basis state."""
    known = {i: (1 if i > n_qubits - k else 0) for i in range(1, n_qubits + 1)}
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "cx":
            _, c, t = b
            if known[c] == 0:
                continue
            if known[c] == 1:
                out.append(("x", t))
                if known[t] is not None:
                    known[t] ^= 1
                continue
            out.append(b)
            known[t] = None
        elif kind == "cry":
            _, th, c, t = b
            if known[c] == 0:
                continue
            out.append(("ry", th, t) if known[c] == 1 else b)
            known[t] = None
        elif kind == "ccry":
            _, th, a, bb, t = b
            if known[a] == 0 or known[bb] == 0:
                continue
            if known[a] == 1 and known[bb] == 1:
                out.append(("ry", th, t))
            elif known[a] == 1:
                out.append(("cry", th, bb, t))
            elif known[bb] == 1:
                out.append(("cry", th, a, t))
            else:
                out.append(b)
            known[t] = None
    return out, known


def scs_dicke_logical(n_qubits, k, simplify=True):
    """Bärtschi-Eidenbenz (arXiv:1904.07358) on LineQubits; |0^(N-k) 1^k> -> |D(N,k)>."""
    q = cirq.LineQubit.range(n_qubits)
    Q = lambda i: q[i - 1]
    blocks = []
    for m in range(n_qubits, 1, -1):
        blocks += _scs_blocks(m, min(k, m - 1))
    ops = []
    if simplify:
        blocks, _ = _propagate_constants(n_qubits, k, blocks)
        # initial |1>s are folded into the first gate on each qubit by the compiler
    ops += [cirq.X(q[i]) for i in range(n_qubits - k, n_qubits)]
    for b in blocks:
        if b[0] == "x":
            ops.append(cirq.X(Q(b[1])))
        elif b[0] == "ry":
            ops.append(cirq.ry(b[1]).on(Q(b[2])))
        elif b[0] == "cx":
            ops.append(cirq.CNOT(Q(b[1]), Q(b[2])))
        elif b[0] == "cry":
            ops += _cry(b[1], Q(b[2]), Q(b[3]))
        else:
            ops += _ccry(b[1], Q(b[2]), Q(b[3]), Q(b[4]))
    return cirq.Circuit(ops)


def route_onto(logical: cirq.Circuit, g: nx.Graph, region, mapping=None, lookahead=8):
    sub = nx.Graph(g.subgraph(region))
    kwargs = {"lookahead_radius": lookahead}
    if mapping is not None:
        kwargs["initial_mapper"] = cirq.HardCodedInitialMapper(mapping)
    routed, _, _ = cirq.RouteCQC(sub).route_circuit(logical, **kwargs)
    return routed


def _rect_layouts(g, n_qubits, widths=(2, 3)):
    """Zig-zag fills of w-row rectangles: logical i -> (r0 + i % w, c0 + i // w).
    SCS couples logical i to i-1..i-k, so packing the line into a short band cuts SWAPs."""
    rows = [q.row for q in g.nodes]
    cols = [q.col for q in g.nodes]
    for w in widths:
        for r0 in range(min(rows), max(rows) + 1):
            for c0 in range(min(cols), max(cols) + 1):
                cells = [cirq.GridQubit(r0 + i % w, c0 + i // w) for i in range(n_qubits)]
                if all(q in g for q in cells) and nx.is_connected(g.subgraph(cells)):
                    yield cells


def _est_error(circuit, g, node_cost, sq_err):
    """Rough log-infidelity: CZ errors on the pairs actually used + readout + idle."""
    err = 0.0
    for op in circuit.all_operations():
        if len(op.qubits) == 2:
            err += g[op.qubits[0]][op.qubits[1]]["err"]
        else:
            err += _value(sq_err[op.qubits[0]])
    qs = circuit.all_qubits()
    err += sum(node_cost[q] for q in qs)
    err += 2e-4 * len(qs) * len(circuit)  # ~idle decoherence per qubit-moment (T1~70us)
    return err


# ============================================================================ compilation
def _is_2q(op):
    return len(op.qubits) == 2


def _is_1q(op):
    return len(op.qubits) == 1


_X_PULSE = cirq.PhasedXZGate(x_exponent=1.0, z_exponent=0.0, axis_phase_exponent=0.0)


def sparse_echo(circuit: cirq.Circuit, min_idle=8) -> cirq.Circuit:
    """One X-X echo pair per idle window of >= `min_idle` moments (pulses at 1/4 and 3/4
    of the window), instead of filling every idle slot. X.X = I, so the unitary is unchanged.
    Windows run from a qubit's first gate to the end of the circuit (trailing idle included)."""
    moments = [list(m.operations) for m in circuit]
    T = len(moments)
    busy = {}
    for t, m in enumerate(circuit):
        for op in m:
            for q in op.qubits:
                busy.setdefault(q, []).append(t)
    for q, times in busy.items():
        stops = times + [T]
        for a, b in zip(stops[:-1], stops[1:]):
            gap = b - a - 1  # idle moments strictly between
            if gap >= min_idle:
                t1, t2 = a + 1 + gap // 4, a + 1 + (3 * gap) // 4
                if t1 != t2:
                    moments[t1].append(_X_PULSE.on(q))
                    moments[t2].append(_X_PULSE.on(q))
    return cirq.Circuit(cirq.Moment(ops) for ops in moments)


def compile_for_willow(circuit: cirq.Circuit, dd_schema="DEFAULT", align_right=True):
    c = cirq.optimize_for_target_gateset(circuit, gateset=cirq.CZTargetGateset())
    c = cirq.eject_phased_paulis(c)
    c = cirq.eject_z(c)
    c = cirq.merge_single_qubit_gates_to_phxz(c)
    c = cirq.drop_negligible_operations(c)
    c = cirq.drop_empty_moments(c)
    if align_right:  # stratify the mirrored circuit -> layers packed as late as possible
        rev = cirq.Circuit(c.moments[::-1])
        rev = cirq.stratified_circuit(rev, categories=[_is_2q, _is_1q])
        c = cirq.Circuit(rev.moments[::-1])
    else:
        c = cirq.stratified_circuit(c, categories=[_is_2q, _is_1q])
    c = cirq.drop_empty_moments(c)
    if dd_schema == "sparse":
        c = sparse_echo(c)
    elif dd_schema:
        qs = sorted(c.all_qubits())
        tmp = c + cirq.Moment(cirq.measure(*qs, key="__dd_tmp__"))
        tmp = cirq.add_dynamical_decoupling(
            tmp, schema=dd_schema, single_qubit_gate_moments_only=False
        )
        c = cirq.Circuit(tmp.moments[:-1])  # drop the temporary measurement
    def to_phxz(op, _):
        if _is_1q(op) and not isinstance(op.gate, cirq.PhasedXZGate):
            u = cirq.unitary(op)
            if np.allclose(u, np.eye(2) * u[0, 0]):
                return []  # identity filler
            return cirq.PhasedXZGate.from_matrix(u).on(*op.qubits)
        if _is_2q(op) and op.gate != cirq.CZ:
            raise ValueError(f"unexpected 2q gate {op}")
        return op
    c = cirq.map_operations_and_unroll(c, to_phxz)
    return c


def _final_flip(circuit, qubits):
    """Append X on every qubit, folded into the last single-qubit moment where possible."""
    c = circuit + cirq.Moment(cirq.X(q) for q in qubits)
    c = cirq.merge_single_qubit_moments_to_phxz(c)
    return cirq.map_operations(
        c,
        lambda op, _: cirq.PhasedXZGate.from_matrix(cirq.unitary(op)).on(*op.qubits)
        if _is_1q(op) and not isinstance(op.gate, cirq.PhasedXZGate) else op,
    )


# ============================================================================ public API
def count_cz(circuit):
    return sum(1 for op in circuit.all_operations() if _is_2q(op))


def create_dicke_state(
    num_qubits, num_excitations, cz_pauli_error_rate, sq_pauli_error_rate, zero_errors,
    one_errors, dd_schema="sparse", n_candidates=6, time_budget_s=12.0, objective="error",
):
    """Challenge entry point. Extra keyword args are optional knobs for experiments."""
    t0 = time.time()
    N, n = num_qubits, num_excitations
    if N < 1 or not 0 <= n <= N:
        raise NotImplementedError
    flip = n > N - n
    k = N - n if flip else n
    g, cands = select_patch(N, n, cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors)

    if k == 0:  # product state |0..0> or |1..1>
        region = cands[0][2]
        gate = cirq.PhasedXZGate(x_exponent=1.0 if flip else 0.0, z_exponent=0, axis_phase_exponent=0)
        return cirq.Circuit(cirq.Moment(gate.on(q) for q in region)), set(region)

    node_cost = _node_costs(g, N, n, sq_pauli_error_rate, zero_errors, one_errors)

    if k == 1:  # W state: native tree on the best patch
        _, root, region = cands[0]
        raw = cirq.Circuit(w_state_ops(g, root, region))
    else:
        # Candidate layouts: greedy compact patches (router picks the mapping) and zig-zag
        # rectangles (hard-coded mapping). Pre-rank by a static cost, then route the best few
        # and keep the routed circuit with the lowest estimated error (or fewest moments).
        lq = cirq.LineQubit.range(N)
        layouts = [(c, region, None) for c, _, region in cands[:3]]
        rects = []
        for cells in _rect_layouts(g, N):
            sub = g.subgraph(cells)
            mean_err = np.mean([d["err"] for *_, d in sub.edges(data=True)])
            rects.append((sum(node_cost[q] for q in cells) + 1.5 * k * N * mean_err, cells))
        rects.sort(key=lambda t: t[0])
        layouts += [(c, cells, dict(zip(lq, cells))) for c, cells in rects[:n_candidates]]

        logical = cirq.optimize_for_target_gateset(
            scs_dicke_logical(N, k), gateset=cirq.CZTargetGateset()
        )
        best = None
        for _, region, mapping in layouts:
            if best is not None and time.time() - t0 > time_budget_s:
                break
            try:
                routed = route_onto(logical, g, region, mapping)
            except Exception:  # RouteCQC occasionally fails on tiny/odd subgraphs
                continue
            routed = cirq.optimize_for_target_gateset(routed, gateset=cirq.CZTargetGateset())
            routed = cirq.drop_empty_moments(cirq.merge_single_qubit_gates_to_phxz(routed))
            if objective == "moments":
                score = len(cirq.stratified_circuit(routed, categories=[_is_2q, _is_1q]))
            else:
                score = _est_error(routed, g, node_cost, sq_pauli_error_rate)
            if best is None or score < best[0]:
                best = (score, routed, region)
        if best is None:
            raise NotImplementedError("routing failed")
        _, raw, region = best

    circuit = compile_for_willow(raw, dd_schema=dd_schema)
    if flip:
        circuit = _final_flip(circuit, region)
    if len(circuit) > MAX_MOMENTS:
        raise NotImplementedError(f"{len(circuit)} moments > {MAX_MOMENTS}")
    return circuit, set(region)


def _uniform_calibration(device):
    qs = list(device.metadata.qubit_set)
    pairs = [tuple(p) for p in device.metadata.qubit_pairs]
    return (
        {p: (2.5e-3, 0) for p in pairs}, {q: (4e-4, 0) for q in qs},
        {q: (5e-3, 0) for q in qs}, {q: (1e-2, 0) for q in qs},
    )


def create_dicke_state_adaptive(num_qubits, num_excitations):
    """Bonus baseline: reuses the unitary construction (allowed by the rules) with no DD,
    since the bonus is scored on moment count only. Adaptive shortcuts are future work."""
    from judge import get_device

    cz, sq, z0, z1 = _uniform_calibration(get_device())
    return create_dicke_state(
        num_qubits, num_excitations, cz, sq, z0, z1, dd_schema=None, objective="moments"
    )