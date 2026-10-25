"""Architecture/angle search for an eleven-moment D(5,2) bonus circuit."""

import itertools
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
    edges = [(0, 1), (1, 2), (0, 3), (1, 4), (3, 4)]
    matchings = [
        combo
        for combo in itertools.combinations(edges, 2)
        if len({q for edge in combo for q in edge}) == 4
    ]
    patterns = [
        p
        for p in itertools.product(range(len(matchings)), repeat=5)
        if all(a != b for a, b in zip(p[:-1], p[1:]))
    ]
    rng = np.random.default_rng(202610258)
    rng.shuffle(patterns)
    target = np.array([i.bit_count() == 2 for i in range(32)], dtype=float) / np.sqrt(10)
    started = time.monotonic()
    rows = []
    for pattern in patterns:
        layers = [matchings[i] for i in pattern]
        loss, p = objective(5, layers, target)
        for restart in range(12):
            if time.monotonic() - started > 180:
                return
            result = minimize(
                loss,
                rng.uniform(-np.pi, np.pi, p),
                jac=True,
                method="L-BFGS-B",
                options=dict(maxiter=2000, gtol=1e-12, ftol=1e-16, maxcor=30),
            )
            row = dict(
                pattern=pattern,
                restart=restart,
                infidelity=float(result.fun),
                seconds=time.monotonic() - started,
            )
            if result.fun < 1e-12:
                c = circuit(5, layers, result.x)
                cirq_google.Willow105.validate_circuit(c)
                state = cirq.final_state_vector(
                    c, qubit_order=sorted(c.all_qubits()), dtype=np.complex128
                )
                phase = np.vdot(target, state)
                error = float(np.linalg.norm(state - target * phase / abs(phase)))
                row.update(moments=len(c), state_l2_error=error)
                if error < 1e-7 and len(c) < 13:
                    cirq.to_json(c, ROOT / "complex_5_2.json")
                    (ROOT / "complex_5_2_angles.json").write_text(
                        json.dumps(
                            dict(k=2, N=5, angles=result.x.tolist(), layers=layers, **row), indent=2
                        )
                    )
                    print("GAIN", row, flush=True)
            rows.append(row)
            (ROOT / "five_results.json").write_text(json.dumps(dict(rows=rows), indent=2))
            if (ROOT / "complex_5_2.json").exists():
                return
        print(
            "PATTERN",
            pattern,
            "minimum",
            min(x["infidelity"] for x in rows),
            "seconds",
            time.monotonic() - started,
            flush=True,
        )


if __name__ == "__main__":
    main()
