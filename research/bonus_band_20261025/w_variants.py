"""Exact single-excitation splitters with alternative native decompositions."""
import argparse
import collections
import json
import math
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np

from . import snapshot as b
from .probe import optimize
from .commuting_schedule import schedule

ROOT=Path(__file__).parent


def random_tree(adj,n,rng):
    roots=[q for q in adj if len(adj[q])==4]
    root=roots[int(rng.integers(len(roots)))];informed=[root];used={root};children=collections.defaultdict(list)
    while len(used)<n:
        fresh=[]
        for p in rng.permutation(len(informed)):
            parent=informed[p];available=[q for q in adj[parent] if q not in used]
            if not available:continue
            child=available[int(rng.integers(len(available)))];children[parent].append(child)
            used.add(child);fresh.append(child)
            if len(used)==n:break
        if not fresh:raise NotImplementedError
        informed+=fresh
    return root,children


def operations(root,children,kinds):
    children,_,size=b.broadcast_order(root,children)
    start={root:0};events=[];stack=[root]
    while stack:
        p=stack.pop()
        for i,c in enumerate(children[p]):
            events.append((start[p]+i,p,c));start[c]=start[p]+i+1;stack.append(c)
    events.sort();remaining=dict(size);ops=[]
    for i,(rnd,p,c) in enumerate(events):
        t=2*math.asin(math.sqrt(size[c]/remaining[p]));remaining[p]-=size[c]
        if i==0:
            ops += [cirq.ry(t).on(c),cirq.X(p),cirq.H(p),cirq.CZ(c,p),cirq.H(p)]
        elif kinds[i-1]:
            # Exactly the same action on |00>, |01> in the (child,parent)
            # order. A W state never occupies |11>, so either form is valid.
            ops += b.givens(c,p,t/2)
        else:
            ops += [cirq.ry(-t/2).on(c),cirq.CZ(p,c),cirq.ry(t/2).on(c),cirq.H(p),cirq.CZ(c,p),cirq.H(p)]
    return ops


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=180);args=parser.parse_args()
    if (ROOT/'combined_circuits.json').exists():
        circuits=cirq.read_json(ROOT/'combined_circuits.json')
    else:
        from . import native_submission
        circuits={f'{n},{k}':native_submission.create_dicke_state_adaptive(n,k)[0]
                  for n in range(2,16) for k in range(1,n//2+1)}
    dev=cirq_google.Willow105.metadata
    adj={q:{} for q in dev.qubit_set}
    for a,c in dev.qubit_pairs:adj[a][c]=adj[c][a]=1e-3
    node={q:1e-3 for q in adj};rng=np.random.default_rng(2026102517)
    baseline={n:len(circuits[f'{n},1']) for n in range(5,16)}
    records=[];start=time.monotonic();trials=0;round_no=0
    while time.monotonic()-start<args.seconds:
        for n in range(5,16):
            if time.monotonic()-start>=args.seconds:break
            if round_no==0:root,children=b.best_tree(adj,node,n,float('inf'),fast=True)
            else:root,children=random_tree(adj,n,rng)
            patterns=[np.zeros(n-2,dtype=bool),np.ones(n-2,dtype=bool),rng.random(n-2)<.5]
            for kinds in patterns:
                if time.monotonic()-start>=args.seconds:break
                c=b.compile_circuit(operations(root,children,kinds),dynamical_decoupling=False,pack=True);trials+=1
                if len(c)>len(circuits[f'{n},1'])+4:continue
                c=optimize(c)
                if len(c)>=len(circuits[f'{n},1']):continue
                c=schedule(c,restarts=6);qs=sorted(c.all_qubits())
                assert len(qs)==n;cirq_google.Willow105.validate_circuit(c)
                state=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=qs).final_state_vector
                target=np.array([int(i.bit_count()==1) for i in range(2**n)])/math.sqrt(n)
                overlap=np.vdot(target,state);error=float(np.linalg.norm(state-target*overlap/abs(overlap)))
                assert error<1e-10,error
                circuits[f'{n},1']=c
                row=dict(N=n,k=1,before=baseline[n],depth=len(c),state_l2_error=error,trials=trials,round=round_no,seconds=time.monotonic()-start)
                records.append(row);print(row,flush=True)
                cirq.to_json(circuits,ROOT/'w_circuits.json')
            score=sum(int(key.split(',')[0])*int(key.split(',')[1])/len(c) for key,c in circuits.items())
            (ROOT/'w_results.json').write_text(json.dumps(dict(cases=len(circuits),score=score,trials=trials,seconds=time.monotonic()-start,improvements=records),indent=2))
        round_no+=1
    cirq.to_json(circuits,ROOT/'w_circuits.json');print('COMPLETE',score,trials,flush=True)


if __name__=='__main__':main()
