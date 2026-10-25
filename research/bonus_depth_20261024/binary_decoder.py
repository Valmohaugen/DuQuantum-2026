"""Depth-first offline synthesis of compressed Schmidt-label decoders."""
import argparse
import json
import math
import time
from pathlib import Path

import cirq
import numpy as np

from ryon import synth
from research.bonus_depth_20261024 import native_fit as fit
from research.bonus_depth_20261024 import latest_20261025 as b
from research.bonus_depth_20261024.clean_cliffords import clean
from research.bonus_depth_20261024.probe import optimize


def cells_for(n):
    width = (n+1)//2
    # Last label bits occupy a contiguous boundary edge of the patch.
    return [(0,j) for j in range(n-width)] + [(1,j) for j in range(width)]


def target(n,k,offset=0):
    inputs = np.eye(2**n)[offset:offset+k+1]
    return inputs,np.array([synth.dicke(n,r) for r in range(k+1)])


def compiled(n,edges,theta):
    qs=cirq.LineQubit.range(n)
    return optimize(b.compile_circuit(b.patch_ops(qs,edges,theta),dynamical_decoupling=False,pack=True))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--n',type=int,default=5)
    p.add_argument('--k',type=int,default=3)
    p.add_argument('--offset',type=int,default=0)
    p.add_argument('--layers',type=int,default=24)
    p.add_argument('--restarts',type=int,default=16)
    p.add_argument('--seconds',type=float,default=180)
    args=p.parse_args();n,k=args.n,args.k
    cells=cells_for(n)
    groups=[]
    for direction,parity in [(1,0),(1,1),(0,0)]:
        group=[]
        for i,(r,c) in enumerate(cells):
            for j,(s,d) in enumerate(cells[:i]):
                if direction==1 and r==s and c==d+1 and d%2==parity:
                    group.append((j,i))
                elif direction==0 and c==d and r==s+1:
                    group.append((j,i))
        if group:groups.append(group)
    edges=[e for layer in range(args.layers) for e in groups[layer%len(groups)]]
    goal=target(n,k,args.offset)
    rng=np.random.default_rng(20261025+100*n+k+args.layers)
    start=time.monotonic();best=2.;theta=None
    dest=Path(__file__).with_name(f'binary_{n}_{k}_{args.offset}_{args.layers}.json')
    def save(loss,th):
        state=synth.run(n,edges,th[None],inputs=goal[0])[0]
        sign=np.sign(np.vdot(goal[1],state))
        error=float(np.max(np.linalg.norm(state-sign*goal[1],axis=1)))
        c=compiled(n,edges,th)
        row=dict(n=n,k=k,offset=args.offset,cells=cells,edges=edges,angles=th.tolist(),zset=[],
                 infidelity=loss,max_column_error=error,depth=len(c),CZ=len(edges),seconds=time.monotonic()-start)
        dest.write_text(json.dumps(row,indent=2))
        print({a:v for a,v in row.items() if a not in ('angles','edges','cells')},flush=True)
    for restart in range(args.restarts):
        if time.monotonic()-start>args.seconds:break
        x=rng.uniform(-np.pi,np.pi,n+2*len(edges))
        loss,x=fit.polish(n,edges,x,goal,maxiter=5000)
        if loss<best:
            best=loss;theta=x;save(loss,x)
        if best<1e-13:break
    if best>1e-13:return
    # Fixed exact Clifford values expose actual emitted depth during pruning.
    cleaned=clean(n,edges,theta,goal)
    if cleaned['max_column_error']<1e-10:
        theta=np.array(cleaned['angles']);save(0.,theta)
    while time.monotonic()-start<args.seconds:
        improved=False
        # Permit intermediate depth increases: only the best artifact is kept.
        for j in rng.permutation(len(edges)):
            if time.monotonic()-start>args.seconds:break
            trial=edges[:j]+edges[j+1:]
            initial=np.r_[theta[:n+2*j],theta[n+2*j+2:]]
            for perturbation in [0.,.3]:
                x=initial+rng.normal(scale=perturbation,size=len(initial))
                loss,x=fit.polish(n,trial,x,goal,maxiter=2000)
                if loss<1e-13:
                    edges,theta=trial,x;improved=True;save(loss,x);break
            if improved:break
        if not improved:break
    # Refine amplitudes, with no Clifford fixing if that overconstrains a fit.
    cleaned=clean(n,edges,theta,goal)
    if cleaned['max_column_error']>1e-10:
        cleaned=clean(n,edges,theta,goal,threshold=0.)
    if cleaned['max_column_error']<1e-10:
        theta=np.array(cleaned['angles']);save(0.,theta)


if __name__=='__main__':main()
