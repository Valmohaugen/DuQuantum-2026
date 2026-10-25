"""Portable phase/sign gauge for coherent unary-column synthesis.

This helper does not fit or change the maintained solver. The simple reference
gradient calls the supplied overlap backend once per column; no speedup claim.
"""
import numpy as np


def unary_input_angles(phases):
    """Return Rz angles in big-endian wire order, for counts0..n inclusive."""
    phases = np.asarray(phases, dtype=float)
    if phases.ndim != 1 or len(phases) < 2 or not np.isfinite(phases).all():
        raise ValueError('Supply one finite output phase for each count0..n')
    return -np.diff(phases)[::-1]


def real_column_loss(fid_grad, n, edges, theta, inputs, targets):
    """Mean per-column infidelity and its gradient for a real Ry/CZ backend."""
    f, g = [], []
    for source, target in zip(inputs, targets):
        overlap, derivative = fid_grad(n, edges, theta, (source[None], target[None]))
        f.append(overlap)
        g.append(derivative)
    f, g = np.stack(f, axis=1), np.stack(g, axis=1)
    return 1-np.mean(f*f, axis=1), -2*np.mean(f[:, :, None]*g, axis=1), f


def check():
    import hashlib
    import json
    import os
    from pathlib import Path
    import cirq
    from . import peer_synth_snapshot as synth

    assert os.environ.get('SYNTH_KERNEL') == '0'
    assert synth._kernel is None
    n = 3
    qs = cirq.LineQubit.range(n)
    edges = [(0, 1), (1, 2), (0, 1)]
    theta = np.random.default_rng(90254).normal(size=synth.n_params(n, edges))
    gates = []
    p = 0
    for kind, wires in synth.gate_list(n, edges):
        if kind == 'ry':
            gates.append(cirq.ry(theta[p])(qs[wires]))
            p += 1
        else:
            gates.append(cirq.CZ(qs[wires[0]], qs[wires[1]]))
    circuit = cirq.Circuit(gates)
    simulator = cirq.Simulator(dtype=np.complex128)
    inputs = np.eye(8)[[0, 1, 3, 7]]
    signs = np.array([1., -1., -1., 1.])
    outputs = np.stack([simulator.simulate(circuit, qubit_order=qs, initial_state=(1 << r)-1).final_state_vector.real for r in range(4)])
    targets = outputs*signs[:, None]
    loss, gradient, overlaps = real_column_loss(synth.fid_grad, n, edges, theta[None], inputs, targets)
    common, _ = synth.fid_grad(n, edges, theta[None], (inputs, targets))
    phases = np.where(overlaps[0] < 0, np.pi, 0.)
    correction = cirq.Circuit(cirq.rz(angle)(q) for q, angle in zip(qs, unary_input_angles(phases)))
    corrected = correction+circuit
    common_phase, errors = None, []
    for r in range(4):
        state = simulator.simulate(corrected, qubit_order=qs, initial_state=(1 << r)-1).final_state_vector
        overlap = np.vdot(targets[r], state)
        if common_phase is None:
            common_phase = overlap/abs(overlap)
        errors.append(float(np.linalg.norm(state-common_phase*targets[r])))
    probe = theta+.17*np.random.default_rng(90255).normal(size=len(theta))
    _, grad, _ = real_column_loss(synth.fid_grad, n, edges, probe[None], inputs, targets)
    finite = []
    epsilon = 1e-6
    for j in range(len(probe)):
        step = np.zeros_like(probe)
        step[j] = epsilon
        high = real_column_loss(synth.fid_grad, n, edges, (probe+step)[None], inputs, targets)[0][0]
        low = real_column_loss(synth.fid_grad, n, edges, (probe-step)[None], inputs, targets)[0][0]
        finite.append((high-low)/(2*epsilon))
    grad_error = float(np.max(abs(grad[0]-finite)))
    assert abs(loss[0]) < 1e-13 and abs(common[0]) < 1e-13
    assert max(errors) < 1e-12 and grad_error < 1e-7
    report = dict(status='generic real-isometry sign witness and gradient passed; no Dicke improvement claim',
        original_common_overlap=float(common[0]), phase_free_loss=float(loss[0]),
        overlaps=overlaps[0].tolist(), corrected_common_phase_errors=errors,
        gradient_error=grad_error, correction_CZ=0, correction_layers=1,
        witness_scope='Targets are sign-modified outputs of a known random real circuit, not Dicke states. This proves the gauge mechanism, not better synthesis performance.',
        relevance='The frozen peer backend optimizes square of mean overlap, imposing common sign. Mean squared individual overlaps instead allows independent signs; unary-input Z corrections restore the required coherent common phase without extra CZ.',
        limitations='Real Ry-only circuits have only sign freedom. Complex circuits permit arbitrary phases using the same difference formula. Final native all-column error remains mandatory. No pruning or fit was run.',
        peer_sha256=hashlib.sha256(Path(synth.__file__).read_bytes()).hexdigest())
    destination = Path(__file__).with_name('column_gauge_checks.json')
    destination.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    check()
