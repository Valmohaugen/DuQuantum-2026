"""Exact support search for affine equivalents of the paper's D(4,2) circuit."""
from collections import deque
import hashlib
import itertools
import json
import math
from pathlib import Path
import time

import cirq
import cirq_google
import numpy as np
from .commuting_schedule import schedule

ROOT = Path(__file__).parent


def transform(support, control, target):
    return tuple(sorted(x ^ ((1 << (3-target)) if x & (1 << (3-control)) else 0)
                        for x in support))


def shortest_sequences(start, edges):
    goal = tuple(x for x in range(16) if x.bit_count() == 2)
    goals = {}
    for flip in range(16):
        goals.setdefault(tuple(sorted(x ^ flip for x in goal)), []).append(flip)
    distances, parents = {start: 0}, {start: []}
    queue = deque([start])
    found, depth = [], None
    while queue:
        state = queue.popleft()
        if depth is not None and distances[state] > depth:
            break
        if state in goals:
            depth = distances[state]
            found.append(state)
            continue
        for edge in edges:
            child = transform(state, *edge)
            distance = distances[state]+1
            if child not in distances:
                distances[child] = distance
                parents[child] = []
                queue.append(child)
            if distances[child] == distance:
                parents[child].append((state, edge))

    def paths(state):
        if state == start:
            yield []
        else:
            for parent, edge in parents[state]:
                for sequence in paths(parent):
                    yield sequence+[edge]

    sequences = [(seq, flip) for state in found for seq in paths(state) for flip in goals[state]]
    return sequences, dict(minimum_affine_CNOT=depth, visited_supports=len(distances),
                          shortest_sequences=len(sequences))


def prefix(qs, control, target, plus):
    return [cirq.ry(math.pi/4)(qs[target]), cirq.ry(math.pi/2)(qs[plus]),
            cirq.ry(2*math.asin(1/math.sqrt(3)))(qs[control]),
            cirq.CNOT(qs[control], qs[target]), cirq.ry(math.pi/4)(qs[target]),
            cirq.CNOT(qs[control], qs[target])]


def native(operations):
    rewritten = []
    for op in operations:
        if op.gate == cirq.CNOT:
            c, t = op.qubits
            rewritten += [cirq.ry(-math.pi/2)(t), cirq.CZ(c, t), cirq.ry(math.pi/2)(t)]
        else:
            rewritten.append(op)
    def single(op):
        return cirq.PhasedXZGate.from_matrix(cirq.unitary(op)).on(op.qubits[0])
    fused = cirq.Circuit(cirq.merge_k_qubit_unitaries(cirq.Circuit(rewritten), k=1,
                                                   rewriter=single).all_operations())
    return schedule(fused, restarts=3)


def main():
    start_time = time.monotonic()
    device = cirq_google.Willow105
    vertices = set(device.metadata.qubit_set)
    edges = {frozenset(e) for e in device.metadata.qubit_pairs}
    for q in sorted(vertices):
        qs = [q, q+ (0, 1), q+(1, 1), q+(1, 0)]
        if all(x in vertices for x in qs) and all(frozenset((qs[a], qs[b])) in edges
                                                 for a, b in [(0,1),(1,2),(2,3),(3,0)]):
            break
    else:
        raise AssertionError('No device square')
    graph = [(0,1),(1,2),(2,3),(3,0)]
    directed = graph+[(b,a) for a,b in graph]
    target = np.array([int(x.bit_count()==2) for x in range(16)])/math.sqrt(6)
    simulator = cirq.Simulator(dtype=np.complex128)
    rows, coverage = [], []
    best = None
    # Square automorphisms fix the first directed edge; two positions for the
    # independent plus qubit exhaust the remaining distinct placements.
    for plus in (2,3):
        control, rotated = 0,1
        support = tuple(sorted((c<<3)|(t<<2)|(b<<(3-plus))
                               for c,t,b in itertools.product((0,1),repeat=3) if not(c and t)))
        sequences, info = shortest_sequences(support, directed)
        info.update(plus=plus, completed=0)
        coverage.append(info)
        for seq, flip in sequences:
            if time.monotonic()-start_time > 45:
                break
            ops = prefix(qs,control,rotated,plus)
            ops += [cirq.CNOT(qs[c],qs[t]) for c,t in seq]
            ops += [cirq.X(qs[j]) for j in range(4) if flip & (1<<(3-j))]
            circuit = native(ops)
            device.validate_circuit(circuit)
            state = simulator.simulate(circuit,qubit_order=qs).final_state_vector
            overlap = np.vdot(target,state)
            error = float(np.linalg.norm(state-target*overlap/abs(overlap)))
            assert error < 1e-10
            row = dict(plus=plus,sequence=seq,final_flip=flip,moments=len(circuit),
                       CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),state_error=error)
            rows.append(row)
            info['completed'] += 1
            if best is None or (row['moments'],row['CZ']) < (best['moments'],best['CZ']):
                best = row
                cirq.to_json(circuit,ROOT/'best_native.json')
                print('BEST',row,flush=True)
        info['complete'] = info['completed']==len(sequences)
    report = dict(status='bounded affine-equivalent square search complete',baseline_moments=9,
                  baseline_CZ=7,best=best,coverage=coverage,rows=rows,
                  seconds=time.monotonic()-start_time,
                  scope='Shortest CNOT support mappings on one square, both distinct initial placements; final X flips are free only in graph search and counted by native compilation. No lower bound on arbitrary native circuits, other footprints, non-shortest mappings, or alternative state-preparation prefixes.')
    (ROOT/'search_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',len(rows),report['seconds'],flush=True)


if __name__ == '__main__':
    main()
