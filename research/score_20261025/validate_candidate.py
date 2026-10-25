"""Independent native/device/complex-state validation through N=15."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import cirq
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ryon"))
import judge  # noqa: E402
from test_dicke import check_rules  # noqa: E402

spec = importlib.util.spec_from_file_location("candidate", ROOT / "toby/calibrated_score_sol.py")
candidate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(candidate)


def validate(circuit, qubits, N, k, cal=None):
    assert len(qubits) == N
    full = sorted(circuit.all_qubits())
    assert set(full) == set(qubits), "this candidate should use no ancillary qubits"
    for op in circuit.all_operations():
        assert op.gate == cirq.CZ or isinstance(op.gate, cirq.PhasedXZGate)
    judge.get_device().validate_circuit(circuit)
    if cal is not None:
        assert not check_rules(circuit, qubits, N, cal[0], cal[1])
    assert len(circuit) <= 1750
    state = cirq.final_state_vector(circuit, qubit_order=full, dtype=np.complex128)
    target = np.array([int(i.bit_count() == k) for i in range(2**N)], dtype=float) / math.sqrt(
        math.comb(N, k)
    )
    overlap = np.vdot(target, state)
    error = float(np.linalg.norm(state - target * overlap / abs(overlap)))
    assert error < 1e-5, (N, k, error)
    return dict(
        N=N,
        k=k,
        state_l2=error,
        moments=len(circuit),
        cz=sum(len(op.qubits) == 2 for op in circuit.all_operations()),
    )


def run():
    rows = []
    source_sha256 = hashlib.sha256((ROOT / "toby/calibrated_score_sol.py").read_bytes()).hexdigest()
    cal = judge.fake_calibration(51000)
    for mode in ("main", "bonus"):
        for N in range(2, 16):
            weights = range(N + 1) if mode == "main" else range(1, N // 2 + 1)
            for k in weights:
                started = time.monotonic()
                if mode == "main":
                    circuit, qubits = candidate.create_dicke_state(N, k, *cal)
                else:
                    circuit, qubits = candidate.create_dicke_state_adaptive(N, k)
                elapsed = time.monotonic() - started
                assert elapsed < 60, (mode, N, k, elapsed)
                row = validate(circuit, qubits, N, k, cal if mode == "main" else None)
                row.update(mode=mode, build_seconds=elapsed)
                rows.append(row)
                print(json.dumps(row), flush=True)
                Path(__file__).with_name("candidate_validation.json").write_text(
                    json.dumps(dict(source_sha256=source_sha256, rows=rows), indent=2) + "\n"
                )
    return rows


if __name__ == "__main__":
    rows = run()
    print(
        json.dumps(
            dict(
                circuits=len(rows),
                max_l2=max(r["state_l2"] for r in rows),
                max_build=max(r["build_seconds"] for r in rows),
                bonus_score=sum(
                    r["N"] * r["k"] / r["moments"] for r in rows if r["mode"] == "bonus"
                ),
            )
        ),
        flush=True,
    )
