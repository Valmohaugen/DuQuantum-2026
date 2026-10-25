"""Explicit density-matrix stress models layered onto the existing evaluator.

Coherent model: each physical coupler has fixed independent N(0,sigma^2)
coefficients (delta,alpha,beta), applying exp(i(delta*n_i*n_j+alpha*n_i+
beta*n_j)) after every CZ. Coefficients persist across detuning realizations.
ZZ model: H/h = J/4 sum Z_i Z_j on all calibrated edges whose two qubits are
in the circuit, applied for each moment's duration after Markovian decay.
Outside spectator qubits, leakage, pulse overlap and correlated readout are
not modeled. This is a defined robustness test, not a fitted hardware model.
"""
import math

import cirq
import numpy as np

from . import fast_eval as fe


MODELS = {'nominal': (0., 0.), 'coherent': (.03, 0.), 'zz': (0., 100000.)}


def fields(cal, seed, n, realization):
    qubits = sorted(cal[1])
    edges = sorted({tuple(sorted(edge)) for edge in cal[0]})
    # Paired variants share physical-chip draws, including overlapping qubits.
    rng = np.random.default_rng([481, seed, n, realization])
    det = dict(zip(qubits, rng.normal(0., 7500., len(qubits))))
    rng = np.random.default_rng([482, seed, n])
    coherent = {edge:rng.normal(size=3) for edge in edges}
    return det, coherent


def diagonal(rho, phases):
    shape = (2,)*rho.n
    rho.t *= phases.reshape(shape+(1,)*rho.n)
    rho.t *= phases.conj().reshape((1,)*rho.n+shape)


def run(rho, moments, order, cal, det, coefficients, sigma=0., zz_hz=0.):
    index = {q:i for i,q in enumerate(order)}; n = len(order)
    indices = np.arange(2**n)
    bits = {q:((indices >> (n-i-1)) & 1).astype(float) for i,q in enumerate(order)}
    zz = np.zeros(2**n)
    if zz_hz:
        for a,b in coefficients:
            if a in index and b in index:
                zz += (1-2*bits[a])*(1-2*bits[b])
    tphi_inverse = 1/fe.T2-1/(2*fe.T1)
    for moment in moments:
        duration = fe.DUR_CZ if any(len(op.qubits)==2 for op in moment) else fe.DUR_1Q
        phase = np.zeros(2**n) if sigma else None
        for op in moment:
            if len(op.qubits)==2:
                rho.cz(*(index[q] for q in op.qubits))
                if sigma:
                    a,b = sorted(op.qubits); delta,alpha,beta = coefficients[a,b]*sigma
                    phase += delta*bits[a]*bits[b]+alpha*bits[a]+beta*bits[b]
            else:
                rho.unitary1(index[op.qubits[0]], cirq.unitary(op))
        if sigma:
            diagonal(rho, np.exp(1j*phase))
        for op in moment:
            err = fe._err(cal[0],*op.qubits) if len(op.qubits)==2 else fe._err(cal[1],op.qubits[0])
            rho.depol([index[q] for q in op.qubits], err)
        ad = 1-math.exp(-duration/fe.T1)
        pd = 1-math.exp(-2*duration*tphi_inverse)
        for q,i in index.items():
            rho.idle(i, ad, pd, 2*math.pi*det[q]*duration)
        if zz_hz:
            diagonal(rho, np.exp(-.5j*math.pi*zz_hz*duration*zz))


def probabilities(circuit, qubits, cal, seed, model, realizations=4):
    order = sorted(qubits); n = len(order)
    assert set(order)==circuit.all_qubits()
    sigma,zz_hz = MODELS[model]
    pz,px = np.zeros(2**n),np.zeros(2**n)
    hm = [cirq.Moment(cirq.H.on_each(*order))]
    for realization in range(realizations):
        det,coefficients = fields(cal,seed,n,realization)
        rho = fe.Rho(n)
        run(rho,list(circuit),order,cal,det,coefficients,sigma,zz_hz)
        pz += rho.probs()/realizations
        run(rho,hm,order,cal,det,coefficients,sigma,zz_hz)
        px += rho.probs()/realizations
    return fe.readout(pz,order,*cal[2:]),fe.readout(px,order,*cal[2:])


def check():
    q = cirq.LineQubit.range(3)
    c = cirq.Circuit(cirq.H.on_each(*q), cirq.CZ(q[0],q[1]), cirq.ry(.37)(q[2]),
                     cirq.CZ(q[1],q[2]), cirq.rx(-.27)(q[1]))
    cal = ({(q[0],q[1]):(.004,0.),(q[1],q[2]):(.005,0.)},
           {v:(.001,0.) for v in q},{v:(.01,0.) for v in q},{v:(.015,0.) for v in q})
    det,coefficients = fields(cal,3,3,0)
    a,b = fe.Rho(3),fe.Rho(3)
    fe.run_noisy(a,list(c),dict(zip(q,range(3))),*cal[:2],det)
    run(b,list(c),q,cal,det,coefficients)
    nominal_error = float(np.max(abs(a.t-b.t)))
    assert nominal_error < 1e-13
    zero = [{key:(0.,0.) for key in d} for d in cal]
    old1,old2 = fe.T1,fe.T2
    try:
        fe.T1 = fe.T2 = float('inf')
        density = fe.Rho(3)
        run(density,list(c),q,zero,{v:0. for v in q},coefficients,.03,100000.)
    finally:
        fe.T1,fe.T2 = old1,old2
    explicit = cirq.Circuit()
    for moment in c:
        explicit.append(moment)
        duration = fe.DUR_CZ if any(len(op.qubits)==2 for op in moment) else fe.DUR_1Q
        for op in moment:
            if len(op.qubits)==2:
                a,b=sorted(op.qubits);delta,alpha,beta=coefficients[a,b]*.03
                explicit.append(cirq.Moment(cirq.CZPowGate(exponent=delta/math.pi)(a,b)))
                explicit.append(cirq.Moment([cirq.ZPowGate(exponent=alpha/math.pi)(a),cirq.ZPowGate(exponent=beta/math.pi)(b)]))
        for a,b in coefficients:
            explicit.append(cirq.Moment(cirq.ZZPowGate(exponent=100000.*duration)(a,b)))
    psi = cirq.Simulator(dtype=np.complex128).simulate(explicit,qubit_order=q).final_state_vector
    coherent_error = float(np.max(abs(density.t.reshape(8,8)-np.outer(psi,psi.conj()))))
    assert coherent_error < 1e-12
    return dict(nominal_density_error=nominal_error,independent_Cirq_unitary_density_error=coherent_error,
                status='nominal channel equivalence and coherent/ZZ phase convention checked independently')


if __name__=='__main__':
    import json
    from pathlib import Path
    result=check()
    Path(__file__).with_name('w_stress_noise_checks.json').write_text(json.dumps(result,indent=2)+'\n')
    print(result,flush=True)
