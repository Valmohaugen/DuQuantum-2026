"""Dicke state preparation on Willow (DuQuantum 2026, Google Quantum AI track).

Overview:
  1. Choose a compact patch of N good qubits using the calibration data.
  2. n = 1 (W state): spread one excitation down a spanning tree of the patch.
     Each tree edge is a single Givens rotation, so this takes 2N - 3 CZs and the
     depth grows with the tree height instead of N.
  3. n >= 2: Bartschi & Eidenbenz split-and-cyclic-shift circuit on a line of
     logical qubits, routed onto the patch with cirq.RouteCQC. The Dicke state is
     symmetric under permuting qubits, so we don't care where routing leaves them.
  4. n > N/2: build D(N, N - n) and flip every qubit at the end.
  5. Compile to CZ + PhasedXZ, push gates as late as possible (qubits sitting in
     |0> don't decohere) and add echo pulses on long idle stretches.
"""
import math
import time

import cirq
import cirq_google
import networkx as nx
import numpy as np

MAX_MOMENTS = 1750
IDLE_ERR = 2e-4  # rough error per idle qubit per moment, T1 ~ 70 us


def _rate(entry):
    # calibration values are (rate, uncertainty) pairs
    if isinstance(entry, (tuple, list, np.ndarray)):
        return float(entry[0])
    return float(entry)


def _is_1q(op):
    return len(op.qubits) == 1


def _is_2q(op):
    return len(op.qubits) == 2


# --- picking qubits ---------------------------------------------------------

def build_graph(cz_err, sq_err, zero_err, one_err):
    """Coupling graph of working qubits, with the CZ error stored on each edge."""
    good = set(sq_err) & set(zero_err) & set(one_err)
    g = nx.Graph()
    for pair, entry in cz_err.items():
        a, b = tuple(pair)
        if a not in good or b not in good:
            continue
        err = _rate(entry)
        if not g.has_edge(a, b) or g[a][b]["err"] > err:
            g.add_edge(a, b, err=err)
    return g


def qubit_costs(g, N, n, sq_err, zero_err, one_err):
    # a qubit reads 1 with probability n/N in the target state, so weight the
    # two readout errors by that
    p1 = n / N
    return {
        q: p1 * _rate(one_err[q]) + (1 - p1) * _rate(zero_err[q]) + 4 * _rate(sq_err[q])
        for q in g.nodes
    }


def grow_patch(g, root, size, cost, lam):
    """Greedily add the cheapest neighbour until we have `size` qubits.

    lam * distance-from-root keeps the patch from turning into a long snake.
    """
    dist = nx.single_source_shortest_path_length(g, root)
    patch = [root]
    seen = {root}
    while len(patch) < size:
        best, best_score = None, math.inf
        for u in patch:
            for v in g.neighbors(u):
                if v in seen:
                    continue
                score = cost[v] + g[u][v]["err"] + lam * dist[v]
                if score < best_score:
                    best, best_score = v, score
        if best is None:
            return None  # connected component is too small
        patch.append(best)
        seen.add(best)
    return patch


def bfs_tree(g, root, nodes):
    """Shallowest spanning tree of g[nodes]. Ties go to the lower-error edge."""
    sub = g.subgraph(nodes)
    depth = nx.single_source_shortest_path_length(sub, root)
    parent = {}
    for v in nodes:
        if v != root:
            options = [u for u in sub.neighbors(v) if depth[u] == depth[v] - 1]
            parent[v] = min(options, key=lambda u: sub[u][v]["err"])
    children = {v: [] for v in nodes}
    for v, p in parent.items():
        children[p].append(v)
    return parent, children, depth


def rank_patches(N, n, cz_err, sq_err, zero_err, one_err, lam=2e-3, top=6):
    """Try growing a patch from every qubit and return the `top` cheapest.

    The cost is a heuristic: readout + single-qubit error on each qubit, the
    expected CZ count times the patch's CZ error, and a small idle penalty that
    grows with the tree depth. Returns (graph, [(cost, root, patch), ...]).
    """
    g = build_graph(cz_err, sq_err, zero_err, one_err)
    cost = qubit_costs(g, N, n, sq_err, zero_err, one_err)
    k = min(n, N - n)
    if k <= 1:
        cz_estimate = 2 * N - 3
    else:
        cz_estimate = 5 * N * k - 5 * k * k - 2 * N  # fitted to our SCS circuits

    patches = []
    for root in g.nodes:
        patch = grow_patch(g, root, N, cost, lam)
        if patch is None:
            continue
        parent, _, depth = bfs_tree(g, root, patch)
        sub = g.subgraph(patch)
        if k <= 1:
            cz_cost = 2 * sum(g[v][p]["err"] for v, p in parent.items())
            idle = 1e-3 * max(depth.values()) * N
        else:
            errs = [d["err"] for _, _, d in sub.edges(data=True)]
            cz_cost = cz_estimate * (np.mean(errs) if errs else 0)
            idle = 1e-3 * max(depth.values()) * (cz_estimate / N)
        total = sum(cost[q] for q in patch) + cz_cost + idle
        patches.append((total, root, patch))

    if not patches:
        raise NotImplementedError("no connected patch of the requested size")
    patches.sort(key=lambda t: t[0])
    return g, patches[:top]


# --- W state ------------------------------------------------------------------

def givens(theta):
    """Moves amplitude between |10> and |01>; |00> and |11> are untouched.

    On qubits (v, c):  |10> -> cos|10> + sin|01>.
    """
    c, s = math.cos(theta), math.sin(theta)
    # cirq basis order is |00>, |01>, |10>, |11> with v as the first qubit
    u = np.array([[1, 0, 0, 0],
                  [0, c, s, 0],
                  [0, -s, c, 0],
                  [0, 0, 0, 1]], dtype=complex)
    return cirq.MatrixGate(u)


def w_state_ops(g, root, patch):
    """Start with the excitation on `root` and hand it down the tree.

    A node holding the excitation with `remaining` qubits left in its subtree
    gives each child a share of size(child) / remaining.
    """
    _, children, _ = bfs_tree(g, root, patch)
    size = {}

    def count(v):
        size[v] = 1 + sum(count(c) for c in children[v])
        return size[v]

    count(root)
    # visit big subtrees first, which keeps the circuit shallower
    for v in children:
        children[v].sort(key=lambda c: -size[c])

    ops = []
    first = True
    stack = [root]
    while stack:
        v = stack.pop()
        remaining = size[v]
        for c in children[v]:
            theta = math.asin(math.sqrt(size[c] / remaining))
            if first:
                # nothing is excited yet, so the first split only needs one CNOT:
                # |00> -> cos|1_v 0_c> + sin|0_v 1_c>
                ops += [cirq.ry(2 * theta).on(c), cirq.X(v), cirq.CNOT(c, v)]
                first = False
            else:
                ops.append(givens(theta).on(v, c))
            remaining -= size[c]
        stack.extend(reversed(children[v]))
    return ops


# --- general Dicke states (split & cyclic shift) -------------------------------
# Qubits are numbered 1..N here to match the paper (arXiv:1904.07358).

def _cry(theta, c, t):
    return [cirq.ry(theta / 2).on(t), cirq.CNOT(c, t),
            cirq.ry(-theta / 2).on(t), cirq.CNOT(c, t)]


def _ccry(theta, a, b, t):
    # doubly controlled Ry with 4 CNOTs. A CNOT turns Ry(x) into Ry(-x), so the
    # four quarter-angle rotations only add up when both a and b are 1.
    p = theta / 4
    return [
        cirq.ry(p).on(t), cirq.CNOT(b, t), cirq.ry(-p).on(t), cirq.CNOT(a, t),
        cirq.ry(p).on(t), cirq.CNOT(b, t), cirq.ry(-p).on(t), cirq.CNOT(a, t),
    ]


def scs_gates(m, k):
    """Gate list for the SCS_{m,k} block, as tuples:
    ("cx", c, t), ("cry", theta, c, t), ("ccry", theta, a, b, t)."""
    gates = [
        ("cx", m - 1, m),
        ("cry", 2 * math.acos(math.sqrt(1 / m)), m, m - 1),
        ("cx", m - 1, m),
    ]
    for l in range(2, k + 1):
        gates += [
            ("cx", m - l, m),
            ("ccry", 2 * math.acos(math.sqrt(l / m)), m, m - l + 1, m - l),
            ("cx", m - l, m),
        ]
    return gates


def prune_known_controls(N, k, gates):
    """Remove or shrink gates whose controls are still in a known 0/1 state.

    At the start qubits N-k+1..N are 1 and the rest are 0, and many early gates
    are controlled on qubits nothing has touched yet. Same idea as
    Mukherjee et al., arXiv:2007.01681.
    """
    known = {i: int(i > N - k) for i in range(1, N + 1)}  # None = unknown
    out = []
    for gate in gates:
        kind = gate[0]
        if kind == "cx":
            _, c, t = gate
            if known[c] == 0:
                continue
            if known[c] == 1:
                out.append(("x", t))
                if known[t] is not None:
                    known[t] ^= 1
            else:
                out.append(gate)
                known[t] = None
        elif kind == "cry":
            _, theta, c, t = gate
            if known[c] == 0:
                continue
            out.append(("ry", theta, t) if known[c] == 1 else gate)
            known[t] = None
        elif kind == "ccry":
            _, theta, a, b, t = gate
            if known[a] == 0 or known[b] == 0:
                continue
            if known[a] == 1 and known[b] == 1:
                out.append(("ry", theta, t))
            elif known[a] == 1:
                out.append(("cry", theta, b, t))
            elif known[b] == 1:
                out.append(("cry", theta, a, t))
            else:
                out.append(gate)
            known[t] = None
    return out


def scs_circuit(N, k):
    """|0..0 1..1> (k ones) -> D(N, k) on LineQubits 0..N-1."""
    q = lambda i: cirq.LineQubit(i - 1)  # paper numbering -> LineQubit
    gates = []
    for m in range(N, 1, -1):
        gates += scs_gates(m, min(k, m - 1))
    gates = prune_known_controls(N, k, gates)

    ops = [cirq.X(cirq.LineQubit(i)) for i in range(N - k, N)]
    for kind, *args in gates:
        if kind == "x":
            ops.append(cirq.X(q(args[0])))
        elif kind == "ry":
            ops.append(cirq.ry(args[0]).on(q(args[1])))
        elif kind == "cx":
            ops.append(cirq.CNOT(q(args[0]), q(args[1])))
        elif kind == "cry":
            ops += _cry(args[0], q(args[1]), q(args[2]))
        else:
            ops += _ccry(args[0], q(args[1]), q(args[2]), q(args[3]))
    return cirq.Circuit(ops)


def route(logical, g, patch, mapping=None, lookahead=8):
    kwargs = {"lookahead_radius": lookahead}
    if mapping is not None:
        kwargs["initial_mapper"] = cirq.HardCodedInitialMapper(mapping)
    router = cirq.RouteCQC(nx.Graph(g.subgraph(patch)))
    routed, _, _ = router.route_circuit(logical, **kwargs)
    return routed


def zigzag_layouts(g, N, widths=(2, 3)):
    """Fold the logical line into a band `w` rows tall: i -> (r0 + i % w, c0 + i // w).

    SCS mostly couples qubit i to its last k neighbours, so a short band keeps
    them close and RouteCQC needs fewer SWAPs than on a random patch.
    """
    rows = [q.row for q in g.nodes]
    cols = [q.col for q in g.nodes]
    for w in widths:
        for r0 in range(min(rows), max(rows) + 1):
            for c0 in range(min(cols), max(cols) + 1):
                cells = [cirq.GridQubit(r0 + i % w, c0 + i // w) for i in range(N)]
                if all(q in g for q in cells) and nx.is_connected(g.subgraph(cells)):
                    yield cells


def estimate_error(circuit, g, cost, sq_err):
    """Very rough total error: gate errors + readout + idling."""
    err = 0.0
    for op in circuit.all_operations():
        if _is_2q(op):
            err += g[op.qubits[0]][op.qubits[1]]["err"]
        else:
            err += _rate(sq_err[op.qubits[0]])
    qubits = circuit.all_qubits()
    err += sum(cost[q] for q in qubits)
    err += IDLE_ERR * len(qubits) * len(circuit)
    return err


def best_routed_scs(N, k, g, patches, cost, sq_err, n_layouts, deadline, objective):
    """Route the SCS circuit onto several candidate layouts and keep the best.

    Candidates are the top greedy patches (RouteCQC picks the mapping) plus the
    cheapest zig-zag bands (mapping fixed). Returns (circuit, patch).
    """
    line = cirq.LineQubit.range(N)
    layouts = [(patch, None) for _, _, patch in patches[:3]]

    bands = []
    for cells in zigzag_layouts(g, N):
        errs = [d["err"] for *_, d in g.subgraph(cells).edges(data=True)]
        bands.append((sum(cost[q] for q in cells) + 1.5 * k * N * np.mean(errs), cells))
    bands.sort(key=lambda t: t[0])
    layouts += [(cells, dict(zip(line, cells))) for _, cells in bands[:n_layouts]]

    logical = cirq.optimize_for_target_gateset(scs_circuit(N, k), gateset=cirq.CZTargetGateset())
    best = None
    for patch, mapping in layouts:
        if best is not None and time.time() > deadline:
            break
        try:
            routed = route(logical, g, patch, mapping)
        except Exception:
            # RouteCQC sometimes gives up on small or oddly shaped patches
            continue
        routed = cirq.optimize_for_target_gateset(routed, gateset=cirq.CZTargetGateset())
        routed = cirq.drop_empty_moments(cirq.merge_single_qubit_gates_to_phxz(routed))
        if objective == "moments":
            score = len(cirq.stratified_circuit(routed, categories=[_is_2q, _is_1q]))
        else:
            score = estimate_error(routed, g, cost, sq_err)
        if best is None or score < best[0]:
            best = (score, routed, patch)

    if best is None:
        raise NotImplementedError("routing failed on every layout")
    return best[1], best[2]


# --- compiling for the device ----------------------------------------------------

X_PULSE = cirq.PhasedXZGate(x_exponent=1.0, z_exponent=0.0, axis_phase_exponent=0.0)


def add_echoes(circuit, min_idle=8):
    """Put an X-X echo pair into every idle stretch of at least `min_idle` moments.

    Pulses go at 1/4 and 3/4 of the gap. X·X = I, so the ideal state doesn't
    change. A qubit's idle time counts from its first gate to the end of the
    circuit. Pulses can land in CZ moments, which the device allows.
    """
    moments = [list(m.operations) for m in circuit]
    end = len(moments)
    busy = {}
    for t, moment in enumerate(circuit):
        for op in moment:
            for q in op.qubits:
                busy.setdefault(q, []).append(t)
    for q, times in busy.items():
        stops = times + [end]
        for a, b in zip(stops, stops[1:]):
            gap = b - a - 1
            if gap < min_idle:
                continue
            t1 = a + 1 + gap // 4
            t2 = a + 1 + (3 * gap) // 4
            if t1 != t2:
                moments[t1].append(X_PULSE.on(q))
                moments[t2].append(X_PULSE.on(q))
    return cirq.Circuit(cirq.Moment(ops) for ops in moments)


def _to_phxz(op, _=None):
    """Rewrite single-qubit gates as PhasedXZ and drop identities."""
    if _is_1q(op) and not isinstance(op.gate, cirq.PhasedXZGate):
        u = cirq.unitary(op)
        if np.allclose(u, np.eye(2) * u[0, 0]):
            return []
        return cirq.PhasedXZGate.from_matrix(u).on(*op.qubits)
    if _is_2q(op) and op.gate != cirq.CZ:
        raise ValueError(f"unexpected two-qubit gate {op}")
    return op


def compile_for_willow(circuit, dd="DEFAULT", align_right=True):
    """CZ + PhasedXZ only, CZ and single-qubit gates in separate layers.

    dd: "sparse" for our own echoes, None for no decoupling, or any schema
    name accepted by cirq.add_dynamical_decoupling.
    """
    c = cirq.optimize_for_target_gateset(circuit, gateset=cirq.CZTargetGateset())
    c = cirq.eject_phased_paulis(c)
    c = cirq.eject_z(c)
    c = cirq.merge_single_qubit_gates_to_phxz(c)
    c = cirq.drop_negligible_operations(c)
    c = cirq.drop_empty_moments(c)

    layers = [_is_2q, _is_1q]
    if align_right:
        # stratifying the reversed circuit packs every gate as late as it can go
        rev = cirq.stratified_circuit(cirq.Circuit(c.moments[::-1]), categories=layers)
        c = cirq.Circuit(rev.moments[::-1])
    else:
        c = cirq.stratified_circuit(c, categories=layers)
    c = cirq.drop_empty_moments(c)

    if dd == "sparse":
        c = add_echoes(c)
    elif dd:
        # cirq only pads idle time that ends in a gate, so add a throwaway
        # measurement on every qubit and strip it off again afterwards
        tmp = c + cirq.Moment(cirq.measure(*sorted(c.all_qubits()), key="tmp"))
        tmp = cirq.add_dynamical_decoupling(tmp, schema=dd, single_qubit_gate_moments_only=False)
        c = cirq.Circuit(tmp.moments[:-1])

    return cirq.map_operations_and_unroll(c, _to_phxz)


def flip_all(circuit, qubits):
    """Apply X to every qubit, merged into the last single-qubit layer if possible."""
    c = circuit + cirq.Moment(cirq.X(q) for q in qubits)
    c = cirq.merge_single_qubit_moments_to_phxz(c)
    return cirq.map_operations(c, _to_phxz)


# --- entry points ----------------------------------------------------------------

def create_dicke_state(num_qubits, num_excitations, cz_pauli_error_rate, sq_pauli_error_rate,
                       zero_errors, one_errors, *, dd_schema="sparse", n_candidates=6,
                       time_budget_s=12.0, objective="error"):
    """Challenge entry point. The keyword-only arguments are for our own experiments."""
    start = time.time()
    N, n = num_qubits, num_excitations
    if N < 1 or not 0 <= n <= N:
        raise NotImplementedError
    flip = n > N - n
    k = N - n if flip else n  # number of excitations we actually prepare
    cal = (cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors)
    g, patches = rank_patches(N, n, *cal)

    if k == 0:  # |0...0> or |1...1>
        patch = patches[0][2]
        gate = cirq.PhasedXZGate(x_exponent=1.0 if flip else 0.0, z_exponent=0, axis_phase_exponent=0)
        return cirq.Circuit(cirq.Moment(gate.on(q) for q in patch)), set(patch)

    cost = qubit_costs(g, N, n, sq_pauli_error_rate, zero_errors, one_errors)
    if k == 1:
        _, root, patch = patches[0]
        raw = cirq.Circuit(w_state_ops(g, root, patch))
    else:
        raw, patch = best_routed_scs(N, k, g, patches, cost, sq_pauli_error_rate,
                                     n_candidates, start + time_budget_s, objective)

    circuit = compile_for_willow(raw, dd=dd_schema)
    if flip:
        circuit = flip_all(circuit, patch)
    if len(circuit) > MAX_MOMENTS:
        raise NotImplementedError(f"{len(circuit)} moments > {MAX_MOMENTS}")
    return circuit, set(patch)


def _willow():
    # Willow105 is only in newer cirq_google; willow_pink is the same chip
    dev = getattr(cirq_google, "Willow105", None)
    return dev or cirq_google.engine.create_device_from_processor_id("willow_pink")


def create_dicke_state_adaptive(num_qubits, num_excitations):
    """Bonus question. No mid-circuit measurements yet: we reuse the standard
    circuit (the rules allow this), skip echoes since only depth is scored, and
    pick layouts by moment count. Every qubit gets the same made-up error rates.
    """
    dev = _willow()
    qubits = list(dev.metadata.qubit_set)
    pairs = [tuple(p) for p in dev.metadata.qubit_pairs]
    cz = {p: (2.5e-3, 0) for p in pairs}
    sq = {q: (4e-4, 0) for q in qubits}
    zero = {q: (5e-3, 0) for q in qubits}
    one = {q: (1e-2, 0) for q in qubits}
    return create_dicke_state(num_qubits, num_excitations, cz, sq, zero, one,
                              dd_schema=None, objective="moments")
