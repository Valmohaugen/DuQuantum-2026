"""Try a six-moment D(4,2) architecture ending with a native CZ matching."""

import json
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np
from scipy.optimize import minimize

from .complex_fit import circuit, objective

ROOT = Path(__file__).parent


def main():
    if not hasattr(cirq_google, "Willow105"):
        cirq_google.Willow105 = cirq_google.engine.create_device_from_processor_id("willow_pink")
    a = ((0, 1), (2, 3))
    b = ((0, 2), (1, 3))
    layers = [a, b]
    last = a
    target = np.array([i.bit_count() == 2 for i in range(16)], dtype=float) / np.sqrt(6)
    for u, v in last:
        for i in range(16):
            if i & (1 << (3 - u)) and i & (1 << (3 - v)):
                target[i] *= -1
    loss, p = objective(4, layers, target)
    rng = np.random.default_rng(202610254)
    rows = []
    started = time.monotonic()
    for restart in range(256):
        if time.monotonic() - started > 120:
            break
        result = minimize(
            loss,
            rng.uniform(-np.pi, np.pi, p),
            jac=True,
            method="L-BFGS-B",
            options=dict(maxiter=2000, gtol=1e-12, ftol=1e-16, maxcor=30),
        )
        row = dict(
            restart=restart, infidelity=float(result.fun), seconds=time.monotonic() - started
        )
        if result.fun < 1e-12:
            c = circuit(4, layers, result.x)
            qs = sorted(c.all_qubits())
            c.append(cirq.Moment(cirq.CZ(qs[u], qs[v]) for u, v in last))
            cirq_google.Willow105.validate_circuit(c)
            state = cirq.final_state_vector(c, qubit_order=qs, dtype=np.complex128)
            ideal = np.array([i.bit_count() == 2 for i in range(16)], dtype=float) / np.sqrt(6)
            phase = np.vdot(ideal, state)
            error = float(np.linalg.norm(state - ideal * phase / abs(phase)))
            row.update(moments=len(c), state_l2_error=error)
            if error < 1e-7 and len(c) < 7:
                cirq.to_json(c, ROOT / "learned_4_2.json")
                (ROOT / "learned_4_2_angles.json").write_text(
                    json.dumps(
                        dict(angles=result.x.tolist(), layers=layers, last=last, **row), indent=2
                    )
                )
                print("GAIN", row, flush=True)
        rows.append(row)
        (ROOT / "four_results.json").write_text(json.dumps(dict(rows=rows), indent=2))
        if (ROOT / "learned_4_2.json").exists():
            break
    print("DONE", len(rows), "best", min(r["infidelity"] for r in rows), flush=True)


if __name__ == "__main__":
    main()
