"""Issue14 no-fit native harvest; bounded scheduling and all56 validation."""
import hashlib
import json
import math
import time
from pathlib import Path
import cirq
import cirq_google
import numpy as np
from . import baseline_submission as baseline
from .commuting_schedule import schedule

ROOT=Path(__file__).parent


def verify(c,qs,n,k):
    assert len(qs)==n and len(set(qs))==n and c.all_qubits()==set(qs)
    assert 0<len(c)<=1750
    assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
    cirq_google.Willow105.validate_circuit(c)
    state=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=sorted(qs)).final_state_vector
    target=np.array([int(i.bit_count()==k) for i in range(2**n)])/math.sqrt(math.comb(n,k))
    overlap=np.vdot(target,state)
    error=float(np.linalg.norm(state-target*overlap/abs(overlap)))
    return error,state


def main():
    start=time.monotonic();deadline=start+45
    circuits={f'{n},{k}':baseline.create_dicke_state_adaptive(n,k)[0] for n in range(2,16) for k in range(1,n//2+1)}
    original={key:len(c) for key,c in circuits.items()}
    cirq.to_json(circuits,ROOT/'baseline_circuits.json')
    summaries=json.loads((ROOT/'summary.json').read_text())
    coverage=[];checks=[];gains=[];alternatives=[]
    keys=sorted(summaries,key=lambda key:-(math.prod(map(int,key.split(',')))*(1/summaries[key]['moments']-1/original[key])))
    for key in keys:
        n,k=map(int,key.split(','));source=summaries[key]['file']
        item=dict(N=n,k=k,source=source,status='not-started');coverage.append(item)
        if time.monotonic()>=deadline:continue
        data=cirq.read_json(ROOT/source);c=data['circuit'];qs=data['qubits'];item['status']='checking'
        row=dict(N=n,k=k,source=source,source_sha256=hashlib.sha256((ROOT/source).read_bytes()).hexdigest(),baseline_depth=original[key],reported_depth=summaries[key]['moments'],raw_depth=len(c),raw_CZ=sum(op.gate==cirq.CZ for op in c.all_operations()))
        try:
            error,state=verify(c,qs,n,k)
            row.update(raw_error=error,raw_accepted=bool(error<1e-5))
            if error>=1e-5:
                item['status']='rejected-state-error';checks.append(row);continue
        except Exception as exc:
            row.update(raw_accepted=False,rejection=f'{type(exc).__name__}: {exc}');item['status']='rejected-structure';checks.append(row);continue
        chosen=c;scheduled=False
        if time.monotonic()<deadline:
            d=schedule(c,restarts=3);scheduled=True
            derr,dstate=verify(d,qs,n,k)
            phase=np.vdot(state,dstate);equivalence=float(np.linalg.norm(dstate-state*phase/abs(phase)))
            row.update(scheduled_depth=len(d),scheduled_error=derr,schedule_phase_aligned_difference=equivalence)
            assert derr<1e-5 and equivalence<1e-10
            if len(d)<len(chosen):chosen=d
        before=circuits[key];oldcz=sum(op.gate==cirq.CZ for op in before.all_operations())
        newcz=sum(op.gate==cirq.CZ for op in chosen.all_operations())
        if oldcz!=newcz:
            alternatives.append(dict(N=n,k=k,incumbent_depth=len(before),incumbent_CZ=oldcz,candidate_depth=len(chosen),candidate_CZ=newcz,candidate_source=source,incumbent_source='baseline_circuits.json',note='Different CZ cost recorded; primary objective remains minimum native moments.'))
        if len(chosen)<len(before):
            circuits[key]=chosen
            gain=dict(N=n,k=k,before=len(before),depth=len(chosen),CZ=newcz,source=source,state_l2_error=verify(chosen,qs,n,k)[0])
            gains.append(gain);print('ACCEPT',gain,flush=True)
        row.update(retained_depth=len(circuits[key]),candidate_selected=len(chosen)<len(before),preserved_precision_tie=(key=='4,2' and len(chosen)==len(before)))
        checks.append(row);item['status']='complete' if scheduled else 'raw-complete;scheduling-deadline'
        cirq.to_json(circuits,ROOT/'harvest_circuits.json')
    search_seconds=time.monotonic()-start;rows=[]
    for key,c in circuits.items():
        n,k=map(int,key.split(','));assert len(c)<=original[key]
        error,_=verify(c,sorted(c.all_qubits()),n,k);assert error<1e-5
        rows.append(dict(N=n,k=k,before=original[key],depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),state_l2_error=error))
    assert len(rows)==56
    cirq.to_json(circuits,ROOT/'harvest_circuits.json')
    result=dict(status='All56 retained complex128/native/device/qubit checks passed',ticket='PORT-039',source_commit='0a848a5e0b7ac016d76527f4bde5b31725b6aefe',baseline_score=sum(int(key.split(',')[0])*int(key.split(',')[1])/depth for key,depth in original.items()),score=sum(r['N']*r['k']/r['depth'] for r in rows),search_budget_seconds=45,search_seconds=search_seconds,total_seconds=time.monotonic()-start,coverage=coverage,checks=checks,improvements=gains,CZ_alternatives=alternatives,rows=rows,whole_state_tolerance=1e-5,no_fit=True,no_maintained_edits=True,preserved_exact_D4_tie=circuits['4,2']==baseline.create_dicke_state_adaptive(4,2)[0])
    (ROOT/'harvest_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMPLETE',result['score'],result['search_seconds'],result['total_seconds'],flush=True)


if __name__=='__main__':main()
