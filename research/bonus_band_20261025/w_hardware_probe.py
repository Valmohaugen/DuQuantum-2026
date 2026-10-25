"""PORT-004: paired native W decompositions on identical calibrated tree choices."""
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import cirq
import numpy as np

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT.resolve().parents[1]/'ryon'))
import fast_eval
import judge

from . import w_hardware_snapshot as baseline
from .w_broadcast import operations


def score_samples(pz,px,n,seed,replicates=32768,shots=10000):
    """Exact sufficient statistics for the finite-shot score, for k=1."""
    weight=np.array([i.bit_count() for i in range(2**n)])
    valid=pz[weight==1]
    zprob=np.r_[valid,max(0.,1-valid.sum())];zprob/=zprob.sum()
    pxw=np.bincount(weight,weights=px,minlength=n+1);pxw/=pxw.sum()
    comb=lambda a,b:math.comb(a,b) if 0<=b<=a else 0
    table=np.array([[sum((-1)**j*comb(w,j)*comb(n-w,r-j) for j in range(r+1))/comb(n,r)
                     for w in range(n+1)] for r in range(1,n+1)])
    expected=np.array([comb(r,r//2)*comb(n-r,1-r//2)/n if r%2==0 else 0. for r in range(1,n+1)])
    rng=np.random.default_rng(seed);counts=rng.multinomial(shots,zprob,size=replicates)[:,:-1]
    fraction=counts.sum(axis=1)/shots;mean=shots*fraction[:,None]/n
    zpen=((counts-mean)**2/mean).sum(axis=1)/n/fraction
    xcounts=rng.multinomial(shots,pxw,size=replicates);averages=xcounts@table.T/shots
    xterms=(averages-expected)**2/np.where(expected==0,1.,expected**2)
    return {cutoff:1/(zpen+xterms[:,:cutoff].sum(axis=1)) for cutoff in (4,n)}


def main():
    records=[];pairs=[];source=hashlib.sha256((ROOT/'w_hardware_snapshot.py').read_bytes()).hexdigest()
    for n in (8,10):
        for seed in range(3):
            cal=judge.fake_calibration(seed);sampled={};placements={}
            for name in ('baseline','givens'):
                original=baseline.w_ops
                if name=='givens':baseline.w_ops=lambda root,children:operations(root,children,[True]*(n-2))
                tick=time.monotonic()
                try:c,qs=baseline.create_dicke_state(n,1,*cal)
                finally:baseline.w_ops=original
                build=time.monotonic()-tick;assert build<60
                baseline.check_circuit(c,cal[0],cal[1]);placements[name]=qs
                state=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=sorted(qs)).final_state_vector
                target=np.array([int(i.bit_count()==1) for i in range(2**n)])/math.sqrt(n)
                overlap=np.vdot(target,state);error=float(np.linalg.norm(state-target*overlap/abs(overlap)));assert error<1e-10
                pz,px=fast_eval.noisy_probs(c,qs,cal,np.random.default_rng([seed,n,1]),realisations=2)
                samples=score_samples(pz,px,n,seed=9000+n*10+seed);sampled[name]=samples
                row=dict(N=n,k=1,seed=seed,variant=name,moments=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),single_qubit_gates=sum(len(op.qubits)==1 for op in c.all_operations()),build_seconds=build,state_l2_error=error,scores={})
                for cutoff,values in samples.items():
                    assert np.isfinite(values).all()
                    *_,proxy=fast_eval.expected_score(pz,px,n,1,cutoff,10000)
                    row['scores'][str(cutoff)]=dict(E_score=float(values.mean()),MC_standard_error=float(values.std(ddof=1)/math.sqrt(len(values))),replicates=len(values),penalty_inverse_proxy=float(proxy))
                records.append(row);print(row,flush=True)
            assert placements['baseline']==placements['givens']
            for cutoff in (4,n):
                delta=sampled['givens'][cutoff]-sampled['baseline'][cutoff]
                pairs.append(dict(N=n,k=1,seed=seed,cutoff=cutoff,mean_delta=float(delta.mean()),paired_MC_standard_error=float(delta.std(ddof=1)/math.sqrt(len(delta)))))
            (ROOT/'w_hardware_results.json').write_text(json.dumps(dict(status='paired synthetic-calibration pilot; no maintained solver changes',source_sha256=source,model='2 detuning realizations, 10000 independent shots per basis; 32768 score Monte Carlo repetitions; identical calibrated qubit sets',rows=records,paired_differences=pairs),indent=2))
    print('PAIRED',pairs,flush=True)


if __name__=='__main__':main()
