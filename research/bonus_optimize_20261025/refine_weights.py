"""Residual-based precision refinement after offline overlap optimization."""

import json
from pathlib import Path

import cirq
import numpy as np
from scipy.optimize import least_squares

from .complex_fit import circuit

ROOT = Path(__file__).parent


def state_vector(n, layers, angles):
    state = np.zeros(2**n, dtype=complex)
    state[0] = 1
    p = 0
    for layer in [None, *layers]:
        if layer is not None:
            for a, b in layer:
                indices = np.arange(2**n)
                both = (1 << (n - 1 - a)) | (1 << (n - 1 - b))
                state[(indices & both) == both] *= -1
        for q in range(n):
            view = state.reshape(-1, 2, 2 ** (n - 1 - q))
            for kind in [1, 0, 1]:
                angle = angles[p]
                p += 1
                if kind == 1:
                    view[:, 0, :] *= np.exp(-0.5j * angle)
                    view[:, 1, :] *= np.exp(0.5j * angle)
                else:
                    a, b = view[:, 0, :].copy(), view[:, 1, :].copy()
                    c, s = np.cos(angle / 2), np.sin(angle / 2)
                    view[:, 0, :] = c * a - s * b
                    view[:, 1, :] = s * a + c * b
    return state


def main():
    for path in ROOT.glob("complex_[0-9]*_*_angles.json"):
        row = json.loads(path.read_text())
        n, k = row.get("N", 6), row["k"]
        layers = row["layers"]
        angles = np.array(row["angles"])
        target = np.array([i.bit_count() == k for i in range(2**n)], dtype=float)
        target /= np.linalg.norm(target)
        initial = state_vector(n, layers, angles)
        compiled = cirq.final_state_vector(
            circuit(n, layers, angles),
            qubit_order=sorted(circuit(n, layers, angles).all_qubits()),
            dtype=np.complex128,
        )
        phase = np.vdot(initial, compiled)
        assert np.linalg.norm(compiled - initial * phase / abs(phase)) < 1e-12
        x0 = np.r_[angles, np.angle(np.vdot(target, initial))]

        def residual(x):
            delta = state_vector(n, layers, x[:-1]) - target * np.exp(1j * x[-1])
            return np.r_[delta.real, delta.imag]

        result = least_squares(residual, x0, ftol=1e-13, xtol=1e-13, gtol=1e-13, max_nfev=30)
        c = circuit(n, layers, result.x[:-1])
        state = cirq.final_state_vector(c, qubit_order=sorted(c.all_qubits()), dtype=np.complex128)
        phase = np.vdot(target, state)
        error = float(np.linalg.norm(state - target * phase / abs(phase)))
        assert error < 1e-10
        row.update(
            angles=result.x[:-1].tolist(),
            before_refinement_error=row["state_l2_error"],
            state_l2_error=error,
            residual_nfev=int(result.nfev),
        )
        (ROOT / f"refined_{n}_{k}_angles.json").write_text(json.dumps(row, indent=2))
        cirq.to_json(c, ROOT / f"refined_{n}_{k}.json")
        print("REFINED", k, len(c), error, flush=True)


if __name__ == "__main__":
    main()
