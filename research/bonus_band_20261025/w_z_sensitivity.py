"""First-order probabilities of valid W outcomes, without a density matrix.

For each error insertion use forward |psi_t> and backward U_after^dagger|j>.
A Lindblad term L contributes |<b_j|L|psi>|^2 minus
Re(conj(<b_j|psi>)*<b_j|L^dagger L|psi>). Pauli channels are
averaged over their nonidentity Paulis. Readout is expanded to first order.
No detuning or products of error rates are included. Research prototype only.
"""
import itertools

import cirq
import numpy as np

from .w_state_cost import T1, T2, DUR_CZ, DUR_1Q, rate

I = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.diag([1., -1.]).astype(complex)
LOWER = np.array([[0, 1], [0, 0]], dtype=complex)
NUMBER = np.diag([0., 1.]).astype(complex)


def apply_local(state, matrix, axis):
    return np.moveaxis(np.tensordot(matrix, state, axes=([1], [axis])), 0, axis)


def apply_gate(state, op, index, batch=False, inverse=False):
    offset = int(batch)
    if op.gate == cirq.CZ:
        state = state.copy()
        sl = [slice(None)]*state.ndim
        for q in op.qubits:
            sl[index[q]+offset] = 1
        state[tuple(sl)] *= -1
        return state
    assert len(op.qubits) == 1
    matrix = cirq.unitary(op)
    return apply_local(state, matrix.conj().T if inverse else matrix, index[op.qubits[0]]+offset)


def probabilities(circuit, cal):
    qs = sorted(circuit.all_qubits()); n = len(qs)
    if not 2 <= n <= 12:
        raise ValueError('Sensitivity prototype supports 2<=N<=12')
    index = {q:i for i,q in enumerate(qs)}
    edges = {frozenset(q):rate(v) for q,v in cal[0].items()}
    state = np.zeros((2,)*n, dtype=complex); state[(0,)*n] = 1
    forward = []
    for moment in circuit:
        for op in moment:
            state = apply_gate(state, op, index)
        forward.append(state.copy())
    valid = np.array([1 << (n-i-1) for i in range(n)])
    amplitudes = state.reshape(-1)[valid]
    ideal = abs(amplitudes)**2
    if (not np.allclose(ideal, 1/n, atol=1e-10, rtol=0)
            or max(abs(amplitudes-amplitudes[0])) > 1e-10):
        raise ValueError('Input must prepare an exact W state')
    backward = np.zeros((n, 2**n), dtype=complex)
    backward[np.arange(n), valid] = 1
    backward = backward.reshape((n,)+(2,)*n)
    terms = {key:np.zeros(n) for key in ('single_qubit','two_qubit','relaxation','dephasing','readout')}
    tphi = 1/(1/T2-1/(2*T1))
    for t in range(len(circuit)-1, -1, -1):
        moment = circuit[t]; state = forward[t]
        bras = backward.reshape(n, -1).conj()
        project = lambda vector: bras@vector.reshape(-1)
        amp = project(state); p = abs(amp)**2
        duration = DUR_CZ if any(len(op.qubits)==2 for op in moment) else DUR_1Q
        for op in moment:
            positions = [index[q] for q in op.qubits]
            delta = np.zeros(n)
            for labels in itertools.product(range(4), repeat=len(positions)):
                if not any(labels):
                    continue
                perturbed = state
                for axis, label in zip(positions, labels):
                    if label:
                        perturbed = apply_local(perturbed, (I,X,Y,Z)[label], axis)
                delta += abs(project(perturbed))**2-p
            error_rate = rate(cal[1][op.qubits[0]]) if len(positions)==1 else edges[frozenset(op.qubits)]
            terms['single_qubit' if len(positions)==1 else 'two_qubit'] += error_rate/(4**len(positions)-1)*delta
        for axis in range(n):
            occupied = project(apply_local(state, NUMBER, axis))
            anti = np.real(amp.conj()*occupied)
            lowered = project(apply_local(state, LOWER, axis))
            terms['relaxation'] += duration/T1*(abs(lowered)**2-anti)
            terms['dephasing'] += 2*duration/tphi*(abs(occupied)**2-anti)
        for op in reversed(tuple(moment.operations)):
            backward = apply_gate(backward, op, index, batch=True, inverse=True)
    zeros = np.array([rate(cal[2][q]) for q in qs])
    ones = np.array([rate(cal[3][q]) for q in qs])
    terms['readout'] = -(ones+zeros.sum()-zeros)/n
    return ideal+sum(terms.values()), terms


if __name__ == '__main__':
    import json
    from pathlib import Path
    from .w_hardware_probe import fast_eval, judge
    from .w_cost_selection import baseline
    cal = judge.fake_calibration(13)
    circuit, qs = baseline.create_dicke_state(4, 1, *cal)
    qs = sorted(qs); valid = [1 << (3-i) for i in range(4)]
    predicted, terms = probabilities(circuit, cal)
    derivative = predicted-.25; checks = []
    old1, old2 = fast_eval.T1, fast_eval.T2
    try:
        for epsilon in (1e-2, 1e-3, 1e-4):
            scaled = [{q:(rate(v)*epsilon,0.) for q,v in d.items()} for d in cal]
            fast_eval.T1 = T1/epsilon; fast_eval.T2 = T2/epsilon
            rho = fast_eval.Rho(4)
            fast_eval.run_noisy(rho, list(circuit), {q:i for i,q in enumerate(qs)}, *scaled[:2], {q:0. for q in qs})
            actual = fast_eval.readout(rho.probs(), qs, *scaled[2:])[valid]
            measured = (actual-.25)/epsilon
            checks.append(dict(epsilon=epsilon, max_derivative_error=float(max(abs(measured-derivative))), measured=measured.tolist()))
        assert checks[-1]['max_derivative_error'] < 2e-7, checks
        assert checks[-1]['max_derivative_error'] < checks[0]['max_derivative_error']/50, checks
    finally:
        fast_eval.T1, fast_eval.T2 = old1, old2
    report = dict(status='independent four-qubit scaled-noise derivative check passed; no selection gain claimed',
                  derivative=derivative.tolist(), terms={k:v.tolist() for k,v in terms.items()}, checks=checks)
    Path(__file__).with_name('w_z_sensitivity_checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)
