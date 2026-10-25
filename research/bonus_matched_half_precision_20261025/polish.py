"""Fixed peer topology, strict common-phase polish, one shared 60s budget."""
import json, math, time
import cirq, cirq_google
import numpy as np
from scipy.optimize import least_squares
from . import helpers as h
from .harvest import certify
class BudgetExpired(Exception):
    pass


def states_and_jacobian(theta, edges, n, columns, zset):
    """Forward state and tangent propagation, independent of Cirq compilation."""
    all_states = np.zeros((len(theta) + 1, columns, 2**n))
    for r in range(columns):
        all_states[0, r, (1 << r) - 1] = 1
    gates = [('ry', q) for q in range(n)]
    for a, b in edges:
        gates.extend([('cz', (a, b)), ('ry', a), ('ry', b)])
    parameter = 0
    indices = np.arange(2**n)
    for kind, data in gates:
        if kind == 'cz':
            a, b = data
            mask = (1 << (n - 1 - a)) | (1 << (n - 1 - b))
            all_states[:, :, (indices & mask) == mask] *= -1
            continue
        tensor = all_states.reshape((len(theta) + 1, columns) + (2,) * n)
        a, b = np.take(tensor, 0, axis=data + 2), np.take(tensor, 1, axis=data + 2)
        co, si = np.cos(theta[parameter] / 2), np.sin(theta[parameter] / 2)
        tensor = np.stack([co * a - si * b, si * a + co * b], axis=data + 2)
        state = tensor[0]
        a, b = np.take(state, 0, axis=data + 1), np.take(state, 1, axis=data + 1)
        tensor[parameter + 1] = np.stack([-b / 2, a / 2], axis=data + 1)
        all_states = tensor.reshape((len(theta) + 1, columns, 2**n))
        parameter += 1
    assert parameter == len(theta)
    for q in zset:
        all_states[:, :, (indices & (1 << (n-1-q))) != 0] *= -1
    return all_states[0], all_states[1:].reshape(len(theta), -1).T


def main():
    dev=cirq_google.Willow105.metadata
    qr={q:(1e-3,0.) for q in dev.qubit_set};pr={tuple(e):(1e-3,0.) for e in dev.qubit_pairs}
    adj,node=h.b.make_chip(pr,qr,qr,qr,15,4)
    comparison=json.loads((h.ROOT/'comparison.json').read_text())
    reports=[];start=time.monotonic();numerical=0.
    for item in comparison['rows']:
        if not item['strict_depth_opportunity']:continue
        n=item['n'];name=item['peer']['name']
        original=json.loads((h.ROOT/f'{name}.json').read_text())
        edges=original['edges'];initial=np.array(original['angles']);zset=original.get('zset',[])
        goal=np.array([h.target(n,r) for r in range(4)])
        tick=time.monotonic()
        def sj(theta):return states_and_jacobian(theta,edges,n,4,zset)
        state,jac=sj(initial);sign=1. if np.vdot(goal,state).real>=0 else -1.;goal*=sign
        derivative_errors=[]
        for j in (0,len(initial)//2,len(initial)-1):
            plus=initial.copy();minus=initial.copy();plus[j]+=1e-6;minus[j]-=1e-6
            derivative_errors.append(float(np.max(abs(((sj(plus)[0]-sj(minus)[0])/2e-6).ravel()-jac[:,j]))))
        assert max(derivative_errors)<1e-7
        cache={};best=dict(theta=initial.copy(),norm=float('inf'),calls=0)
        def evaluate(theta):
            if numerical+time.monotonic()-tick>60:raise BudgetExpired()
            if 'theta' not in cache or not np.array_equal(theta,cache['theta']):
                states,jac=sj(theta);residual=(states-goal).ravel()
                cache.update(theta=theta.copy(),residual=residual,jacobian=jac)
                best['calls']+=1
                if np.linalg.norm(residual)<best['norm']:best.update(theta=theta.copy(),norm=float(np.linalg.norm(residual)))
            return cache
        try:
            fit=least_squares(lambda x:evaluate(x)['residual'],initial,jac=lambda x:evaluate(x)['jacobian'],method='lm',ftol=1e-14,xtol=1e-14,gtol=1e-14,max_nfev=250)
            evaluate(fit.x);termination=str(fit.message)
        except BudgetExpired:termination='combined 60s numerical budget reached'
        duration=time.monotonic()-tick;numerical+=duration
        polished=dict(original,angles=best['theta'].tolist())
        assert polished['edges']==original['edges'] and polished.get('zset',[])==zset
        check=certify(polished,f'polished-{n}',adj,node)
        (h.ROOT/f'polished_{n}_3.json').write_text(json.dumps(polished,indent=2)+'\n')
        row=dict(n=n,check=check,termination=termination,numerical_seconds=duration,residual_calls=best['calls'],max_angle_change=float(max(abs(best['theta']-initial))),derivative_max_errors=derivative_errors,common_real_sign=sign)
        reports.append(row);print('POLISH',row,flush=True)
        if check['accepted']:
            qs=h.b.best_path(adj,node,[1]*(n-1),float('-inf'))
            c=h.schedule(h.optimize(h.compile_ops(h.operations(qs,polished))),restarts=3)
            cirq.to_json(c,h.ROOT/f'decoder_{n}_r0to3_native.json')
    report=dict(numerical_budget_seconds=60,numerical_seconds=numerical,total_seconds=time.monotonic()-start,rows=reports)
    (h.ROOT/'precision_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',report,flush=True)

if __name__=='__main__':main()
