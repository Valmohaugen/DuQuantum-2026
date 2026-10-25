"""Independent PORT025 native export of a unary-support-only permutation."""
import hashlib
import json
import math
from pathlib import Path

import cirq
import cirq_google
import numpy as np

ROOT = Path(__file__).parent
SOURCE = ROOT.parent/'bonus_clifford_screen_20261025/subspace_results.json'


def compile_schedule(source):
    arm = source['three_arm_unitary']
    order = [cirq.GridQubit(*cell) for cell in arm['logical_qubit_cells']]
    operations = []
    for entry in sorted(arm['schedule'], key=lambda entry: entry['moment']):
        op = entry['operation']
        name = op[0]
        if name == 'CZ':
            operations.append(cirq.CZ(order[op[1]], order[op[2]]))
        else:
            gate = {'H': cirq.H, 'X': cirq.X}.get(name)
            if name == 'RY':
                gate = cirq.ry(op[2])
            if gate is None:
                raise ValueError(op)
            operations.append(cirq.PhasedXZGate.from_matrix(cirq.unitary(gate)).on(order[op[1]]))
    unfused = cirq.Circuit(operations)
    pending, merged = {}, []

    def flush(q):
        if q in pending:
            matrix = pending.pop(q)
            # Do not use tolerance-based ejection or a gateset compiler.
            merged.append(cirq.PhasedXZGate.from_matrix(matrix).on(q))

    for op in operations:
        if len(op.qubits) == 1:
            q = op.qubits[0]
            pending[q] = cirq.unitary(op)@pending.get(q, np.eye(2))
        else:
            for q in op.qubits:
                flush(q)
            merged.append(op)
    for q in order:
        flush(q)
    return order, unfused, cirq.Circuit(merged)


def verify(circuit, order):
    cirq_google.Willow105.validate_circuit(circuit)
    assert all(op.gate == cirq.CZ or isinstance(op.gate, cirq.PhasedXZGate)
               for op in circuit.all_operations())
    simulator = cirq.Simulator(dtype=np.complex128)
    phase, errors = None, []
    for r in range(8):
        basis = (1 << r)-1
        target = basis if r <= 3 else int(f'{basis:07b}'[::-1], 2)
        state = simulator.simulate(circuit, qubit_order=order, initial_state=basis).final_state_vector
        if phase is None:
            phase = state[target]/abs(state[target])
        expected = np.zeros(128, dtype=np.complex128)
        expected[target] = phase
        error = float(np.linalg.norm(state-expected))
        assert error < 1e-10
        errors.append(dict(count=r, input_basis=basis, output_basis=target, common_phase_l2_error=error))
    return dict(moments=len(circuit), CZ=sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                max_common_phase_l2_error=max(r['common_phase_l2_error'] for r in errors),
                common_phase=[float(phase.real), float(phase.imag)], columns=errors)


def main():
    source = json.loads(SOURCE.read_text())
    order, unfused, merged = compile_schedule(source)
    checks = {name: verify(circuit, order) for name, circuit in [('unfused', unfused), ('merged', merged)]}
    destination = ROOT/'folded_unary_7_native.json'
    cirq.to_json(merged, destination)
    loaded = cirq.read_json(destination)
    assert loaded == merged
    report = dict(status='native supported-subspace transform verified; not a Dicke decoder',
                  source=str(SOURCE), source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
                  native=str(destination), native_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                  cirq=cirq.__version__, logical_qubit_order=[[q.row, q.col] for q in order],
                  checks=checks, device='Willow105.validate_circuit passed',
                  limitations='Only the eight unary columns are certified. No Dicke-state output is produced by this module alone. A symmetric coherent core and compatible upstream unary layout remain necessary; neither cost is included. No measurements, fitting, or maintained solver changes.')
    (ROOT/'folded_unary_native_verified.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(checks, indent=2))


if __name__ == '__main__':
    main()
