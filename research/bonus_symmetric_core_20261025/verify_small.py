"""Independent Cirq all-column certificate for the successful n3 prototype."""
import hashlib
import json
import math
from pathlib import Path

import cirq
import cirq_google
import numpy as np

ROOT = Path(__file__).parent


def main():
    results = json.loads((ROOT/'continuation_results.json').read_text())
    row = min((r for r in results['rows'] if r['n'] == 3),
              key=lambda r: (r['core_CZ'], r['max_phase_aligned_error']))
    qs = [cirq.GridQubit(i, 7) for i in range(3)]
    phases = [row['column_phases'][min(r, 3-r)] for r in range(4)]
    logical = []
    for r in range(1, 4):
        logical.append(cirq.rz(-(phases[r]-phases[r-1]))(qs[3-r]))
    a, c, b = qs
    logical += [cirq.CNOT(a, b), cirq.ry(math.pi/4)(a), cirq.CNOT(c, a),
                cirq.ry(math.pi/4)(a), cirq.CNOT(b, a), cirq.ry(-math.pi/4)(a),
                cirq.CNOT(c, a), cirq.ry(-math.pi/4)(a), cirq.CNOT(a, b)]
    core_ops = []
    for gate in row['gates']:
        wires = [qs[i] for i in gate['qubits']]
        if gate['kind'] == 'CZ':
            core_ops.append(cirq.CZ(*wires))
        elif len(wires) == 2:
            assert gate['kind'] == 'X' and gate['fixed'] == math.pi/2
            core_ops += [cirq.H(wires[0]), cirq.H(wires[1]),
                         cirq.S(wires[0]), cirq.S(wires[1]), cirq.CZ(*wires),
                         cirq.H(wires[0]), cirq.H(wires[1])]
        else:
            theta = row['angles'][gate['parameter']]
            core_ops.append((cirq.rx(theta) if gate['kind'] == 'X' else cirq.ry(theta))(wires[0]))
    logical += core_ops
    # Explicit remote-CX bridge preserves the dirty intermediate qubit.
    routed = []
    for op in logical:
        if op.gate == cirq.CNOT and abs(op.qubits[0].row-op.qubits[1].row) == 2:
            control, target = op.qubits
            middle = qs[1]
            routed += [cirq.CNOT(control, middle), cirq.CNOT(middle, target),
                       cirq.CNOT(control, middle), cirq.CNOT(middle, target)]
        else:
            routed.append(op)
    native_ops = []
    for op in routed:
        native_ops += ([cirq.H(op.qubits[1]), cirq.CZ(*op.qubits), cirq.H(op.qubits[1])]
                       if op.gate == cirq.CNOT else [op])
    pending, output = {}, []

    def flush(q):
        if q in pending:
            output.append(cirq.PhasedXZGate.from_matrix(pending.pop(q)).on(q))

    for op in native_ops:
        if len(op.qubits) == 1:
            q = op.qubits[0]
            pending[q] = cirq.unitary(op)@pending.get(q, np.eye(2))
        else:
            for q in op.qubits:
                flush(q)
            output.append(op)
    for q in qs:
        flush(q)
    circuit = cirq.Circuit(output)
    cirq_google.Willow105.validate_circuit(circuit)
    assert all(op.gate == cirq.CZ or isinstance(op.gate, cirq.PhasedXZGate)
               for op in circuit.all_operations())
    simulator = cirq.Simulator(dtype=np.complex128)
    common_phase, checks = None, []
    for r in range(4):
        target = np.array([int(i.bit_count() == r) for i in range(8)])/math.sqrt(math.comb(3, r))
        state = simulator.simulate(circuit, qubit_order=qs, initial_state=(1 << r)-1).final_state_vector
        overlap = np.vdot(target, state)
        if common_phase is None:
            common_phase = overlap/abs(overlap)
        error = float(np.linalg.norm(state-common_phase*target))
        assert error < 1e-10
        checks.append(dict(count=r, common_phase_l2_error=error))
    destination = ROOT/'full3_native.json'
    cirq.to_json(circuit, destination)
    report = dict(status='all-count native n3 feasibility decoder verified; not integrated',
        source_results_sha256=hashlib.sha256((ROOT/'continuation_results.json').read_bytes()).hexdigest(),
        selected=dict(n=3, cycles=row['cycles'], seed=row['seed']), core_CZ=row['core_CZ'],
        full_native_CZ=sum(op.gate == cirq.CZ for op in circuit.all_operations()),
        full_native_moments=len(circuit), physical_qubits=[[q.row, q.col] for q in qs],
        checks=checks, max_common_phase_l2_error=max(r['common_phase_l2_error'] for r in checks),
        native_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        phase_correction='Input Rz differences cancel all count phases before the folded transform; one shared output phase is fitted from r0 only.',
        scope='Proof of a complete small decoder for this family, not a depth improvement. N5 attempts failed even at36/45 coreCZ. No N7 fit, maintained solver edit, or portfolio change.')
    (ROOT/'full3_verified.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
