"""Offline complex single-qubit angle learning for fixed shallow CZ layers."""

import ctypes
import itertools
import json
import subprocess
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).parent


def structure(n, layers):
    gates, p = [], 0
    for layer in [None, *layers]:
        if layer is not None:
            gates.extend((2, (1 << (n - 1 - a)) | (1 << (n - 1 - b)), -1) for a, b in layer)
        for q in range(n):
            for kind in [1, 0, 1]:
                gates.append((kind, 1 << (n - 1 - q), p))
                p += 1
    return [np.ascontiguousarray(x, dtype=np.int32) for x in zip(*gates)], p


def objective(n, layers, target, compiled=None):
    cache = ROOT / "__pycache__"
    cache.mkdir(exist_ok=True)
    libpath = cache / "complex_kernel.so"
    if (
        not libpath.exists()
        or libpath.stat().st_mtime < (ROOT / "complex_kernel.c").stat().st_mtime
    ):
        subprocess.run(
            [
                "gcc",
                "-O3",
                "-shared",
                "-fPIC",
                str(ROOT / "complex_kernel.c"),
                "-o",
                str(libpath),
                "-lm",
            ],
            check=True,
        )
    fn = ctypes.CDLL(str(libpath.resolve())).loss_grad
    ints = np.ctypeslib.ndpointer(dtype=np.int32, flags="C_CONTIGUOUS")
    doubles = np.ctypeslib.ndpointer(dtype=np.float64, flags="C_CONTIGUOUS")
    fn.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ints,
        ints,
        ints,
        doubles,
        ctypes.c_int,
        doubles,
        doubles,
    ]
    fn.restype = ctypes.c_double
    (kinds, masks, parameters), size = structure(n, layers) if compiled is None else compiled
    target = np.ascontiguousarray(target, dtype=float)

    def loss(x):
        x = np.ascontiguousarray(x, dtype=float)
        gradient = np.empty_like(x)
        value = fn(n, len(kinds), kinds, masks, parameters, x, size, target, gradient)
        return value, gradient

    return loss, size


def circuit(n, layers, angles):
    qs = [cirq.GridQubit(3 + r, 3 + c) for r in range(2) for c in range(3)][:n]
    if n == 4:
        qs = list(cirq.GridQubit.rect(2, 2, top=3, left=3))
    operations, p = [], 0
    for layer in [None, *layers]:
        if layer is not None:
            operations.extend(cirq.CZ(qs[a], qs[b]) for a, b in layer)
        for q in qs:
            operations.extend(
                [
                    cirq.rz(angles[p]).on(q),
                    cirq.ry(angles[p + 1]).on(q),
                    cirq.rz(angles[p + 2]).on(q),
                ]
            )
            p += 3
    c = cirq.merge_single_qubit_gates_to_phxz(cirq.Circuit(operations), atol=1e-13)
    return cirq.Circuit(cirq.drop_negligible_operations(c, atol=1e-12).all_operations())


def check_gradients():
    layers = [((0, 1),), ((1, 2),)]
    target = np.array([i.bit_count() == 1 for i in range(8)], dtype=float) / np.sqrt(3)
    loss, p = objective(3, layers, target)
    x = np.random.default_rng(117).normal(size=p)
    value, gradient = loss(x)
    for j in range(p):
        plus, minus = x.copy(), x.copy()
        plus[j] += 1e-5
        minus[j] -= 1e-5
        assert abs((loss(plus)[0] - loss(minus)[0]) / 2e-5 - gradient[j]) < 1e-7
    c = circuit(3, layers, x)
    state = cirq.final_state_vector(c, qubit_order=sorted(c.all_qubits()), dtype=np.complex128)
    assert abs(value - (1 - abs(np.vdot(target, state)) ** 2)) < 1e-12


def main():
    check_gradients()
    if not hasattr(cirq_google, "Willow105"):
        cirq_google.Willow105 = cirq_google.engine.create_device_from_processor_id("willow_pink")
    matchings = [((0, 3), (1, 4), (2, 5)), ((0, 1), (3, 4), (2, 5)), ((1, 2), (4, 5), (0, 3))]
    patterns = [
        p
        for p in itertools.product(range(3), repeat=5)
        if p[0] <= 1 and all(a != b for a, b in zip(p[:-1], p[1:]))
    ]
    rng = np.random.default_rng(202610253)
    rng.shuffle(patterns)
    best, rows = {2: 13, 3: 12}, []
    started = time.monotonic()
    for pattern in patterns:
        layers = [matchings[i] for i in pattern]
        for k in [3, 2]:
            if best[k] <= 11:
                continue
            target = np.array([i.bit_count() == k for i in range(64)], dtype=float)
            target /= np.linalg.norm(target)
            loss, p = objective(6, layers, target)
            for restart in range(12):
                if time.monotonic() - started > 360:
                    return
                result = minimize(
                    loss,
                    rng.uniform(-np.pi, np.pi, p),
                    jac=True,
                    method="L-BFGS-B",
                    options=dict(maxiter=2000, gtol=1e-12, ftol=1e-16, maxcor=30),
                )
                row = dict(
                    k=k,
                    pattern=pattern,
                    restart=restart,
                    infidelity=float(result.fun),
                    seconds=time.monotonic() - started,
                )
                if result.fun < 1e-12:
                    c = circuit(6, layers, result.x)
                    cirq_google.Willow105.validate_circuit(c)
                    state = cirq.final_state_vector(
                        c, qubit_order=sorted(c.all_qubits()), dtype=np.complex128
                    )
                    overlap = np.vdot(target, state)
                    error = float(np.linalg.norm(state - target * overlap / abs(overlap)))
                    row.update(moments=len(c), state_l2_error=error)
                    if error < 1e-7 and len(c) < best[k]:
                        best[k] = len(c)
                        cirq.to_json(c, ROOT / f"complex_6_{k}.json")
                        (ROOT / f"complex_6_{k}_angles.json").write_text(
                            json.dumps(
                                dict(angles=result.x.tolist(), layers=layers, **row), indent=2
                            )
                        )
                        print("GAIN", row, flush=True)
                rows.append(row)
                (ROOT / "complex_results.json").write_text(
                    json.dumps(
                        dict(rows=rows, best_depths=best, seconds=time.monotonic() - started),
                        indent=2,
                    )
                )
                if best[k] <= 11:
                    break
        if all(d <= 11 for d in best.values()):
            break
        print("PATTERN", pattern, "best", best, "seconds", time.monotonic() - started, flush=True)


if __name__ == "__main__":
    main()
