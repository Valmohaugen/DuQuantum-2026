"""Native-moment scheduling with unordered commuting CZs on each wire."""

import cirq
import networkx as nx
import numpy as np


def schedule(circuit, restarts=12):
    operations = list(circuit.all_operations())
    count = len(operations)
    successors = [set() for _ in operations]
    predecessors = [set() for _ in operations]
    wires = {}
    diagonal = []
    for op in operations:
        if op.gate == cirq.CZ:
            diagonal.append(True)
        else:
            u = cirq.unitary(op)
            diagonal.append(bool(np.max(np.abs(u - np.diag(np.diag(u)))) < 1e-13))
    for i, op in enumerate(operations):
        for q in op.qubits:
            for j in wires.get(q, []):
                if diagonal[i] and diagonal[j]:
                    continue
                predecessors[i].add(j)
                successors[j].add(i)
            wires.setdefault(q, []).append(i)
    height = [1] * count
    for i in reversed(range(count)):
        height[i] = 1 + max((height[j] for j in successors[i]), default=0)
    qubits = sorted(circuit.all_qubits())
    index = {q: i for i, q in enumerate(qubits)}
    best = circuit
    rng = np.random.default_rng(20261025)
    for restart in range(restarts):
        remaining = [len(p) for p in predecessors]
        ready = {i for i, d in enumerate(remaining) if d == 0}
        result = []
        power = [1.0, 2.0, 4.0][restart % 3]
        jitter = 0 if restart < 3 else 0.2
        done = 0
        while ready:
            graph = nx.Graph()
            for i in sorted(ready):
                op = operations[i]
                a = index[op.qubits[0]]
                d = index[op.qubits[1]] if len(op.qubits) == 2 else len(qubits) + a
                value = (height[i] ** power) * (1 + jitter * rng.random())
                if not graph.has_edge(a, d) or graph[a][d]["weight"] < value:
                    graph.add_edge(a, d, weight=value, operation=i)
            matching = nx.max_weight_matching(graph)
            selected = [graph[a][d]["operation"] for a, d in matching]
            assert selected
            result.append(cirq.Moment(operations[i] for i in selected))
            done += len(selected)
            ready.difference_update(selected)
            for i in selected:
                for j in successors[i]:
                    remaining[j] -= 1
                    if remaining[j] == 0:
                        ready.add(j)
        assert done == count
        if len(result) < len(best):
            best = cirq.Circuit(result)
    return best
