"""Validate the standalone bonus checkpoint and rank one-moment score gains."""

import hashlib
import json
import math
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np

from . import submission

ROOT = Path(__file__).parent


def main():
    fallback = not hasattr(cirq_google, "Willow105")
    if fallback:
        cirq_google.Willow105 = cirq_google.engine.create_device_from_processor_id("willow_pink")
    device = cirq_google.Willow105
    rows, circuits = [], {}
    for n in range(2, 16):
        for k in range(1, n // 2 + 1):
            started = time.monotonic()
            circuit, qubits = submission.create_dicke_state_adaptive(n, k)
            seconds = time.monotonic() - started
            assert seconds < 60 and 0 < len(circuit) <= 1750
            assert len(qubits) == n and circuit.all_qubits() == set(qubits)
            assert set(qubits) <= device.metadata.qubit_set
            assert all(
                op.gate == cirq.CZ or isinstance(op.gate, cirq.PhasedXZGate)
                for op in circuit.all_operations()
            )
            device.validate_circuit(circuit)
            state = cirq.final_state_vector(
                circuit, qubit_order=sorted(qubits), dtype=np.complex128
            )
            target = np.array([i.bit_count() == k for i in range(2**n)]) / math.sqrt(
                math.comb(n, k)
            )
            overlap = np.vdot(target, state)
            error = float(np.linalg.norm(state - target * overlap / abs(overlap)))
            assert error < 1e-5, (n, k, error)
            rows.append(
                dict(
                    N=n,
                    k=k,
                    moments=len(circuit),
                    CZ=sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                    state_l2_error=error,
                    fidelity=float(abs(overlap) ** 2),
                    build_seconds=seconds,
                    contribution=n * k / len(circuit),
                    one_moment_gain=n * k / (len(circuit) * (len(circuit) - 1)),
                )
            )
            circuits[f"{n},{k}"] = circuit
    report = dict(
        cases=len(rows),
        score=sum(row["contribution"] for row in rows),
        source_sha256=hashlib.sha256((ROOT / "submission.py").read_bytes()).hexdigest(),
        cirq=cirq.__version__,
        numpy=np.__version__,
        willow_fallback=fallback,
        max_moments=max(row["moments"] for row in rows),
        max_state_l2_error=max(row["state_l2_error"] for row in rows),
        max_build_seconds=max(row["build_seconds"] for row in rows),
        rows=rows,
    )
    assert len(rows) == 56
    (ROOT / "validation.json").write_text(json.dumps(report, indent=2))
    cirq.to_json(circuits, ROOT / "circuits.json")
    (ROOT / "priorities.json").write_text(
        json.dumps(sorted(rows, key=lambda r: -r["one_moment_gain"]), indent=2)
    )
    print({key: value for key, value in report.items() if key != "rows"})


if __name__ == "__main__":
    main()
