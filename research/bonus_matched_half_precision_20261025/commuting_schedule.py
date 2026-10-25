"""Native-moment scheduling with unordered commuting CZs on each wire."""
import heapq

import cirq
import networkx as nx
import numpy as np


def schedule(circuit,restarts=12):
    operations=list(circuit.all_operations());count=len(operations)
    successors=[set() for _ in operations];predecessors=[set() for _ in operations]
    wires={}
    diagonal=[]
    for op in operations:
        if op.gate==cirq.CZ:diagonal.append(True)
        else:
            u=cirq.unitary(op)
            diagonal.append(bool(np.max(np.abs(u-np.diag(np.diag(u))))<1e-13))
    for i,op in enumerate(operations):
        for q in op.qubits:
            for j in wires.get(q,[]):
                if diagonal[i] and diagonal[j]:continue
                predecessors[i].add(j);successors[j].add(i)
            wires.setdefault(q,[]).append(i)
    height=[1]*count
    for i in reversed(range(count)):
        height[i]=1+max((height[j] for j in successors[i]),default=0)
    qubits=sorted(circuit.all_qubits());index={q:i for i,q in enumerate(qubits)}
    best=circuit;rng=np.random.default_rng(20261025)
    for restart in range(restarts):
        remaining=[len(p) for p in predecessors]
        ready={i for i,d in enumerate(remaining) if d==0}
        result=[];power=[1.,2.,4.][restart%3]
        jitter=0 if restart<3 else .2
        done=0
        while ready:
            graph=nx.Graph()
            for i in sorted(ready):
                op=operations[i];a=index[op.qubits[0]]
                d=index[op.qubits[1]] if len(op.qubits)==2 else len(qubits)+a
                value=(height[i]**power)*(1+jitter*rng.random())
                if not graph.has_edge(a,d) or graph[a][d]['weight']<value:
                    graph.add_edge(a,d,weight=value,operation=i)
            matching=nx.max_weight_matching(graph)
            selected=[graph[a][d]['operation'] for a,d in matching]
            assert selected
            result.append(cirq.Moment(operations[i] for i in selected));done+=len(selected)
            ready.difference_update(selected)
            for i in selected:
                for j in successors[i]:
                    remaining[j]-=1
                    if remaining[j]==0:ready.add(j)
        assert done==count
        if len(result)<len(best):best=cirq.Circuit(result)
    return best


if __name__=='__main__':
    from research.bonus_terminal_integration_20261025 import cleaned_candidate as b
    import json,time
    from pathlib import Path
    records=[]
    for n,k in [(8,4),(10,5),(12,6),(15,7)]:
        c,qs=b.create_dicke_state_adaptive(n,k)
        start=time.monotonic();d=schedule(c,restarts=30)
        a=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=sorted(qs)).final_state_vector
        z=cirq.Simulator(dtype=np.complex128).simulate(d,qubit_order=sorted(qs)).final_state_vector
        error=float(np.linalg.norm(a-z));assert error<1e-10
        row=dict(n=n,k=k,before=len(c),after=len(d),seconds=time.monotonic()-start,state_error=error)
        records.append(row);print(row,flush=True)
    Path(__file__).with_name('commuting_schedule_checks.json').write_text(json.dumps(records,indent=2))
