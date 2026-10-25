"""Warm-start complex adjoint refits after removing one native CZ gate."""

import json
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np
from scipy.optimize import minimize

from .complex_fit import objective

ROOT = Path(__file__).parent


def main():
    if not hasattr(cirq_google, "Willow105"):
        cirq_google.Willow105 = cirq_google.engine.create_device_from_processor_id("willow_pink")
    cache = cirq.read_json(ROOT / "cp_circuits.json")
    started, rows = time.monotonic(), []
    rng = np.random.default_rng(202610257)
    for n, k in [(6, 3), (6, 2), (5, 2), (7, 2)]:
        original = cache[f"{n},{k}"]
        qs = sorted(original.all_qubits())
        index = {q: i for i, q in enumerate(qs)}
        skeleton, angles = [], []
        for op in original.all_operations():
            if op.gate == cirq.CZ:
                skeleton.append((2, tuple(index[q] for q in op.qubits), -1))
            else:
                euler = cirq.deconstruct_single_qubit_matrix_into_angles(cirq.unitary(op))
                for kind, angle in zip([1, 0, 1], euler):
                    skeleton.append((kind, (index[op.qubits[0]],), len(angles)))
                    angles.append(angle)
        angles = np.array(angles)
        target = np.array([i.bit_count() == k for i in range(2**n)], dtype=float)
        target /= np.linalg.norm(target)

        def model(sequence):
            gates = [
                (kind, sum(1 << (n - 1 - q) for q in qubits), p) for kind, qubits, p in sequence
            ]
            return ([np.ascontiguousarray(x, dtype=np.int32) for x in zip(*gates)], len(angles))

        def emit(sequence, x):
            ops = []
            for kind, qubits, p in sequence:
                if kind == 2:
                    ops.append(cirq.CZ(*(qs[q] for q in qubits)))
                else:
                    ops.append((cirq.ry(x[p]) if kind == 0 else cirq.rz(x[p])).on(qs[qubits[0]]))
            c = cirq.merge_single_qubit_gates_to_phxz(cirq.Circuit(ops))
            return cirq.Circuit(cirq.drop_negligible_operations(c, atol=1e-12).all_operations())

        loss, _ = objective(n, [], target, model(skeleton))
        assert abs(loss(angles)[0]) < 1e-10
        candidates = [i for i, g in enumerate(skeleton) if g[0] == 2]
        candidates.sort(key=lambda i: len(emit(skeleton[:i] + skeleton[i + 1 :], angles)))
        for i in candidates:
            sequence = skeleton[:i] + skeleton[i + 1 :]
            loss, _ = objective(n, [], target, model(sequence))
            for restart in range(6):
                if time.monotonic() - started > 180:
                    return
                x = angles.copy()
                if restart:
                    x += rng.normal(scale=0.3 if restart < 3 else 1.2, size=len(x))
                result = minimize(
                    loss,
                    x,
                    jac=True,
                    method="L-BFGS-B",
                    options=dict(maxiter=2000, gtol=1e-12, ftol=1e-16, maxcor=30),
                )
                row = dict(
                    N=n,
                    k=k,
                    removed=i,
                    restart=restart,
                    infidelity=float(result.fun),
                    seconds=time.monotonic() - started,
                )
                if result.fun < 1e-12:
                    c = emit(sequence, result.x)
                    state = cirq.final_state_vector(c, qubit_order=qs, dtype=np.complex128)
                    phase = np.vdot(target, state)
                    error = float(np.linalg.norm(state - target * phase / abs(phase)))
                    row.update(moments=len(c), state_l2_error=error)
                    if error < 1e-7 and len(c) < len(original):
                        cirq_google.Willow105.validate_circuit(c)
                        cirq.to_json(c, ROOT / f"pruned_{n}_{k}.json")
                        print("GAIN", row, flush=True)
                rows.append(row)
                (ROOT / "prune_results.json").write_text(json.dumps(dict(rows=rows), indent=2))
            print(
                "EDGE",
                n,
                k,
                i,
                "best",
                min(
                    r["infidelity"]
                    for r in rows
                    if r["N"] == n and r["k"] == k and r["removed"] == i
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
