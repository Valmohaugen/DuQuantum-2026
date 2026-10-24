"""Estimate the challenge score of dicke_prep circuits under a Willow-like noise model.

Noise model (per moment, density-matrix simulation):
  * CZ: two-qubit depolarizing with the calibrated Pauli error rate.
  * PhasedXZ: single-qubit depolarizing with the calibrated rate.
  * Idle/every moment: amplitude damping (T1) and pure dephasing (T_phi) for its duration.
  * Optional quasi-static detuning (random Z rotation rate per qubit, fixed per
    realization) - the low-frequency noise that dynamical decoupling targets.
  * Readout: asymmetric classical flips from zero_errors / one_errors.
Scores use the notebook's own overall_score (exec'd from the .ipynb).

Usage: python -u claude/scripts/noisy_benchmark.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import cirq
import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # claude/
REPO = ROOT.parent  # holds the challenge notebook
OUTPUT_DIR = REPO / "benchmark_outputs"
CHECKPOINT_PATH = OUTPUT_DIR / "noisy_benchmark_checkpoint.json"
RESULTS_PATH = OUTPUT_DIR / "noisy_benchmark_results.json"
RESUME_FROM_CHECKPOINT = True
sys.path.insert(0, str(ROOT))  # claude/dicke_prep.py loads the notebook's solution
sys.path.insert(0, str(ROOT / "scripts"))
import dicke_prep as dp  # noqa: E402
from challenge_calibration import make_challenge_calibration  # noqa: E402

# Edit these values to control the automated comparison.
CALIBRATION_SEED = 1234
BENCHMARK_SEEDS = tuple(range(1, 6))
BENCHMARK_CASES = tuple(
    (n, k) for n in range(2, 9) for k in range(1, n // 2 + 1)
)
DETONING_KHZ = 20.0
SHOTS = 10_000
RUN_IDEAL_BASELINE = True


@dataclass(frozen=True)
class NoiseConfig:
    t1_us: float = 68.0  # Willow spec-sheet mean T1 [us]
    tphi_us: float = 100.0  # pure dephasing time [us]
    t_1q_ns: float = 25.0  # single-qubit moment duration [ns]
    t_cz_ns: float = 42.0  # CZ moment duration [ns]
    detuning_khz: float = 0.0  # std of quasi-static detuning [kHz]
    n_realizations: int = 2  # detuning samples averaged (if detuning > 0)
    shots: int = SHOTS
    max_correlator_size: int = 4
    seed: int = 7


def load_scoring():
    """Exec the notebook's scoring cell so we use the exact official functions."""
    nb = json.loads((REPO / "Google Quantum AI Challenge.ipynb").read_text())
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


def mean_and_std(scores: list[float]) -> tuple[float, float]:
    values = np.asarray(scores, dtype=float)
    return float(values.mean()), float(values.std(ddof=1)) if len(values) > 1 else 0.0


def benchmark_signature() -> dict:
    """Return settings that make checkpointed scores reproducible."""
    return {
        "calibration_seed": CALIBRATION_SEED,
        "benchmark_seeds": list(BENCHMARK_SEEDS),
        "benchmark_cases": [list(case) for case in BENCHMARK_CASES],
        "detuning_khz": DETONING_KHZ,
        "shots": SHOTS,
        "run_ideal_baseline": RUN_IDEAL_BASELINE,
    }


def atomic_write_json(path: Path, payload: dict) -> None:
    """Write JSON through a temporary file so interruption cannot corrupt it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def load_checkpoint(signature: dict) -> dict:
    """Load compatible checkpoint data, or return an empty result set."""
    if not RESUME_FROM_CHECKPOINT or not CHECKPOINT_PATH.exists():
        return {"signature": signature, "results": {}}
    try:
        checkpoint = json.loads(CHECKPOINT_PATH.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[warn] ignoring unreadable checkpoint: {exc}")
        return {"signature": signature, "results": {}}
    if checkpoint.get("signature") != signature:
        print("[warn] checkpoint settings changed; starting a fresh benchmark")
        return {"signature": signature, "results": {}}
    print(f"[resume] loaded {len(checkpoint.get('results', {}))} saved scores")
    return checkpoint


def result_key(n: int, k: int, seed: int, mode: str) -> str:
    return f"{n},{k},{seed},{mode}"


def main() -> None:
    sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    print(
        f"[setup] cirq {cirq.__version__}, numpy {np.__version__}, git {sha}, "
        f"calibration seed {CALIBRATION_SEED}"
    )
    print(
        f"[setup] comparison seeds={list(BENCHMARK_SEEDS)}, cases={len(BENCHMARK_CASES)}, "
        f"shots={SHOTS}, detuning={DETONING_KHZ} kHz"
    )
    overall_score = load_scoring()
    cal = make_challenge_calibration(CALIBRATION_SEED)
    with_dd = dp.PrepConfig(use_dynamical_decoupling=True)
    without_dd = dp.PrepConfig(use_dynamical_decoupling=False)
    clean_cal = tuple({key: (0.0, 0) for key in m} for m in cal)
    signature = benchmark_signature()
    checkpoint = load_checkpoint(signature)
    saved: dict[str, dict[str, float | int]] = checkpoint.setdefault("results", {})
    totals: dict[str, list[float]] = {"dd": [], "no-dd": [], "ideal": []}
    print(f"{'N':>3} {'n':>3} {'moments':>8} {'DD mean±std':>18} {'no-DD mean±std':>18} {'winner':>9}")
    for n, k in BENCHMARK_CASES:
        dd_scores = []
        no_dd_scores = []
        ideal_scores = []
        moments = 0
        for seed in BENCHMARK_SEEDS:
            dd_key = result_key(n, k, seed, "dd")
            if dd_key not in saved:
                noisy = NoiseConfig(seed=seed, detuning_khz=DETONING_KHZ)
                dd_score, moments = score_instance(n, k, cal, noisy, overall_score, with_dd)
                saved[dd_key] = {"score": dd_score, "moments": moments}
                atomic_write_json(CHECKPOINT_PATH, checkpoint)
            dd_score = float(saved[dd_key]["score"])
            moments = int(saved[dd_key]["moments"])

            no_dd_key = result_key(n, k, seed, "no-dd")
            if no_dd_key not in saved:
                noisy = NoiseConfig(seed=seed, detuning_khz=DETONING_KHZ)
                no_dd_score, no_dd_moments = score_instance(
                    n, k, cal, noisy, overall_score, without_dd
                )
                saved[no_dd_key] = {"score": no_dd_score, "moments": no_dd_moments}
                atomic_write_json(CHECKPOINT_PATH, checkpoint)
            no_dd_score = float(saved[no_dd_key]["score"])
            dd_scores.append(dd_score)
            no_dd_scores.append(no_dd_score)
            if RUN_IDEAL_BASELINE:
                ideal_key = result_key(n, k, seed, "ideal")
                if ideal_key not in saved:
                    ideal_score, ideal_moments = score_instance(
                        n, k, clean_cal,
                        NoiseConfig(seed=seed, t1_us=1e12, tphi_us=1e12),
                        overall_score,
                    )
                    saved[ideal_key] = {"score": ideal_score, "moments": ideal_moments}
                    atomic_write_json(CHECKPOINT_PATH, checkpoint)
                ideal_score = float(saved[ideal_key]["score"])
                ideal_scores.append(ideal_score)
        dd_mean, dd_std = mean_and_std(dd_scores)
        no_dd_mean, no_dd_std = mean_and_std(no_dd_scores)
        totals["dd"].append(dd_mean)
        totals["no-dd"].append(no_dd_mean)
        if ideal_scores:
            totals["ideal"].append(mean_and_std(ideal_scores)[0])
        winner = "DD" if dd_mean > no_dd_mean else "no-DD"
        print(
            f"{n:>3} {k:>3} {moments:>8} "
            f"{dd_mean:>8.3f} ± {dd_std:<7.3f} "
            f"{no_dd_mean:>8.3f} ± {no_dd_std:<7.3f} {winner:>9}"
        )
    dd_total, dd_total_std = mean_and_std(totals["dd"])
    no_dd_total, no_dd_total_std = mean_and_std(totals["no-dd"])
    print(
        f"[done] aggregate mean: DD={dd_total:.2f} ± {dd_total_std:.2f}; "
        f"no-DD={no_dd_total:.2f} ± {no_dd_total_std:.2f}; "
        f"winner={'DD' if dd_total > no_dd_total else 'no-DD'}"
    )
    if totals["ideal"]:
        ideal_total, ideal_std = mean_and_std(totals["ideal"])
        print(f"[done] ideal shot-noise baseline: {ideal_total:.2f} ± {ideal_std:.2f}")
    atomic_write_json(
        RESULTS_PATH,
        {
            "signature": signature,
            "complete": True,
            "aggregate": {
                "dd_mean": dd_total,
                "dd_std": dd_total_std,
                "no_dd_mean": no_dd_total,
                "no_dd_std": no_dd_total_std,
            },
            "results": saved,
        },
    )
    print(f"[saved] checkpoint: {CHECKPOINT_PATH}")
    print(f"[saved] final results: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
