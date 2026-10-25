"""Fixed30CZ peer7 repair; freeze raw and faithful-native evidence before fit."""
import hashlib
import json
import time
import cirq
import cirq_google
import numpy as np
from scipy.optimize import least_squares
from . import helpers as h
from .harvest import certify
from .state_jacobian import states_and_jacobian,BudgetExpired

def faithful(ops):
    def rewrite(op):return cirq.PhasedXZGate.from_matrix(cirq.unitary(op)).on(next(iter(op.qubits)))
    return cirq.Circuit(cirq.merge_k_qubit_unitaries(cirq.Circuit(ops),k=1,rewriter=rewrite).all_operations())

h.compile_ops=faithful
h.optimize=lambda c:c

def main():
    original_path=h.ROOT/'original_7_3.json';original=json.loads(original_path.read_text())
    n,k=original['n'],original['k'];assert (n,k)==(7,3) and len(original['edges'])==30
    initial=np.array(original['angles']);edges=original['edges'];zset=original.get('zset',[])
    assert len(initial)==67
    goal=np.array([h.target(n,r) for r in range(k+1)])
    def sj(theta):return states_and_jacobian(theta,edges,n,k+1,zset)
    raw,jac=sj(initial);sign=1. if np.vdot(goal,raw).real>=0 else -1.;goal*=sign
    raw_errors=np.linalg.norm(raw-goal,axis=1)
    dev=cirq_google.Willow105.metadata;qr={q:(1e-3,0.) for q in dev.qubit_set};pr={tuple(e):(1e-3,0.) for e in dev.qubit_pairs}
    adj,node=h.b.make_chip(pr,qr,qr,qr,15,4)
    before=certify(original,'unmodified-peer7-faithful',adj,node)
    pre=dict(source_sha256=hashlib.sha256(original_path.read_bytes()).hexdigest(),raw_column_errors=raw_errors.tolist(),raw_max_error=float(max(raw_errors)),raw_passes=bool(max(raw_errors)<1e-10),faithful_native=before,common_real_sign=sign,
             note='Written before least_squares is called. No coefficient change if raw and native already pass.')
    (h.ROOT/'raw_precision_before_fit.json').write_text(json.dumps(pre,indent=2)+'\n');print('PRE_FIT',pre,flush=True)
    tick=time.monotonic();derivative_errors=[];best=dict(theta=initial.copy(),norm=float(np.linalg.norm(raw-goal)),calls=0);cache={}
    if pre['raw_passes'] and before['accepted']:
        termination='Already certified; no least_squares call'
    else:
        for j in (0,33,66):
            plus=initial.copy();minus=initial.copy();plus[j]+=1e-6;minus[j]-=1e-6
            derivative_errors.append(float(np.max(abs(((sj(plus)[0]-sj(minus)[0])/2e-6).ravel()-jac[:,j]))))
        assert max(derivative_errors)<1e-7
        def evaluate(theta):
            if time.monotonic()-tick>60:raise BudgetExpired()
            if 'theta' not in cache or not np.array_equal(theta,cache['theta']):
                state,jacobian=sj(theta);residual=(state-goal).ravel();cache.update(theta=theta.copy(),residual=residual,jacobian=jacobian);best['calls']+=1
                if np.linalg.norm(residual)<best['norm']:best.update(theta=theta.copy(),norm=float(np.linalg.norm(residual)))
            return cache
        try:
            result=least_squares(lambda x:evaluate(x)['residual'],initial,jac=lambda x:evaluate(x)['jacobian'],method='lm',ftol=1e-14,xtol=1e-14,gtol=1e-14,max_nfev=250)
            evaluate(result.x);termination=str(result.message)
        except BudgetExpired:termination='60second numerical budget; best iterate retained'
    numerical=time.monotonic()-tick
    polished=dict(original,angles=best['theta'].tolist());assert polished['edges']==edges and polished.get('zset',[])==zset
    raw_after,_=sj(best['theta']);raw_after_errors=np.linalg.norm(raw_after-goal,axis=1)
    after=certify(polished,'polished-peer7-faithful',adj,node)
    report=dict(numerical_budget_seconds=60,numerical_seconds=numerical,termination=termination,derivative_max_errors=derivative_errors,
        evaluations=best['calls'],maximum_angle_change=float(max(abs(best['theta']-initial))),raw_before=pre,
        raw_after_column_errors=raw_after_errors.tolist(),raw_after_max_error=float(max(raw_after_errors)),faithful_native=after,
        integration_eligible=bool(after['accepted'] and after['depth']<=51 and after['CZ']==30 and max(raw_after_errors)<1e-10),
        no_topology_change=True,no_default_ejection=True,incumbent_same_range_depth=53)
    (h.ROOT/'polished_7_3.json').write_text(json.dumps(polished,indent=2)+'\n')
    (h.ROOT/'precision_results.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['integration_eligible']:
        qs=h.b.best_path(adj,node,[1]*6,float('-inf'));c=h.schedule(faithful(h.operations(qs,polished)),restarts=3)
        cirq.to_json(c,h.ROOT/'decoder_7_r0to3_native.json')
    print('COMPLETE',report,flush=True)

if __name__=='__main__':main()
