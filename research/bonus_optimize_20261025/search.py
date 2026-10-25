"""Bonus-only search over exact collective phases, compilation and schedules."""

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np

from .commuting_schedule import schedule

ROOT = Path(__file__).parent
BASE = ROOT.parent / "bonus_priority_20261025"


def inverse(circuit):
    return cirq.Circuit(
        cirq.Moment(op if op.gate == cirq.CZ else cirq.inverse(op) for op in moment)
        for moment in reversed(circuit)
    )


def compact(circuit):
    for _ in range(2):
        circuit = cirq.eject_z(circuit)
        circuit = cirq.eject_phased_paulis(circuit)
        circuit = cirq.merge_single_qubit_gates_to_phxz(circuit)
        circuit = cirq.drop_negligible_operations(circuit, atol=1e-12)
        circuit = cirq.Circuit(circuit.all_operations())
    return circuit


def error(circuit, n, k):
    qubits = sorted(circuit.all_qubits())
    assert len(qubits) == n
    assert all(
        op.gate == cirq.CZ or isinstance(op.gate, cirq.PhasedXZGate)
        for op in circuit.all_operations()
    )
    cirq_google.Willow105.validate_circuit(circuit)
    state = cirq.final_state_vector(circuit, qubit_order=qubits, dtype=np.complex128)
    target = np.array([i.bit_count() == k for i in range(2**n)]) / math.sqrt(math.comb(n, k))
    overlap = np.vdot(target, state)
    return float(np.linalg.norm(state - target * overlap / abs(overlap)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=240)
    args = parser.parse_args()
    if not hasattr(cirq_google, "Willow105"):
        cirq_google.Willow105 = cirq_google.engine.create_device_from_processor_id("willow_pink")
    circuits = cirq.read_json(BASE / "circuits.json")
    original = {key: len(circuit) for key, circuit in circuits.items()}
    baseline_rows = {
        f"{r['N']},{r['k']}": r for r in json.loads((BASE / "validation.json").read_text())["rows"]
    }
    keys = sorted(circuits, key=lambda key: -baseline_rows[key]["one_moment_gain"])
    started = time.monotonic()
    trials, gains, coverage = 0, [], []
    for key in keys:
        if time.monotonic() - started >= args.seconds:
            break
        n, k = map(int, key.split(","))
        c = circuits[key]
        qs = sorted(c.all_qubits())
        phases = {0.0, 0.5, -0.5, 1.0, -0.25, 0.25}
        last = {}
        for op in c.all_operations():
            if len(op.qubits) == 1:
                last[op.qubits[0]] = op.gate
        phases.update(
            round(-g.z_exponent % 2, 12)
            for g in last.values()
            if isinstance(g, cirq.PhasedXZGate) and abs(g.x_exponent % 2) < 1e-10
        )
        count = 0
        for phase in sorted(phases, key=lambda p: (abs(p), p)):
            if time.monotonic() - started >= args.seconds:
                break
            # Collective Z(t) acts as exp(i*pi*t*k) on every weight-k basis state.
            trial = c.copy()
            if phase:
                trial.append(cirq.Moment(cirq.Z(q) ** phase for q in qs))
            trial = compact(trial)
            options = [
                trial,
                schedule(trial, restarts=6),
                inverse(schedule(inverse(trial), restarts=6)),
            ]
            trial = min(options, key=len)
            trials += 1
            count += 1
            if len(trial) >= len(circuits[key]):
                continue
            state_error = error(trial, n, k)
            if state_error > max(1e-10, 1.1 * baseline_rows[key]["state_l2_error"]):
                continue
            before = len(circuits[key])
            circuits[key] = trial
            row = dict(
                N=n,
                k=k,
                before=before,
                moments=len(trial),
                phase=phase,
                state_l2_error=state_error,
                gain=n * k * (1 / len(trial) - 1 / before),
            )
            gains.append(row)
            print("GAIN", row, flush=True)
            cirq.to_json(circuits, ROOT / "circuits.json")
        coverage.append(
            dict(case=key, trials=count, before=original[key], after=len(circuits[key]))
        )
        report = dict(
            baseline_score=sum(
                int(key.split(",")[0]) * int(key.split(",")[1]) / d for key, d in original.items()
            ),
            score=sum(
                int(key.split(",")[0]) * int(key.split(",")[1]) / len(c)
                for key, c in circuits.items()
            ),
            trials=trials,
            seconds=time.monotonic() - started,
            improvements=gains,
            coverage=coverage,
            baseline_sha256=hashlib.sha256((BASE / "circuits.json").read_bytes()).hexdigest(),
        )
        (ROOT / "results.json").write_text(json.dumps(report, indent=2))
        print(key, "depth", len(circuits[key]), "trials", count, flush=True)
    cirq.to_json(circuits, ROOT / "circuits.json")


if __name__ == "__main__":
    main()
