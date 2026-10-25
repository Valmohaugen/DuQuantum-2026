"""PORT016 frozen-selector evaluation on reserved confirmation seeds27..32."""
import hashlib
import json
import math
import time
from pathlib import Path

import cirq
import numpy as np

# Pin evaluator modules before importing shared wrappers.
import importlib.util
import sys
EVAL_DIR=Path(__file__).parent/'w_edge_eval_snapshot'
for _name in ('judge','test_dicke','fast_eval'):
    _spec=importlib.util.spec_from_file_location(_name,EVAL_DIR/f'{_name}.py')
    _module=importlib.util.module_from_spec(_spec)
    sys.modules[_name]=_module
    _spec.loader.exec_module(_module)
from .w_hardware_probe import fast_eval,judge,score_samples
from .w_edge_selection import select,baseline
from .w_heterogeneous_noise import probabilities as signed_probabilities
from .w_stress_noise import probabilities as stress_probabilities
MODELS=('nominal','coherent','zz','signed_zz')
def probabilities(c,qs,cal,seed,model):
    return (signed_probabilities if model=='signed_zz' else stress_probabilities)(c,qs,cal,seed,model)

ROOT=Path(__file__).parent


def main():
    rows,pairs,selections=[],[],[]
    for n in (8,10):
        for seed in (27,28,29,30,31,32):
            tick=time.monotonic()
            cal=judge.fake_calibration(seed)
            reference,rqs,candidate,cqs,selection=select(n,cal)
            assert selection['seconds']<60
            selections.append(dict(N=n,seed=seed,**selection))
            for c,qs in [(reference,rqs),(candidate,cqs)]:
                baseline.check_circuit(c,*cal[:2]);judge.get_device().validate_circuit(c)
                psi=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=sorted(qs)).final_state_vector
                goal=np.array([int(i.bit_count()==1) for i in range(2**n)])/math.sqrt(n)
                overlap=np.vdot(goal,psi)
                assert np.linalg.norm(psi-goal*overlap/abs(overlap))<1e-10
            for model in MODELS:
                cache,samples={},{}
                for name,c,qs in [('baseline',reference,rqs),('candidate',candidate,cqs)]:
                    key=c.freeze()
                    if key not in cache:
                        pz,px=probabilities(c,qs,cal,seed,model)
                        cache[key]=(pz,px,score_samples(pz,px,n,seed=310000+seed*10+n))
                    pz,px,sampled=cache[key];samples[name]=sampled
                    scores={}
                    for cutoff,v in sampled.items():
                        f,zf,zb,x,proxy=fast_eval.expected_score(pz,px,n,1,cutoff,10000)
                        scores[str(cutoff)]=dict(E_score=float(v.mean()),MC_standard_error=float(v.std(ddof=1)/math.sqrt(len(v))),valid_fraction=float(f),Z_floor=float(zf),Z_bias=float(zb),X_penalty=float(x),penalty_inverse_proxy=float(proxy))
                    rows.append(dict(N=n,seed=seed,model=model,variant=name,moments=len(c),scores=scores))
                for cutoff in (4,n):
                    delta=samples['candidate'][cutoff]-samples['baseline'][cutoff]
                    pairs.append(dict(N=n,seed=seed,model=model,cutoff=cutoff,mean_delta=float(delta.mean()),paired_MC_standard_error=float(delta.std(ddof=1)/math.sqrt(len(delta)))))
                report=dict(status='unchanged fixed4pattern selector on reserved confirmation seeds; maintained main unchanged',models=MODELS,baseline_sha256=hashlib.sha256((ROOT/'w_cost_snapshot.py').read_bytes()).hexdigest(),model_definition='nominal/coherent/uniform100kHz/signed100kHz stress models;4 shared detuning draws,10000shots and32768 score repetitions',rows=rows,paired_differences=pairs)
                (ROOT/'w_edge_confirmation_results.json').write_text(json.dumps(report,indent=2)+'\n')
                print(n,seed,model,'delta',pairs[-1]['mean_delta'],'elapsed',round(time.monotonic()-tick,2),flush=True)
            (ROOT/'w_edge_confirmation_selections.json').write_text(json.dumps(selections,indent=2)+'\n')


if __name__=='__main__':main()
