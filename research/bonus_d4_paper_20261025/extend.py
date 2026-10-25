"""Bounded longer affine mappings; CNOT count need not minimize native depth."""
from collections import deque
import hashlib
import itertools
import json
import math
import time

import cirq
import cirq_google
import numpy as np
from .search import ROOT, transform, prefix, native


def main():
    initial = json.loads((ROOT/'search_results.json').read_text())
    incumbent = cirq.read_json(ROOT/'best_native.json')
    # Recover the cyclic order used by the frozen initial search.
    a = min(incumbent.all_qubits())
    qs = [a,a+(0,1),a+(1,1),a+(1,0)]
    graph = [(0,1),(1,2),(2,3),(3,0)]
    directed = graph+[(b,a) for a,b in graph]
    goal = tuple(x for x in range(16) if x.bit_count()==2)
    goals = {}
    for flip in range(16):
        goals.setdefault(tuple(sorted(x^flip for x in goal)),[]).append(flip)
    distance = {s:0 for s in goals}
    queue = deque(goals)
    while queue:
        state = queue.popleft()
        for edge in directed:
            child = transform(state,*edge)
            if child not in distance:
                distance[child] = distance[state]+1
                queue.append(child)
    target = np.array([int(x.bit_count()==2) for x in range(16)])/math.sqrt(6)
    simulator = cirq.Simulator(dtype=np.complex128)
    device = cirq_google.Willow105
    best = dict(initial['best'])
    best.update(origin='shortest affine search')
    cirq.to_json(incumbent,ROOT/'extended_best_native.json')
    start = time.monotonic()
    rows,coverage,seen = [],[],set()

    def walks(state,remaining,sequence=()):
        if time.monotonic()-start>45:
            raise TimeoutError()
        if distance.get(state,100)>remaining:
            return
        if remaining==0:
            if state in goals:
                yield sequence,goals[state]
            return
        for edge in directed:
            if sequence and edge==sequence[-1]:
                continue # Consecutive identical CNOTs cancel exactly.
            yield from walks(transform(state,*edge),remaining-1,sequence+(edge,))

    expired = False
    for length,plus in itertools.product((5,6),(2,3)):
        item=dict(length=length,plus=plus,complete=False,paths=0,evaluated=0,duplicates=0)
        coverage.append(item)
        support=tuple(sorted((c<<3)|(t<<2)|(b<<(3-plus))
                             for c,t,b in itertools.product((0,1),repeat=3) if not(c and t)))
        try:
            for sequence,flips in walks(support,length):
                item['paths']+=1
                for flip in flips:
                    ops=prefix(qs,0,1,plus)
                    ops += [cirq.CNOT(qs[c],qs[t]) for c,t in sequence]
                    ops += [cirq.X(qs[j]) for j in range(4) if flip & (1<<(3-j))]
                    circuit=native(ops)
                    frozen=circuit.freeze()
                    if frozen in seen:
                        item['duplicates']+=1
                        continue
                    seen.add(frozen)
                    device.validate_circuit(circuit)
                    state=simulator.simulate(circuit,qubit_order=qs).final_state_vector
                    overlap=np.vdot(target,state)
                    error=float(np.linalg.norm(state-target*overlap/abs(overlap)))
                    assert error<1e-10
                    row=dict(length=length,plus=plus,sequence=sequence,flip=flip,
                             moments=len(circuit),CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),
                             state_error=error)
                    rows.append(row);item['evaluated']+=1
                    if (row['moments'],row['CZ'])<(best['moments'],best['CZ']):
                        best=row
                        cirq.to_json(circuit,ROOT/'extended_best_native.json')
                        print('BEST',row,flush=True)
            item['complete']=True
        except TimeoutError:
            expired=True
            break
    report=dict(status='bounded longer affine search complete',best=best,coverage=coverage,
                rows=rows,seconds=time.monotonic()-start,expired=expired,
                baseline_moments=9,baseline_CZ=7,
                planned_groups=[dict(length=l,plus=p) for l,p in itertools.product((5,6),(2,3))],
                scope='Only5/6CNOT suffixes on a square, both final complementary X frames; exact inverse-distance pruning and adjacent identical CNOT cancellation. No claim about other graphs or general quantum circuits.')
    (ROOT/'extended_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',len(rows),report['seconds'],expired,flush=True)


if __name__=='__main__':
    main()
