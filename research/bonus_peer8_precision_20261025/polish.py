"""Fixed 38-CZ peer8 precision repair. Run only after CPU release."""
import hashlib
import json
import time
import cirq
import cirq_google
import numpy as np
from scipy.optimize import least_squares
from . import helpers as h
from .state_jacobian import states_and_jacobian, BudgetExpired


def faithful(ops):
    def rewrite(op):
        return cirq.PhasedXZGate.from_matrix(cirq.unitary(op)).on(next(iter(op.qubits)))
    merged=cirq.merge_k_qubit_unitaries(cirq.Circuit(ops),k=1,rewriter=rewrite)
    return h.schedule(cirq.Circuit(merged.all_operations()),restarts=3)


def main():
    path=h.ROOT/'original_8_3.json';original=json.loads(path.read_text())
    n,k=original['n'],original['k'];edges=original['edges'];zset=original.get('zset',[])
    initial=np.array(original['angles'])
    assert (n,k,len(edges),len(initial))==(8,3,38,84)
    qs=[cirq.GridQubit(i,7) for i in range(n)]
    target=np.array([h.target(n,r) for r in range(k+1)])
    def sj(x):return states_and_jacobian(x,edges,n,k+1,zset)
    raw,jac=sj(initial);sign=1. if np.vdot(target,raw).real>=0 else -1.
    target*=sign
    def native(row):
        c=faithful(h.operations(qs,row));cirq_google.Willow105.validate_circuit(c)
        assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
        sim=cirq.Simulator(dtype=np.complex128)
        states=np.array([sim.simulate(c,initial_state=(1<<r)-1,qubit_order=qs).final_state_vector for r in range(k+1)])
        phase=np.vdot(target,states);phase/=abs(phase)
        errors=np.linalg.norm(states-phase*target,axis=1)
        return c,dict(depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),column_errors=errors.tolist(),max_column_error=float(max(errors)),accepted=bool(max(errors)<1e-10),common_phase=[float(phase.real),float(phase.imag)])
    _,before=native(original)
    pre=dict(source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),raw_column_errors=np.linalg.norm(raw-target,axis=1).tolist(),native=before,common_real_sign=sign)
    (h.ROOT/'raw_precision_before_fit.json').write_text(json.dumps(pre,indent=2)+'\n')
    print('PRE_FIT',pre,flush=True)
    tick=time.monotonic();best=dict(theta=initial.copy(),norm=float(np.linalg.norm(raw-target)),calls=0);cache={};derivatives=[]
    if max(pre['raw_column_errors'])<1e-10 and before['accepted']:
        termination='Already certified; no least-squares call'
    else:
        for j in (0,42,83):
            plus=initial.copy();minus=initial.copy();plus[j]+=1e-6;minus[j]-=1e-6
            derivatives.append(float(np.max(abs(((sj(plus)[0]-sj(minus)[0])/2e-6).ravel()-jac[:,j]))))
        assert max(derivatives)<1e-7
        def evaluate(theta):
            if time.monotonic()-tick>60:raise BudgetExpired()
            if 'theta' not in cache or not np.array_equal(theta,cache['theta']):
                state,jacobian=sj(theta);residual=(state-target).ravel()
                cache.update(theta=theta.copy(),residual=residual,jacobian=jacobian);best['calls']+=1
                if np.linalg.norm(residual)<best['norm']:best.update(theta=theta.copy(),norm=float(np.linalg.norm(residual)))
            return cache
        try:
            result=least_squares(lambda x:evaluate(x)['residual'],initial,jac=lambda x:evaluate(x)['jacobian'],method='lm',ftol=1e-14,xtol=1e-14,gtol=1e-14,max_nfev=250)
            evaluate(result.x);termination=str(result.message)
        except BudgetExpired:termination='60-second budget; best iterate retained'
    seconds=time.monotonic()-tick
    polished=dict(original,angles=best['theta'].tolist())
    assert polished['edges']==edges and polished.get('zset',[])==zset
    raw_after,_=sj(best['theta']);errors=np.linalg.norm(raw_after-target,axis=1)
    circuit,after=native(polished)
    eligible=bool(max(errors)<1e-10 and after['accepted'] and after['depth']<67 and after['CZ']==38)
    report=dict(numerical_budget_seconds=60,numerical_seconds=seconds,termination=termination,evaluations=best['calls'],derivative_max_errors=derivatives,maximum_angle_change=float(max(abs(best['theta']-initial))),raw_before=pre,raw_after_column_errors=errors.tolist(),raw_after_max_error=float(max(errors)),faithful_native=after,integration_eligible=eligible,same_range_incumbent_depth=67,no_topology_change=True,no_default_ejection=True)
    (h.ROOT/'polished_8_3.json').write_text(json.dumps(polished,indent=2)+'\n')
    (h.ROOT/'precision_results.json').write_text(json.dumps(report,indent=2)+'\n')
    if eligible:cirq.to_json(circuit,h.ROOT/'decoder_8_r0to3_native.json')
    print('COMPLETE',report,flush=True)


if __name__=='__main__':main()
