"""Offline Adam/adjoint angle learning for five-CZ-layer six-qubit states."""

import itertools
import json
import time
from pathlib import Path

import cirq
import numpy as np

from ryon import synth

ROOT = Path(__file__).parent


def main():
    started = time.monotonic()
    # All three perfect matchings of the native 2x3 grid.
    matchings = [((0, 3), (1, 4), (2, 5)), ((0, 1), (3, 4), (2, 5)), ((1, 2), (4, 5), (0, 3))]
    patterns = [
        p
        for p in itertools.product(range(3), repeat=5)
        if all(a != b for a, b in zip(p[:-1], p[1:])) and p[0] <= 1
    ]
    rng = np.random.default_rng(20261025)
    rng.shuffle(patterns)
    trials, gains = [], []
    best = {2: 13, 3: 12}
    for trial_index, pattern in enumerate(patterns):
        if time.monotonic() - started > 360:
            break
        edges = [edge for layer in pattern for edge in matchings[layer]]
        for k in [3, 2]:
            if best[k] <= 11:
                continue
            inf, theta = synth.fit(
                6, k, edges, restarts=24, iters=500, seed=trial_index * 19 + k, tol=1e-14
            )
            row = dict(k=k, pattern=pattern, infidelity=inf, seconds=time.monotonic() - started)
            trials.append(row)
            if inf < 1e-12:
                qs = [cirq.GridQubit(3 + r, 3 + c) for r in range(2) for c in range(3)]
                ops = [cirq.ry(theta[i]).on(q) for i, q in enumerate(qs)]
                for i, (a, b) in enumerate(edges):
                    ops.extend(
                        [
                            cirq.CZ(qs[a], qs[b]),
                            cirq.ry(theta[6 + 2 * i]).on(qs[a]),
                            cirq.ry(theta[7 + 2 * i]).on(qs[b]),
                        ]
                    )
                circuit = cirq.merge_single_qubit_gates_to_phxz(cirq.Circuit(ops))
                circuit = cirq.Circuit(
                    cirq.drop_negligible_operations(circuit, atol=1e-12).all_operations()
                )
                state = cirq.final_state_vector(circuit, qubit_order=qs, dtype=np.complex128)
                target = synth.dicke(6, k)
                phase = np.vdot(target, state)
                error = float(np.linalg.norm(state - target * phase / abs(phase)))
                row.update(depth=len(circuit), state_l2_error=error)
                if error < 1e-7 and len(circuit) < best[k]:
                    best[k] = len(circuit)
                    cirq.to_json(circuit, ROOT / f"fit_6_{k}.json")
                    (ROOT / f"fit_6_{k}_angles.json").write_text(
                        json.dumps(
                        dict(N=6, edges=edges, angles=theta.tolist(), **row), indent=2
                        )
                    )
                    gains.append(row)
                    print("GAIN", row, flush=True)
            print("TRIAL", row, flush=True)
            (ROOT / "layer_fit_results.json").write_text(
                json.dumps(
                    dict(
                        trials=trials,
                        improvements=gains,
                        best_depths=best,
                        seconds=time.monotonic() - started,
                    ),
                    indent=2,
                )
            )
        if all(d <= 11 for d in best.values()):
            break


if __name__ == "__main__":
    main()
