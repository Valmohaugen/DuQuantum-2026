"""Independent mixed-field and finite-strength checks for PORT016."""
import json
from pathlib import Path

import cirq
import numpy as np

from .w_edge_sensitivity import coefficients
from .w_state_cost import DUR_CZ, DUR_1Q

ROOT = Path(__file__).parent


def exact(circuit, weights, scale):
    order = sorted(circuit.all_qubits())
    explicit = cirq.Circuit()
    for moment in circuit:
        explicit.append(moment)
        duration = DUR_CZ if any(len(op.qubits) == 2 for op in moment) else DUR_1Q
        for edge, weight in weights.items():
            explicit.append(cirq.Moment(cirq.ZZPowGate(
                exponent=scale*100000.*duration*weight).on(*edge)))
    psi = cirq.Simulator(dtype=np.complex128).simulate(explicit, qubit_order=order).final_state_vector
    return abs(psi[[1 << i for i in reversed(range(len(order)))]])**2


def z_bias(probabilities):
    conditional = probabilities/probabilities.sum()
    return float(10000*sum((conditional-1/len(conditional))**2))


def main():
    q = cirq.LineQubit.range(4)
    circuit = cirq.Circuit(cirq.ry(.71).on_each(*q), cirq.CZ(q[0], q[1]),
                          cirq.rz(.49)(q[1]), cirq.rx(.37)(q[1]),
                          cirq.CZ(q[1], q[2]), cirq.ry(-.29)(q[2]),
                          cirq.CZ(q[2], q[3]), cirq.rx(.43)(q[3]))
    edges = [(q[i], q[i+1]) for i in range(3)]
    a, b = dict(zip(edges, [1., -1., .5])), dict(zip(edges, [-.25, .75, 1.]))
    plus = {e: a[e]+b[e] for e in edges}
    minus = {e: a[e]-b[e] for e in edges}
    ca, cb, cp, cm = [coefficients(circuit, w) for w in (a, b, plus, minus)]
    identity_error = float(max(abs(cp['quadratic']+cm['quadratic']-2*ca['quadratic']-2*cb['quadratic'])))
    assert identity_error < 1e-13
    eps = .03
    cross = (exact(circuit, plus, eps)-exact(circuit, minus, eps)
             -exact(circuit, minus, -eps)+exact(circuit, plus, -eps))/(8*eps**2)
    predicted_cross = (cp['quadratic']-ca['quadratic']-cb['quadratic'])/2
    cross_error = float(max(abs(cross-predicted_cross)))
    assert max(abs(predicted_cross)) > 1e-7
    assert cross_error < 1e-7
    rows = []
    for name, weights, expansion in [('a', a, ca), ('b', b, cb)]:
        for scale in (-1., -.5, -.1, .1, .5, 1.):
            measured = exact(circuit, weights, scale)
            predicted = expansion['ideal']+scale*expansion['linear']+scale**2*expansion['quadratic']
            rows.append(dict(field=name, scale=scale,
                             max_probability_error=float(max(abs(measured-predicted))),
                             exact_Z_bias=z_bias(measured), predicted_Z_bias=z_bias(predicted)))
    assert max(r['max_probability_error'] for r in rows) < 1e-4
    report = dict(status='mixed-field algebra and independent full-strength four-qubit check passed',
                  polarization_identity_error=identity_error, independent_cross_coefficient_error=cross_error,
                  max_full_strength_probability_error=max(r['max_probability_error'] for r in rows),
                  rows=rows, scope='Small coherent-only example, with nonreal intermediate amplitudes. This does not bound larger-circuit truncation or mixed-noise error.')
    (ROOT/'w_edge_fullfield_checks.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}), flush=True)


if __name__ == '__main__':
    main()
