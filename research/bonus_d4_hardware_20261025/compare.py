"""Frozen D4k2 hardware pilot; execute only after CPU release."""
import hashlib
import json
import math
import time
from pathlib import Path
import cirq
import numpy as np
from . import baseline,judge,test_dicke,fast_eval,score,stress_noise,signed_noise

ROOT=Path(__file__).parent
SEEDS=tuple(range(41,47))
MODELS=('nominal','coherent','zz','signed_zz')


def select(cal):
    tick=time.monotonic()
    reference,rqs=baseline.create_dicke_state(4,2,*cal)
    baseline_seconds=time.monotonic()-tick
    adj,node=baseline.make_chip(*cal,4,2)
    skew={q:baseline.rate(cal[3][q])-baseline.rate(cal[2][q]) for q in node}
    bias=lambda qs:baseline.readout_bias(qs,4,2,skew)
    template=cirq.read_json(ROOT/'template_native.json');logical=sorted(template.all_qubits())
    r0=min(q.row for q in logical);c0=min(q.col for q in logical)
    cells=[(q.row-r0,q.col-c0) for q in logical]
    seq=[tuple(logical.index(q) for q in op.qubits) for op in template.all_operations() if len(op.qubits)==2]
    lab=baseline.best_patch(adj,node,cells,seq,bias)
    cost0=baseline.estimate_error(reference,rqs,adj,node,bias)
    if lab is None:
        return reference,rqs,reference,rqs,dict(selected='baseline',reason='no square placement',baseline_cost=cost0,baseline_seconds=baseline_seconds,seconds=time.monotonic()-tick)
    candidate=template.transform_qubits(dict(zip(logical,lab)));cqs=set(lab)
    cost1=baseline.estimate_error(candidate,cqs,adj,node,bias)
    selection='candidate' if cost1<cost0 else 'baseline'
    return reference,rqs,candidate,cqs,dict(selected=selection,reason='lower existing estimate_error; baseline on ties',baseline_cost=cost0,candidate_cost=cost1,baseline_seconds=baseline_seconds,seconds=time.monotonic()-tick)


def verify(c,qs,cal,tolerance):
    baseline.check_circuit(c,*cal[:2]);test_dicke.check_rules(c,qs,4,*cal[:2]);judge.get_device().validate_circuit(c)
    assert len(qs)==4 and len(c)<=1750 and c.all_qubits()==set(qs)
    assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
    state=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=sorted(qs)).final_state_vector
    target=judge.create_dicke_statevector(4,2);overlap=np.vdot(target,state)
    error=float(np.linalg.norm(state-target*overlap/abs(overlap)))
    assert error<tolerance
    return error


def calibration_for(seed):
    """Replay saved explicit maps instead of depending on device-set iteration."""
    path=ROOT/f'calibration_{seed}.json'
    if not path.exists():return judge.fake_calibration(seed)
    maps=[]
    for index,entries in enumerate(json.loads(path.read_text())):
        dictionary={}
        for entry in entries:
            key=entry['key']
            key=tuple(cirq.GridQubit(*q) for q in key) if index==0 else cirq.GridQubit(*key)
            dictionary[key]=tuple(entry['value'])
        maps.append(dictionary)
    return tuple(maps)


def main():
    checks=score.check()
    checks['stress_model_check']=stress_noise.check();checks['signed_model_check']=signed_noise.check()
    (ROOT/'independent_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    rows=[];pairs=[];selections=[];circuits={};start=time.monotonic()
    for seed in SEEDS:
        cal=calibration_for(seed)
        ref,rqs,new,nqs,selection=select(cal);assert selection['seconds']<60
        for name,c,qs in [('baseline',ref,rqs),('candidate',new,nqs)]:
            err=verify(c,qs,cal,1e-5 if name=='baseline' else 1e-10);selection[name+'_state_error']=err
            circuits[f'{seed}-{name}']=c
        selections.append(dict(seed=seed,**selection))
        # Capture calibration values explicitly; fake calibration relies on device iteration order.
        calibration=[]
        for dictionary in cal:
            entries=[]
            for key,value in dictionary.items():
                encoded=[[q.row,q.col] for q in key] if isinstance(key,tuple) else [key.row,key.col]
                entries.append(dict(key=encoded,value=list(value)))
            calibration.append(entries)
        (ROOT/f'calibration_{seed}.json').write_text(json.dumps(calibration,indent=2)+'\n')
        for model in MODELS:
            sampled={}
            for name,c,qs in [('baseline',ref,rqs),('candidate',new,nqs)]:
                fn=signed_noise.probabilities if model=='signed_zz' else stress_noise.probabilities
                pz,px=fn(c,qs,cal,seed,model,realizations=4)
                samples=score.samples(pz,px,4,2,seed=640000+seed)
                sampled[name]=samples[4];assert np.isfinite(sampled[name]).all()
                f,zf,zb,x,proxy=fast_eval.expected_score(pz,px,4,2,4,10000)
                rows.append(dict(seed=seed,model=model,variant=name,moments=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),qubits=[[q.row,q.col] for q in sorted(qs)],E_score=float(sampled[name].mean()),MC_standard_error=float(sampled[name].std(ddof=1)/math.sqrt(len(sampled[name]))),replicates=len(sampled[name]),valid_fraction=float(f),Z_floor=float(zf),Z_bias=float(zb),X_penalty=float(x),penalty_inverse_proxy=float(proxy),pz=pz.tolist(),px=px.tolist()))
            chosen=sampled[selection['selected']]
            for name,values in [('raw_candidate',sampled['candidate']),('selected_with_fallback',chosen)]:
                delta=values-sampled['baseline']
                pairs.append(dict(seed=seed,model=model,variant=name,mean_delta=float(delta.mean()),paired_MC_standard_error=float(delta.std(ddof=1)/math.sqrt(len(delta)))))
            print(seed,model,selection['selected'],pairs[-1]['mean_delta'],flush=True)
            report=dict(status='Frozen six-seed synthetic calibration pilot; no maintained promotion',seeds=SEEDS,models=MODELS,rows=rows,paired_differences=pairs,selections=selections,elapsed_seconds=time.monotonic()-start,baseline_sha256=hashlib.sha256((ROOT/'baseline.py').read_bytes()).hexdigest(),scoring='E[1/(Z+X)] Monte Carlo,32768 repetitions,10000 independent shots per basis,general k=2. Four shared detuning draws. At N4 cutoff-four equals all-X.',limitations='Synthetic calibrations and assumed coherent/ZZ fields,not measured hardware. Six calibration seeds are independent units; MC errors are shot-repetition errors,not hardware/generalization uncertainty. Raw and selected variants share seeds,not necessarily placement. No ancillas/measurements in preparation.')
            (ROOT/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        cirq.to_json(circuits,ROOT/'paired_circuits.json')
    print('COMPLETE',time.monotonic()-start,flush=True)


if __name__=='__main__':main()
