"""PORT016 prototype: second-order output probabilities for signed couplers.

Patterns depend only on physical coordinates and a fixed pattern identifier,
never on calibration/evaluation seeds. This module does not change selection.
"""
import hashlib
import math

import cirq
import numpy as np

from .w_state_cost import DUR_CZ, DUR_1Q
from .w_z_sensitivity import apply_gate


def signs(edges, pattern):
    result = {}
    for edge in edges:
        a, b = sorted(edge)
        key = f'PORT016-pattern-{pattern}:{a!r}:{b!r}'.encode()
        result[a, b] = 1. if hashlib.sha256(key).digest()[0] & 1 else -1.
    return result


def coefficients(circuit, edge_weights, reference_hz=100000.):
    order = sorted(circuit.all_qubits()); n = len(order)
    if not 2 <= n <= 12:
        raise ValueError('Signed-coupler prototype supports2<=N<=12')
    index = {q: i for i, q in enumerate(order)}
    basis = np.arange(2**n)
    z = {q: 1.-2*((basis >> (n-i-1)) & 1) for i, q in enumerate(order)}
    zz = sum((weight*z[a]*z[b] for (a, b), weight in edge_weights.items()
              if a in index and b in index), start=np.zeros(2**n))
    wave = np.zeros((3,)+(2,)*n, dtype=complex)
    wave[(0,)+(0,)*n] = 1
    for moment in circuit:
        for op in moment:
            wave = apply_gate(wave, op, index, batch=True)
        duration = DUR_CZ if any(len(op.qubits) == 2 for op in moment) else DUR_1Q
        h = (.5*math.pi*reference_hz*duration*zz).reshape((2,)*n)
        wave[2] += -1j*h*wave[1]-.5*h*h*wave[0]
        wave[1] += -1j*h*wave[0]
    valid = [1 << (n-i-1) for i in range(n)]
    a, b, c = wave.reshape(3, -1)[:, valid]
    return dict(ideal=abs(a)**2, linear=2*np.real(a.conj()*b),
                quadratic=abs(b)**2+2*np.real(a.conj()*c), reference_hz=reference_hz)


def check():
    q = cirq.LineQubit.range(4)
    edges = [(q[i], q[i+1]) for i in range(3)]
    circuit = cirq.Circuit(cirq.ry(.71).on_each(*q), cirq.CZ(q[0], q[1]),
                           cirq.rx(.37)(q[1]), cirq.CZ(q[1], q[2]),
                           cirq.ry(-.29)(q[2]), cirq.CZ(q[2], q[3]), cirq.rx(.43)(q[3]))
    weights = dict(zip(edges, [1., -1., .5]))
    expansion = coefficients(circuit, weights)
    rows = []
    for epsilon in (.1, .03, .01):
        values = []
        for side in (-1, 1):
            explicit = cirq.Circuit()
            for moment in circuit:
                explicit.append(moment)
                duration = DUR_CZ if any(len(op.qubits) == 2 for op in moment) else DUR_1Q
                for edge, weight in weights.items():
                    explicit.append(cirq.Moment(cirq.ZZPowGate(
                        exponent=side*epsilon*100000.*duration*weight).on(*edge)))
            psi = cirq.Simulator(dtype=np.complex128).simulate(explicit, qubit_order=q).final_state_vector
            values.append(abs(psi[[8, 4, 2, 1]])**2)
        first = (values[1]-values[0])/(2*epsilon)
        second = (values[1]+values[0]-2*expansion['ideal'])/(2*epsilon**2)
        rows.append(dict(epsilon=epsilon,
                         max_linear_error=float(max(abs(first-expansion['linear']))),
                         max_quadratic_error=float(max(abs(second-expansion['quadratic'])))))
    assert rows[-1]['max_linear_error'] < 1e-7
    assert rows[-1]['max_quadratic_error'] < 1e-7
    # Uniform weights reproduce the prior implementation; coordinate fields
    # are unaffected by iteration order or the presence of another coupler.
    from .w_zz_sensitivity import coefficients as uniform
    a, b = uniform(circuit, edges), coefficients(circuit, {e: 1. for e in edges})
    assert all(np.array_equal(a[k], b[k]) for k in ('ideal', 'linear', 'quadratic'))
    assert signs(edges, 0) == signs(reversed(edges), 0)
    assert signs(edges[:2], 0) == {e: signs(edges, 0)[e] for e in edges[:2]}
    return dict(status='weighted derivative checks passed; selector not changed', checks=rows,
                uniform_equivalence=True, physical_pattern_stability=True)


if __name__ == '__main__':
    import json
    from pathlib import Path
    result = check()
    Path(__file__).with_name('w_edge_sensitivity_checks.json').write_text(json.dumps(result, indent=2)+'\n')
    print(result, flush=True)
