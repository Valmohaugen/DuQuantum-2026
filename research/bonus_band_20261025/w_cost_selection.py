"""Choose exact W edge decompositions by calibrated costs on one fixed tree."""
import copy
import time

import numpy as np

from . import w_cost_snapshot as baseline
from .w_broadcast import operations
from .w_state_cost import infidelity_cost,rate,T1,T2,DUR_1Q,DUR_CZ


def gate_count_cost(circuit,cal):
    edges={frozenset(edge):rate(value) for edge,value in cal[0].items()}
    value=sum(edges[frozenset(op.qubits)] if len(op.qubits)==2 else rate(cal[1][op.qubits[0]]) for op in circuit.all_operations())
    duration=sum(DUR_CZ if any(len(op.qubits)==2 for op in moment) else DUR_1Q for moment in circuit)
    tphi=1/(1/T2-1/(2*T1));n=len(circuit.all_qubits())
    return value+n*duration*(1/(2*T1)+1/(2*tphi))


def select(n,cal,max_patterns=48):
    if not 2 <= n <= 12:
        raise ValueError('Experimental selector is limited to 2<=N<=12; use the baseline outside this pilot domain')
    tick=time.monotonic();captured={};original=baseline.w_ops
    def capture(root,children):
        captured.update(root=root,children=copy.deepcopy(children))
        return original(root,children)
    baseline.w_ops=capture
    try:reference,qs=baseline.create_dicke_state(n,1,*cal)
    finally:baseline.w_ops=original
    patterns=[(False,)*(n-2),(True,)*(n-2)]
    patterns += [tuple(i==j for i in range(n-2)) for j in range(n-2)]
    patterns += [tuple(i!=j for i in range(n-2)) for j in range(n-2)]
    patterns=list(dict.fromkeys(patterns));rng=np.random.default_rng(73000+n)
    limit=min(max_patterns,2**(n-2))
    while len(patterns)<limit:
        pattern=tuple(rng.random(n-2)<.5)
        if pattern not in patterns:patterns.append(pattern)
    candidates=[('baseline',reference)]
    for pattern in patterns:
        if time.monotonic()-tick>20:break
        c=baseline.compile_circuit(operations(captured['root'],copy.deepcopy(captured['children']),pattern),dynamical_decoupling=True,pack=False)
        candidates.append((''.join(str(int(v)) for v in pattern),c))
    scores=[]
    for name,c in candidates:
        if scores and time.monotonic()-tick>25:break
        value,parts=infidelity_cost(c,cal,True)
        scores.append(dict(pattern=name,state_cost=value,state_terms=parts,count_cost=gate_count_cost(c,cal),moments=len(c)))
    selected={}
    for method,key in [('count','count_cost'),('state','state_cost')]:
        i=min(range(len(scores)),key=lambda j:scores[j][key])
        if scores[i][key]>=scores[0][key]-1e-8:i=0
        selected[method]=(candidates[i][1],scores[i])
    seconds=time.monotonic()-tick
    assert seconds<60,(n,seconds)
    return reference,qs,selected,dict(seconds=seconds,patterns=len(scores),pool=scores)
