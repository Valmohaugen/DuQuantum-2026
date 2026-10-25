"""Second-order coherent ZZ contribution to valid W-output probabilities.

Propagate the three wavefunction coefficients of exp(-i lambda H dt), with
H/h = J/4 sum Z_i Z_j. This isolates coherent coupling from Markovian/readout
errors; adding the two models neglects mixed terms. No hardware claim follows
from this expansion alone.
"""
import math

import cirq
import numpy as np

from .w_z_sensitivity import apply_gate
from .w_state_cost import DUR_CZ,DUR_1Q


def coefficients(circuit, edges, reference_hz=100000.):
    order=sorted(circuit.all_qubits());n=len(order);index={q:i for i,q in enumerate(order)}
    if not 2<=n<=12:raise ValueError('ZZ sensitivity prototype supports2<=N<=12')
    basis=np.arange(2**n)
    z={q:1.-2*((basis>>(n-i-1))&1) for i,q in enumerate(order)}
    zz=sum((z[a]*z[b] for a,b in {tuple(sorted(e)) for e in edges} if a in index and b in index),start=np.zeros(2**n))
    wave=np.zeros((3,)+(2,)*n,dtype=complex);wave[(0,)+(0,)*n]=1
    for moment in circuit:
        for op in moment:wave=apply_gate(wave,op,index,batch=True)
        duration=DUR_CZ if any(len(op.qubits)==2 for op in moment) else DUR_1Q
        h=(.5*math.pi*reference_hz*duration*zz).reshape((2,)*n)
        wave[2] += -1j*h*wave[1]-.5*h*h*wave[0]
        wave[1] += -1j*h*wave[0]
    valid=[1<<(n-i-1) for i in range(n)]
    a,b,c=wave.reshape(3,-1)[:,valid]
    return dict(ideal=abs(a)**2,linear=2*np.real(a.conj()*b),quadratic=abs(b)**2+2*np.real(a.conj()*c),reference_hz=reference_hz)


if __name__=='__main__':
    import json
    from pathlib import Path
    from .w_cost_selection import baseline
    from .w_hardware_probe import fast_eval as fe,judge
    from .w_stress_noise import run,fields
    cal=judge.fake_calibration(13);c,qs=baseline.create_dicke_state(4,1,*cal);order=sorted(qs)
    result=coefficients(c,cal[0]);valid=[1<<(3-i) for i in range(4)]
    zero=[{q:(0.,0.) for q in d} for d in cal]
    _,field=fields(cal,13,4,0);old1,old2=fe.T1,fe.T2;checks=[]
    try:
        fe.T1=fe.T2=float('inf')
        for epsilon in (.1,.03,.01):
            sides=[]
            for sign in (-1,1):
                rho=fe.Rho(4)
                run(rho,list(c),order,zero,{q:0. for q in order},field,zz_hz=sign*epsilon*100000.)
                sides.append(rho.probs()[valid])
            measured=(sides[0]+sides[1]-2*result['ideal'])/(2*epsilon**2)
            checks.append(dict(epsilon=epsilon,max_quadratic_coefficient_error=float(max(abs(measured-result['quadratic'])))))
        assert checks[-1]['max_quadratic_coefficient_error']<1e-7,checks
        assert checks[-1]['max_quadratic_coefficient_error']<checks[0]['max_quadratic_coefficient_error']/20,checks
    finally:fe.T1,fe.T2=old1,old2
    report=dict(status='symmetric finite-difference check passed; no selection gain claimed',coefficients={k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in result.items()},checks=checks)
    Path(__file__).with_name('w_zz_sensitivity_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report,flush=True)
