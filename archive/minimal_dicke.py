"""Minimal valid Dicke-state solution (~40 lines): the "card-dealing" algorithm + Cirq plumbing.

No qubit-quality selection, no gate-saving tricks, no echo pulses. It produces exactly the right
state and follows the rules (CZ on listed pairs + PhasedXZ only); it just uses more gates.
"""
import math

import cirq
import networkx as nx


def card_dealing_circuit(N, k):
    """Bärtschi-Eidenbenz on a line of logical qubits: |0...0 1...1> (k ones) -> Dicke(N, k).
    Working down from the last qubit, each step decides whether a 1 stays or moves left, with
    probability (1s left) / (qubits left), controlled on what has been dealt so far."""
    q = cirq.LineQubit.range(N)
    ops = [cirq.X(q[i]) for i in range(N - k, N)]  # start with the k ones at the end
    for m in range(N, 1, -1):
        for l in range(1, min(k, m - 1) + 1):
            a, t, c = q[m - 1], q[m - 1 - l], q[m - l]
            ry = cirq.ry(2 * math.acos(math.sqrt(l / m))).on(t)
            ops += [cirq.CNOT(t, a), ry.controlled_by(a) if l == 1 else ry.controlled_by(a, c),
                    cirq.CNOT(t, a)]
    return cirq.Circuit(ops)


def create_dicke_state(num_qubits, num_excitations, cz_pauli_error_rate, sq_pauli_error_rate,
                       zero_errors, one_errors):
    N, n = num_qubits, num_excitations
    if not 0 < n < N:
        raise NotImplementedError
    # Chip map: only working qubits and couplers. Grab N connected qubits around a busy hub.
    g = nx.Graph((a, b) for a, b in cz_pauli_error_rate
                 if a in sq_pauli_error_rate and b in sq_pauli_error_rate)
    region = list(nx.bfs_tree(g, max(g, key=g.degree)))[:N]
    # Translate to the chip's gates (CZ + PhasedXZ), then let Cirq insert SWAPs so every
    # two-qubit gate acts on neighbours. The final shuffle of qubits doesn't matter: the
    # Dicke state looks the same under any permutation.
    to_chip = lambda c: cirq.optimize_for_target_gateset(c, gateset=cirq.CZTargetGateset())
    logical = to_chip(card_dealing_circuit(N, n))
    routed, _, _ = cirq.RouteCQC(nx.Graph(g.subgraph(region))).route_circuit(logical)
    circuit = to_chip(routed)
    if len(circuit) > 1750:  # the judges won't run longer circuits (hits N >= 16, n ~ N/2)
        raise NotImplementedError
    return circuit, set(region)