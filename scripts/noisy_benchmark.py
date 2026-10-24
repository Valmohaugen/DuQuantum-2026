"""Estimate the challenge score of dicke_prep circuits under a Willow-like noise model.

Noise model (per moment, density-matrix simulation):
  * CZ: two-qubit depolarizing with the calibrated Pauli error rate.
  * PhasedXZ: single-qubit depolarizing with the calibrated rate.
  * Idle/every moment: amplitude damping (T1) and pure dephasing (T_phi) for its duration.
  * Optional quasi-static detuning (random Z rotation rate per qubit, fixed per
    realization) - the low-frequency noise that dynamical decoupling targets.
  * Readout: asymmetric classical flips from zero_errors / one_errors.
Scores use the notebook's own overall_score (exec'd from the .ipynb).

Usage: python -u scripts/noisy_benchmark.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cirq
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import dicke_prep as dp  # noqa: E402
from test_dicke_prep import fake_calibration  # noqa: E402


@dataclass(frozen=True)
class NoiseConfig:
    t1_us: float = 68.0  # Willow spec-sheet mean T1 [us]
    tphi_us: float = 100.0  # pure dephasing time [us]
    t_1q_ns: float = 25.0  # single-qubit moment duration [ns]
    t_cz_ns: float = 42.0  # CZ moment duration [ns]
    detuning_khz: float = 0.0  # std of quasi-static detuning [kHz]
    n_realizations: int = 2  # detuning samples averaged (if detuning > 0)
    shots: int = 10_000
    max_correlator_size: int = 4
    seed: int = 7


def load_scoring():
    """Exec the notebook's scoring cell so we use the exact official functions."""
    nb = json.loads((ROOT / "Google Quantum AI Challenge.ipynb").read_text())
    ns: dict = {}
    exec("import itertools, math\nimport numpy as np", ns)
    for cell in nb["cells"]:
        src = "".join(cell["source"])
        if cell["cell_type"] == "code" and "def overall_score" in src:
            exec(src, ns)
    return ns["overall_score"]


def noisy_circuit(circuit, qubits, cal, cfg: NoiseConfig, detuning: dict):
    cz_err = {frozenset(p): e for p, (e, _) in cal[0].items()}
    sq_err = {q: e for q, (e, _) in cal[1].items()}
    out = cirq.Circuit()
    for moment in circuit:
        out.append(moment)
        is_cz = any(len(op.qubits) == 2 for op in moment)
        dt_us = (cfg.t_cz_ns if is_cz else cfg.t_1q_ns) * 1e-3
        gate_noise = []
        for op in moment:
            if len(op.qubits) == 2:
                gate_noise.append(cirq.depolarize(cz_err[frozenset(op.qubits)], n_qubits=2).on(*op.qubits))
            else:
                gate_noise.append(cirq.depolarize(sq_err[op.qubits[0]]).on(*op.qubits))
        # explicit Moments so noise stays attached to this time step
        out.append(cirq.Moment(gate_noise))
        out.append(cirq.Moment(cirq.amplitude_damp(1 - np.exp(-dt_us / cfg.t1_us)).on_each(*qubits)))
        out.append(cirq.Moment(cirq.phase_damp(1 - np.exp(-2 * dt_us / cfg.tphi_us)).on_each(*qubits)))
        if detuning:
            out.append(cirq.Moment(cirq.rz(2 * np.pi * detuning[q] * 1e-3 * dt_us).on(q) for q in qubits))
    return out


def apply_readout(probs: np.ndarray, order, cal) -> np.ndarray:
    """Apply per-qubit asymmetric confusion matrices to a probability vector."""
    n = len(order)
    p = probs.reshape([2] * n)
    for i, q in enumerate(order):
        e0 = cal[2].get(q, (0.0, 0))[0]
        e1 = cal[3].get(q, (0.0, 0))[0]
        conf = np.array([[1 - e0, e1], [e0, 1 - e1]])
        p = np.moveaxis(np.tensordot(conf, p, axes=([1], [i])), 0, i)
    return p.reshape(-1)


def sample_bits(probs, n, shots, rng):
    probs = np.clip(probs.real, 0, None)
    idx = rng.choice(len(probs), size=shots, p=probs / probs.sum())
    return ((idx[:, None] >> np.arange(n - 1, -1, -1)) & 1).astype(int)


def score_instance(n, k, cal, cfg: NoiseConfig, overall_score, prep_cfg=dp.CONFIG):
    rng = np.random.default_rng(cfg.seed)
    circuit, qset = dp.create_dicke_state(n, k, *cal, config=prep_cfg)
    order = sorted(qset)
    reals = cfg.n_realizations if cfg.detuning_khz > 0 else 1
    pz = px = 0
    sim = cirq.DensityMatrixSimulator(dtype=np.complex128)
    for _ in range(reals):
        det = {q: rng.normal(0, cfg.detuning_khz) for q in order} if cfg.detuning_khz else {}
        rho = sim.simulate(noisy_circuit(circuit, order, cal, cfg, det), qubit_order=order).final_density_matrix
        h = cirq.unitary(cirq.Circuit(cirq.H.on_each(*order)))
        pz = pz + np.diag(rho) / reals
        px = px + np.diag(h @ rho @ h.conj().T) / reals
    zb = sample_bits(apply_readout(pz, order, cal), n, cfg.shots, rng)
    xb = sample_bits(apply_readout(px, order, cal), n, cfg.shots, rng)
    mcs = min(cfg.max_correlator_size, n)
    return overall_score(zb, xb, k, mcs), len(circuit)


def main() -> None:
    sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    print(f"[setup] cirq {cirq.__version__}, numpy {np.__version__}, git {sha}, calibration seed 1234")
    overall_score = load_scoring()
    cal = fake_calibration(1234)
    cases = [(n, k) for n in range(2, 9) for k in range(1, n // 2 + 1)]
    noisy = NoiseConfig(detuning_khz=20.0)
    with_dd = dp.PrepConfig(use_dynamical_decoupling=True)
    without_dd = dp.PrepConfig(use_dynamical_decoupling=False)
    clean_cal = tuple({key: (0.0, 0) for key in m} for m in cal)
    noiseless = NoiseConfig(t1_us=1e12, tphi_us=1e12)
    print(f"{'N':>3} {'n':>3} {'moments':>8} {'score(dd)':>10} {'score(noDD)':>12}  ideal-shot-noise")
    tot = {"dd": 0.0, "no-dd": 0.0, "ideal": 0.0}
    for n, k in cases:
        s_dd, mom = score_instance(n, k, cal, noisy, overall_score, with_dd)
        s_nodd, _ = score_instance(n, k, cal, noisy, overall_score, without_dd)
        s_ideal, _ = score_instance(n, k, clean_cal, noiseless, overall_score)
        tot["dd"] += s_dd
        tot["no-dd"] += s_nodd
        tot["ideal"] += s_ideal
        print(f"{n:>3} {k:>3} {mom:>8} {s_dd:>10.3f} {s_nodd:>12.3f}  {s_ideal:>8.3f}")
    print(f"[done] totals: dd={tot['dd']:.2f}  no-dd={tot['no-dd']:.2f}  ideal={tot['ideal']:.2f}")


if __name__ == "__main__":
    main()
