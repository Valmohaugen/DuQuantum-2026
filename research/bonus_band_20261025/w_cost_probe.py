"""PORT-004 cost-based selection pilot, including unseen calibration seeds."""
import hashlib
import json
import math
import time
from pathlib import Path

import cirq
import numpy as np

from .w_hardware_probe import fast_eval,judge,score_samples
from .w_cost_selection import select,baseline

ROOT=Path(__file__).parent


def main():
    records=[];pairs=[];pools=[]
    for n in (8,10):
        for seed in range(6):
            cal=judge.fake_calibration(seed);tick=time.monotonic();reference,qs,choices,pool=select(n,cal)
            pool.update(N=n,seed=seed);pools.append(pool)
            candidates={'baseline':reference,**{name:row[0] for name,row in choices.items()}}
            cache={};samples={}
            for name,c in candidates.items():
                baseline.check_circuit(c,cal[0],cal[1])
                psi=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=sorted(qs)).final_state_vector
                target=np.array([int(i.bit_count()==1) for i in range(2**n)])/math.sqrt(n)
                overlap=np.vdot(target,psi);error=float(np.linalg.norm(psi-target*overlap/abs(overlap)));assert error<1e-10
                key=cirq.FrozenCircuit(c)
                if key not in cache:
                    pz,px=fast_eval.noisy_probs(c,qs,cal,np.random.default_rng([seed,n,1]),realisations=4)
                    sampled=score_samples(pz,px,n,seed=100000+n*10+seed)
                    cache[key]=(pz,px,sampled)
                pz,px,sampled=cache[key];samples[name]=sampled
                row=dict(N=n,k=1,seed=seed,held_out=seed>=3,variant=name,moments=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),single_qubit_gates=sum(len(op.qubits)==1 for op in c.all_operations()),state_l2_error=error,selection=choices[name][1] if name!='baseline' else pool['pool'][0],scores={})
                for cutoff,values in sampled.items():
                    *_,proxy=fast_eval.expected_score(pz,px,n,1,cutoff,10000)
                    row['scores'][str(cutoff)]=dict(E_score=float(values.mean()),MC_standard_error=float(values.std(ddof=1)/math.sqrt(len(values))),penalty_inverse_proxy=float(proxy))
                records.append(row)
                print(n,seed,name,len(c),row['selection']['pattern'],row['scores'][str(n)]['E_score'],flush=True)
            for name in ('count','state'):
                for cutoff in (4,n):
                    difference=samples[name][cutoff]-samples['baseline'][cutoff]
                    pairs.append(dict(N=n,seed=seed,held_out=seed>=3,variant=name,cutoff=cutoff,mean_delta=float(difference.mean()),paired_MC_standard_error=float(difference.std(ddof=1)/math.sqrt(len(difference)))))
            report=dict(status='experimental; no maintained constructor changes',baseline_sha256=hashlib.sha256((ROOT/'w_cost_snapshot.py').read_bytes()).hexdigest(),model='Four matched detuning realizations, 10000 shots per basis, 32768 score repetitions. Selection uses only calibration and first-order or gate-count costs, not noisy evaluation.',rows=records,paired_differences=pairs)
            (ROOT/'w_cost_results.json').write_text(json.dumps(report,indent=2));(ROOT/'w_cost_pools.json').write_text(json.dumps(pools,indent=2))
            print('CASE_SECONDS',round(time.monotonic()-tick,3),'BUILD',round(pool['seconds'],3),flush=True)


if __name__=='__main__':main()
