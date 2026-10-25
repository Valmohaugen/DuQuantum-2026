"""Held-out stress model with independent signed residual coupler strengths.

The +/-100kHz fields are assumptions, not Willow measurements. They persist
across moments and detuning draws, paired by physical edge between variants.
"""
import math

import cirq
import numpy as np

from . import w_stress_noise as stress

MODELS = ('nominal', 'signed_zz')


def couplings(cal, seed, n):
    edges = sorted({tuple(sorted(e)) for e in cal[0]})
    rng = np.random.default_rng([483, seed, n])
    return dict(zip(edges, rng.choice([-100000., 100000.], size=len(edges))))


def run(rho, moments, order, cal, det, coherent, hz):
    n = len(order)
    indices = np.arange(2**n)
    z = {q: 1.-2*((indices >> (n-i-1)) & 1) for i, q in enumerate(order)}
    energy = sum((j*z[a]*z[b] for (a, b), j in hz.items() if a in z and b in z),
                 start=np.zeros(2**n))
    for moment in moments:
        stress.run(rho, [moment], order, cal, det, coherent)
        duration = stress.fe.DUR_CZ if any(len(op.qubits) == 2 for op in moment) else stress.fe.DUR_1Q
        stress.diagonal(rho, np.exp(-.5j*math.pi*duration*energy))


def probabilities(circuit, qubits, cal, seed, model, realizations=4):
    assert model in MODELS
    order = sorted(qubits); n = len(order)
    hz = couplings(cal, seed, n) if model == 'signed_zz' else {}
    pz, px = np.zeros(2**n), np.zeros(2**n)
    for realization in range(realizations):
        det, coherent = stress.fields(cal, seed, n, realization)
        rho = stress.fe.Rho(n)
        run(rho, list(circuit), order, cal, det, coherent, hz)
        pz += rho.probs()/realizations
        run(rho, [cirq.Moment(cirq.H.on_each(*order))], order, cal, det, coherent, hz)
        px += rho.probs()/realizations
    return stress.fe.readout(pz, order, *cal[2:]), stress.fe.readout(px, order, *cal[2:])


def check():
    q = cirq.LineQubit.range(3)
    c = cirq.Circuit(cirq.H.on_each(*q), cirq.CZ(q[0], q[1]), cirq.ry(.37)(q[2]),
                     cirq.CZ(q[1], q[2]), cirq.rx(-.27)(q[1]))
    cal = ({(q[0], q[1]): (0., 0.), (q[1], q[2]): (0., 0.)},
           {v: (0., 0.) for v in q}, {v: (0., 0.) for v in q}, {v: (0., 0.) for v in q})
    hz = {(q[0], q[1]): 100000., (q[1], q[2]): -100000.}
    det, coherent = stress.fields(cal, 15, 3, 0)
    old1, old2 = stress.fe.T1, stress.fe.T2
    try:
        stress.fe.T1 = stress.fe.T2 = float('inf')
        rho = stress.fe.Rho(3)
        run(rho, list(c), q, cal, {v: 0. for v in q}, coherent, hz)
    finally:
        stress.fe.T1, stress.fe.T2 = old1, old2
    explicit = cirq.Circuit()
    for moment in c:
        explicit.append(moment)
        duration = stress.fe.DUR_CZ if any(len(op.qubits) == 2 for op in moment) else stress.fe.DUR_1Q
        for edge, j in hz.items():
            explicit.append(cirq.Moment(cirq.ZZPowGate(exponent=j*duration).on(*edge)))
    psi = cirq.Simulator(dtype=np.complex128).simulate(explicit, qubit_order=q).final_state_vector
    error = float(np.max(abs(rho.t.reshape(8, 8)-np.outer(psi, psi.conj()))))
    assert error < 1e-12
    # The nominal wrapper must reproduce the previously verified model exactly.
    a, b = stress.fe.Rho(3), stress.fe.Rho(3)
    run(a, list(c), q, cal, det, coherent, {})
    stress.run(b, list(c), q, cal, det, coherent)
    nominal = float(np.max(abs(a.t-b.t)))
    assert nominal < 1e-13
    return dict(independent_signed_Cirq_density_error=error, nominal_density_error=nominal,
                status='signed phase convention and nominal equivalence passed')


if __name__ == '__main__':
    import json
    from pathlib import Path
    report = check()
    Path(__file__).with_name('w_heterogeneous_noise_checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report, flush=True)
