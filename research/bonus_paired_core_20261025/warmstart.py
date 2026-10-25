"""Exact logical folded-input warm start; physical routing is separate."""
import hashlib
import json
import math
import os
import time
from pathlib import Path

import cirq
import numpy as np
from scipy.optimize import least_squares
from . import peer_synth_snapshot as synth
from .paired_core_objective import PairedCore

ROOT = Path(__file__).parent


def folded_permutation(qs):
    n = len(qs)
    c = qs[n//2]
    operations = []
    for i in range(n//2):
        a, b = qs[i], qs[n-1-i]
        operations += [cirq.CNOT(a, b), cirq.ry(math.pi/4)(a), cirq.CNOT(c, a),
                       cirq.ry(math.pi/4)(a), cirq.CNOT(b, a), cirq.ry(-math.pi/4)(a),
                       cirq.CNOT(c, a), cirq.ry(-math.pi/4)(a), cirq.CNOT(a, b)]
    return cirq.Circuit(operations)


def real_ops(qs, edges, angles, zset):
    operations = []
    p = 0
    for kind, wires in synth.gate_list(len(qs), edges):
        if kind == 'ry':
            operations.append(cirq.ry(angles[p])(qs[wires]))
            p += 1
        else:
            operations.append(cirq.CZ(qs[wires[0]], qs[wires[1]]))
    operations.extend(cirq.Z(qs[q]) for q in zset)
    return operations


def output_signs(n, zset):
    return np.array([(-1.)**sum((b >> (n-1-q)) & 1 for q in zset) for b in range(1 << n)])


def objective_for(n, left_edges, right_edges, zset):
    objective = PairedCore(n, left_edges, right_edges)
    # Both fixed output-Z frames are identical. Absorb their action into the
    # target bras; this does not change the physical target or root amplitudes.
    objective.targets *= output_signs(n, zset)[None, :]
    return objective


def main():
    assert os.environ.get('SYNTH_KERNEL') == '0' and synth._kernel is None
    source = json.loads((ROOT/'full5_source.json').read_text())
    n = source['n']
    inputs = np.eye(1 << n)[[(1 << r)-1 for r in range(n+1)]]
    targets = np.array([synth.dicke(n, r) for r in range(n+1)])*output_signs(n, source['zset'])
    original = np.array(source['angles'])
    original_output = synth.run(n, source['edges'], original[None], inputs)[0]
    sign = np.sign(np.sum(targets*original_output))
    targets *= sign
    original_error = float(np.max(np.linalg.norm(original_output-targets, axis=1)))
    assert original_error < 1e-5
    tick = time.monotonic()

    def precision_residual(x):
        if time.monotonic()-tick > 10:
            raise RuntimeError('fixed-topology precision repair exceeded10s')
        return (synth.run(n, source['edges'], x[None], inputs)[0]-targets).ravel()

    polished = least_squares(precision_residual, original, max_nfev=20,
                            gtol=1e-13, xtol=1e-13, ftol=1e-13)
    source['angles'] = polished.x.tolist()
    repaired_error = float(np.max(np.linalg.norm(precision_residual(polished.x).reshape(n+1, -1), axis=1)))
    assert repaired_error < 1e-10
    precision = dict(original_max_error=original_error, repaired_max_error=repaired_error,
                     seconds=time.monotonic()-tick, evaluations=polished.nfev,
                     scope='Fixed supplied37CZ topology; coefficient precision repair only')
    (ROOT/'full5_polished.json').write_text(json.dumps(source, indent=2)+'\n')
    qs = cirq.LineQubit.range(n)
    decoder = cirq.Circuit(real_ops(qs, source['edges'], source['angles'], source['zset']))
    fold = folded_permutation(qs)
    logical = cirq.inverse(fold)+decoder
    # Translate CX to real single-qubit rotations around one CZ, exactly.
    operations = []
    for op in logical.all_operations():
        if op.gate == cirq.CNOT:
            c, t = op.qubits
            operations += [cirq.ry(-math.pi/2)(t), cirq.CZ(c, t), cirq.ry(math.pi/2)(t)]
        else:
            operations.append(op)
    edges, angles, zset = synth.from_ops(operations, qs)
    compiled = cirq.Circuit(real_ops(qs, edges, angles, zset))
    simulator = cirq.Simulator(dtype=np.complex128)
    common_phase, checks = None, []
    for s in range(n//2+1):
        for branch in (0, 1):
            basis = ((1 << s)-1) ^ (((1 << n)-1) if branch else 0)
            count = n-s if branch else s
            target = synth.dicke(n, count)
            state = simulator.simulate(compiled, qubit_order=qs, initial_state=basis).final_state_vector
            overlap = np.vdot(target, state)
            if common_phase is None:
                common_phase = overlap/abs(overlap)
            error = float(np.linalg.norm(state-common_phase*target))
            assert error < 1e-10
            checks.append(dict(seed_count=s, branch=branch, output_count=count, common_phase_error=error))
    objective = objective_for(n, edges, edges, zset)
    x = np.r_[angles, angles]
    overlap, gradient = objective.overlap_gradient(x)
    left, right = objective.outputs(x)
    signs = output_signs(n, zset)
    left, right = left*signs, right*signs
    full = sum((w*np.kron(left[j], right[objective.partner[j]]) for j, w in enumerate(objective.weights)),
               start=np.zeros(1 << (2*n)))
    target = synth.dicke(2*n, n)
    direct_overlap = float(np.dot(target, full))
    error = float(np.linalg.norm(full-target*np.sign(direct_overlap)))
    assert error < 1e-10 and abs(overlap-direct_overlap) < 1e-12
    report = dict(status='exact logical paired-core warm start verified; not routed or scored', n=n,
        source_sha256=hashlib.sha256((ROOT/'full5_source.json').read_bytes()).hexdigest(),
        edges=edges, angles=angles.tolist(), zset=zset, original_decoder_CZ=len(source['edges']),
        folded_core_CZ=len(edges), column_checks=checks, full_target_qubits=2*n,
        precision_repair=precision,
        full_state_error=error, compressed_overlap=overlap, direct_overlap=direct_overlap,
        gradient_max=float(np.max(abs(gradient))),
        limitation='Logical5-site cores contain nonadjacent edges. This10-qubit check starts from the ideal folded root vector; no native root or full-device circuit is claimed. Physical routing and complete constructor cost remain acceptance gates.')
    (ROOT/'warmstart.json').write_text(json.dumps(report, indent=2)+'\n')
    cirq.to_json(compiled, ROOT/'warmstart_logical_core.json')
    print(json.dumps({k: v for k, v in report.items() if k not in ('edges', 'angles')}, indent=2))


if __name__ == '__main__':
    main()
