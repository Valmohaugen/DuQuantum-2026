"""Reproducible local noise experiments scored with the untouched challenge code.

T1 and Tphi use microseconds; moment durations use nanoseconds; detuning uses
kHz. A channel is applied after each native moment. This is an approximate
noise model, not a prediction of an actual hardware calibration. Imports are
inert. Run directories are addressed by effective model/code provenance.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import cirq
import cirq_google
import networkx as nx
import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from claude import dicke_prep as dp  # noqa: E402
from claude.benchmark_statistics import case_statistics, paired_aggregate  # noqa: E402
from claude.score_diagnostics import (  # noqa: E402
    TABLE_NOTE,
    score_diagnostics,
    table_header,
    table_row,
    table_totals,
)
from claude.scripts.challenge_calibration import make_challenge_calibration  # noqa: E402
from claude.validation import validate_preparation  # noqa: E402

OUTPUT_DIR = REPO / "benchmark_outputs"
RESUME_FROM_CHECKPOINT = True
CALIBRATION_SEED = 1234
BENCHMARK_SEEDS = tuple(range(1, 6))
BENCHMARK_CASES = tuple((n, k) for n in range(2, 9) for k in range(1, n // 2 + 1))
DETUNING_KHZ = 20.0
SHOTS = 10_000
RUN_IDEAL_BASELINE = True
SCHEMA_VERSION = 2
PROB_ATOL = 1e-9
MAX_DENSITY_QUBITS = 10
SCORING_NOTEBOOK = REPO / "Google Quantum AI Challenge.ipynb"
SOURCE_PATHS = {
    "preparation": REPO / "claude/dicke_prep.py",
    "benchmark": Path(__file__).resolve(),
    "calibration": REPO / "claude/scripts/challenge_calibration.py",
    "statistics": REPO / "claude/benchmark_statistics.py",
    "score_diagnostics": REPO / "claude/score_diagnostics.py",
}
RNG_DOMAINS = {"shots": 1, "noise": 2}
Calibration = tuple[dict, dict, dict, dict]
Scorer = Callable[[np.ndarray, np.ndarray, int, int], float]
Prepared = tuple[cirq.Circuit, set[cirq.GridQubit]]


@dataclass(frozen=True)
class NoiseConfig:
    """Effective noise/sampling configuration, with independent RNG streams.

    seed controls measurement samples only; noise_seed controls the physical
    detuning ensemble. All values and units enter the provenance signature.
    Invalid rates, times, counts or seeds raise ValueError before simulation.
    """

    t1_us: float = 68.0
    tphi_us: float = 100.0
    t_1q_ns: float = 25.0
    t_cz_ns: float = 42.0
    detuning_khz: float = 0.0
    n_realizations: int = 2
    shots: int = 10_000
    max_correlator_size: int = 4
    seed: int = 7
    noise_seed: int = 7
    max_density_qubits: int = MAX_DENSITY_QUBITS

    def __post_init__(self) -> None:
        for name in ("t1_us", "tphi_us", "t_1q_ns", "t_cz_ns"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive; got {value}")
        if not math.isfinite(self.detuning_khz) or self.detuning_khz < 0:
            raise ValueError("detuning_khz must be finite and nonnegative")
        for name in ("n_realizations", "shots", "max_correlator_size", "max_density_qubits"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if min(self.seed, self.noise_seed) < 0:
            raise ValueError("RNG seeds must be nonnegative")


def make_rng(seed: int, stream: str) -> np.random.Generator:
    """Create a reproducible domain-separated noise or shot RNG from a numeric seed.

    SeedSequence mixes [seed, domain_id]; equal numeric seeds do not replay
    the same underlying stream in the two domains. DD/no-DD use matching
    domains and seeds so their common-random-number pairing is preserved.
    """
    if stream not in RNG_DOMAINS:
        raise ValueError(f"unknown RNG domain {stream!r}")
    return np.random.default_rng(np.random.SeedSequence([seed, RNG_DOMAINS[stream]]))


# Scoped by the unified runner; legacy module settings remain supported.
_NOISE_OVERRIDE: NoiseConfig | None = None
_PREPARATION_OVERRIDE: dp.PrepConfig | None = None


def _effective_noise() -> NoiseConfig:
    base = _NOISE_OVERRIDE if _NOISE_OVERRIDE is not None else NoiseConfig()
    return replace(base, shots=SHOTS, detuning_khz=DETUNING_KHZ)


def _effective_preparation() -> dict[bool, dp.PrepConfig]:
    base = _PREPARATION_OVERRIDE if _PREPARATION_OVERRIDE is not None else dp.PrepConfig()
    return {dd: replace(base, use_dynamical_decoupling=dd) for dd in (True, False)}


def scoring_source() -> str:
    """Read the original scoring cell without altering or executing other cells."""
    notebook = json.loads(SCORING_NOTEBOOK.read_text())
    matches = [
        "".join(cell["source"])
        for cell in notebook["cells"]
        if cell["cell_type"] == "code" and "def overall_score" in "".join(cell["source"])
    ]
    if len(matches) != 1:
        raise ValueError(f"expected one original scoring cell, found {len(matches)}")
    return matches[0]


def load_scoring() -> Scorer:
    """Return the exact official higher-is-better scorer, including its edge cases."""
    namespace: dict[str, Any] = {}
    exec("import itertools, math\nimport numpy as np", namespace)
    exec(compile(scoring_source(), "original challenge scoring", "exec"), namespace)
    return namespace["overall_score"]


def noisy_circuit(
    circuit: cirq.Circuit,
    qubits: Sequence[cirq.GridQubit],
    cal: Calibration,
    cfg: NoiseConfig,
    detuning: dict[cirq.GridQubit, float],
) -> cirq.Circuit:
    """Attach Pauli, damping and quasi-static Z errors after each native moment.

    Calibration entries are (probability, uncertainty). Missing gate calibration
    raises KeyError; invalid probabilities raise ValueError in the Cirq channel.
    Detuning is in kHz and must specify every simulated qubit when nonempty.
    """
    cz_err = {frozenset(pair): error for pair, (error, _) in cal[0].items()}
    sq_err = {q: error for q, (error, _) in cal[1].items()}
    output = cirq.Circuit()
    for moment in circuit:
        output.append(moment)
        is_cz = any(len(op.qubits) == 2 for op in moment)
        dt_us = (cfg.t_cz_ns if is_cz else cfg.t_1q_ns) * 1e-3
        gate_noise = []
        for op in moment:
            if len(op.qubits) == 2:
                gate_noise.append(
                    cirq.depolarize(cz_err[frozenset(op.qubits)], n_qubits=2).on(*op.qubits)
                )
            else:
                gate_noise.append(cirq.depolarize(sq_err[op.qubits[0]]).on(*op.qubits))
        output.append(cirq.Moment(gate_noise))
        output.append(
            cirq.Moment(cirq.amplitude_damp(-np.expm1(-dt_us / cfg.t1_us)).on_each(*qubits))
        )
        output.append(
            cirq.Moment(cirq.phase_damp(-np.expm1(-2 * dt_us / cfg.tphi_us)).on_each(*qubits))
        )
        if detuning:
            output.append(
                cirq.Moment(cirq.rz(2 * np.pi * detuning[q] * 1e-3 * dt_us).on(q) for q in qubits)
            )
    return output


def _probabilities(values: np.ndarray) -> np.ndarray:
    """Validate normalized probabilities, tolerating only roundoff-sized negatives."""
    values = np.asarray(values)
    if not np.all(np.isfinite(values)) or np.max(np.abs(values.imag)) > PROB_ATOL:
        raise ValueError("probabilities contain NaN, infinity or a nonreal component")
    probabilities = values.real.astype(float)
    mass = float(probabilities.sum())
    if np.min(probabilities) < -PROB_ATOL or not np.isclose(mass, 1, atol=PROB_ATOL, rtol=1e-10):
        raise ValueError(
            f"invalid probabilities: minimum={probabilities.min():.6g}, mass={mass:.16g}"
        )
    probabilities = np.clip(probabilities, 0, None)
    return probabilities / probabilities.sum()


def apply_readout(
    probs: np.ndarray, order: Sequence[cirq.GridQubit], cal: Calibration
) -> np.ndarray:
    """Apply asymmetric per-qubit confusion matrices to a length-2**N probability vector.

    Matrix columns label true bits, rows observed bits. The first ordered qubit
    is the most significant bit. Missing readout entries mean zero flips;
    probabilities outside [0,1] or invalid input mass raise ValueError.
    """
    n = len(order)
    p = _probabilities(probs).reshape([2] * n)
    for i, q in enumerate(order):
        e0, e1 = cal[2].get(q, (0.0, 0.0))[0], cal[3].get(q, (0.0, 0.0))[0]
        if not (0 <= e0 <= 1 and 0 <= e1 <= 1):
            raise ValueError(f"invalid readout probabilities for {q}: {e0}, {e1}")
        confusion = np.array([[1 - e0, e1], [e0, 1 - e1]])
        p = np.moveaxis(np.tensordot(confusion, p, axes=([1], [i])), 0, i)
    return _probabilities(p.reshape(-1))


def x_basis_probabilities(rho: np.ndarray, n: int) -> np.ndarray:
    """Compute diag(H**tensor(N) rho H**tensor(N)) in O(N*4**N) work.

    A Hadamard acts independently on each ket and bra tensor axis. Its real
    matrix gives (row0+row1, row0-row1)/sqrt(2). Applying both axes implements
    H rho H† without allocating or multiplying a dense full-register unitary.
    """
    tensor = rho.reshape((2,) * (2 * n))
    for axis in range(2 * n):
        moved = np.moveaxis(tensor, axis, 0)
        tensor = np.moveaxis(
            np.stack((moved[0] + moved[1], moved[0] - moved[1])) / np.sqrt(2), 0, axis
        )
    return _probabilities(np.diag(tensor.reshape(2**n, 2**n)))


def simulate_probabilities(
    circuit: cirq.Circuit,
    order: Sequence[cirq.GridQubit],
    cal: Calibration,
    cfg: NoiseConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ensemble-averaged observed Z/X probabilities, each shape (2**N,).

    Uses noise_seed only, so changing cfg.seed isolates shot noise. Includes
    readout flips in both bases. Raises ValueError for excessive density-matrix
    size or invalid probabilities; memory grows as 4**N.
    """
    n = len(order)
    if n < 1 or n > cfg.max_density_qubits:
        raise ValueError(f"density simulation requires 1 <= N <= {cfg.max_density_qubits}; got {n}")
    rng = make_rng(cfg.noise_seed, "noise")
    realizations = cfg.n_realizations if cfg.detuning_khz > 0 else 1
    pz, px = np.zeros(2**n), np.zeros(2**n)
    simulator = cirq.DensityMatrixSimulator(dtype=np.complex128)
    for _ in range(realizations):
        detuning = {q: rng.normal(0, cfg.detuning_khz) for q in order} if cfg.detuning_khz else {}
        rho = simulator.simulate(
            noisy_circuit(circuit, order, cal, cfg, detuning), qubit_order=order
        ).final_density_matrix
        if not np.all(np.isfinite(rho)):
            raise ValueError("density matrix contains nonfinite entries")
        np.testing.assert_allclose(rho, rho.conj().T, atol=1e-12, rtol=1e-10)
        pz += _probabilities(np.diag(rho)) / realizations
        px += x_basis_probabilities(rho, n) / realizations
    return apply_readout(pz, order, cal), apply_readout(px, order, cal)


def sample_bits(probs: np.ndarray, n: int, shots: int, rng: np.random.Generator) -> np.ndarray:
    """Draw (shots,N) big-endian bits from normalized probabilities; reject invalid data."""
    if shots < 1 or len(probs) != 2**n:
        raise ValueError("shots must be positive and probabilities must have length 2**N")
    indices = rng.choice(len(probs), size=shots, p=_probabilities(probs))
    return ((indices[:, None] >> np.arange(n - 1, -1, -1)) & 1).astype(int)


def score_instance(
    n: int,
    k: int,
    cal: Calibration,
    cfg: NoiseConfig,
    overall_score: Scorer,
    prep_cfg: dp.PrepConfig = dp.CONFIG,
    *,
    prepared: Prepared | None = None,
    probabilities: tuple[np.ndarray, np.ndarray] | None = None,
) -> tuple[float, int]:
    """Sample the official score for one case; preserve infinite/undefined outcomes.

    Optional prepared circuit/probabilities permit reuse across seeds. The score
    is not a fidelity. Call score_record before serialization. Invalid counts
    or simulation inputs fail loudly; the official scoring function is unchanged.
    """
    if n < 1 or not 1 <= k <= n:
        raise ValueError("official finite-shot scoring requires N >= 1 and 1 <= n <= N")
    circuit, qset = (
        prepared if prepared is not None else dp.create_dicke_state(n, k, *cal, config=prep_cfg)
    )
    pz, px = (
        probabilities
        if probabilities is not None
        else simulate_probabilities(circuit, sorted(qset), cal, cfg)
    )
    rng = make_rng(cfg.seed, "shots")
    zb, xb = sample_bits(pz, n, cfg.shots, rng), sample_bits(px, n, cfg.shots, rng)
    with np.errstate(divide="ignore", invalid="ignore"):
        score = float(overall_score(zb, xb, k, min(cfg.max_correlator_size, n)))
    return score, len(circuit)


def score_record(score: float, moments: int) -> dict[str, Any]:
    """Represent official scores in strict JSON, preserving nonfinite semantics.

    Finite values are numeric. Positive infinity (zero score denominator) and
    undefined/invalid results use null plus an explicit status; neither is
    silently included in finite-score summaries. No arbitrary score clipping.
    """
    status = (
        "finite"
        if math.isfinite(score)
        else "infinite"
        if math.isinf(score) and score > 0
        else "undefined"
    )
    return {
        "score": float(score) if status == "finite" else None,
        "score_status": status,
        "moments": int(moments),
    }


def mean_and_std(scores: Sequence[float]) -> tuple[float | None, float | None]:
    """Return finite sample mean/SD, zero SD for a singleton, or nulls for no data."""
    values = np.asarray(scores, dtype=float)
    if not len(values):
        return None, None
    if not np.all(np.isfinite(values)):
        raise ValueError("nonfinite scores require explicit status handling")
    return float(values.mean()), float(values.std(ddof=1)) if len(values) > 1 else 0.0


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def calibration_fingerprint(cal: Calibration) -> str:
    """Hash canonical endpoint/rate/uncertainty records, independent of mapping order."""
    maps = []
    for index, mapping in enumerate(cal):
        entries = []
        for key, value in mapping.items():
            coords = [[q.row, q.col] for q in sorted(key)] if index == 0 else [[key.row, key.col]]
            entries.append([coords, [float(x) for x in value]])
        maps.append(sorted(entries))
    return _digest(maps)


def benchmark_signature(cal: Calibration | None = None) -> dict[str, Any]:
    """Fingerprint all effective inputs that determine scores, including source/runtime."""
    maps = cal if cal is not None else make_challenge_calibration(CALIBRATION_SEED)
    return {
        "schema_version": SCHEMA_VERSION,
        "score_diagnostics_note": TABLE_NOTE,
        "settings": {
            "calibration_seed": CALIBRATION_SEED,
            "benchmark_seeds": list(BENCHMARK_SEEDS),
            "benchmark_cases": [list(case) for case in BENCHMARK_CASES],
            "detuning_khz": DETUNING_KHZ,
            "shots": SHOTS,
            "run_ideal_baseline": RUN_IDEAL_BASELINE,
        },
        "noise": asdict(_effective_noise()),
        "preparation": {str(dd): asdict(config) for dd, config in _effective_preparation().items()},
        "sources": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in SOURCE_PATHS.items()
        },
        "scoring_sha256": hashlib.sha256(scoring_source().encode()).hexdigest(),
        "calibration_sha256": calibration_fingerprint(maps),
        "runtime": {
            "python": platform.python_version(),
            "cirq": cirq.__version__,
            "cirq_google": cirq_google.__version__,
            "numpy": np.__version__,
            "networkx": nx.__version__,
            "scipy": importlib.metadata.version("scipy"),
            "machine": platform.machine(),
            "simulator": "CPU complex128",
        },
    }


def atomic_write_json(path: Path, payload: dict) -> None:
    """Atomically save strict JSON; serialization failure leaves prior data intact."""
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, prefix=path.name, suffix=".tmp", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(text)
    temporary.replace(path)


def run_directory(signature: dict) -> Path:
    """Return the provenance-addressed run folder, leaving legacy files untouched."""
    return OUTPUT_DIR / "runs" / _digest(signature)[:16]


def result_key(n: int, k: int, seed: int, mode: str) -> str:
    """Return the stable four-field key for a case/seed/mode record."""
    return f"{n},{k},{seed},{mode}"


def _expected_keys() -> set[str]:
    modes = ("dd", "no-dd", "ideal") if RUN_IDEAL_BASELINE else ("dd", "no-dd")
    return {
        result_key(n, k, seed, mode)
        for n, k in BENCHMARK_CASES
        for seed in BENCHMARK_SEEDS
        for mode in modes
    }


def load_checkpoint(signature: dict, path: Path | None = None) -> dict:
    """Load only matching, schema-valid records; reject corrupt/legacy/nonfinite JSON."""
    empty = {"signature": signature, "results": {}}
    path = (
        path if path is not None else run_directory(signature) / "noisy_benchmark_checkpoint.json"
    )
    if not RESUME_FROM_CHECKPOINT or not path.exists():
        return empty
    try:

        def reject(value: str) -> None:
            raise ValueError(f"nonstandard JSON number {value}")

        checkpoint = json.loads(path.read_text(), parse_constant=reject)
        if not isinstance(checkpoint, dict) or checkpoint.get("signature") != signature:
            raise ValueError("effective model, source, or runtime changed")
        records = checkpoint["results"]
        if not isinstance(records, dict) or not set(records) <= _expected_keys():
            raise ValueError("unexpected checkpoint result keys")
        for key, record in records.items():
            if not isinstance(record, dict):
                raise ValueError("checkpoint records must be mappings")
            status, score = record["score_status"], record["score"]
            moments = record["moments"]
            seed = int(key.split(",")[2])
            if (
                status not in ("finite", "infinite", "undefined")
                or not isinstance(moments, int)
                or isinstance(moments, bool)
                or not 1 <= moments <= dp.MAX_MOMENTS
            ):
                raise ValueError("invalid result status or moment count")
            for name in ("shot_seed", "noise_seed"):
                if type(record.get(name)) is not int or record[name] != seed:
                    raise ValueError(f"{name} does not match the declared result key")
            if status == "finite" and (
                not isinstance(score, (int, float))
                or isinstance(score, bool)
                or not math.isfinite(score)
            ):
                raise ValueError("invalid finite score")
            if status != "finite" and score is not None:
                raise ValueError("nonfinite status must have a null score")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"[warn] ignoring incompatible checkpoint: {exc}")
        return empty
    print(f"[resume] loaded {len(records)} validated scores")
    return checkpoint


def main() -> Path:
    """Run/resume the configured experiment and return its saved results path.

    Prepared circuits and identical probability ensembles are cached per run.
    Existing legacy data is never overwritten. No hardware API is used.
    """
    if (
        not BENCHMARK_CASES
        or not BENCHMARK_SEEDS
        or len(set(BENCHMARK_SEEDS)) != len(BENCHMARK_SEEDS)
    ):
        raise ValueError("cases and unique seeds must be nonempty")
    if len(set(BENCHMARK_CASES)) != len(BENCHMARK_CASES):
        raise ValueError("benchmark cases must be unique")
    base_noise = _effective_noise()
    if any(
        n > base_noise.max_density_qubits or n < 2 or not 1 <= k <= n for n, k in BENCHMARK_CASES
    ):
        raise ValueError(
            "benchmark cases exceed the density limit or have invalid excitation counts"
        )
    cal = make_challenge_calibration(CALIBRATION_SEED)
    signature = benchmark_signature(cal)
    directory = run_directory(signature)
    if not RESUME_FROM_CHECKPOINT and directory.exists():
        index = 1
        while directory.with_name(directory.name + f"-repeat-{index}").exists():
            index += 1
        directory = directory.with_name(directory.name + f"-repeat-{index}")
    checkpoint_path = directory / "noisy_benchmark_checkpoint.json"
    results_path = directory / "noisy_benchmark_results.json"
    checkpoint = load_checkpoint(signature, checkpoint_path)
    saved = checkpoint["results"]
    scorer = load_scoring()
    configs = {
        "dd": _effective_preparation()[True],
        "no-dd": _effective_preparation()[False],
    }
    clean_cal = tuple({key: (0.0, 0.0) for key in mapping} for mapping in cal)
    modes = ("dd", "no-dd", "ideal") if RUN_IDEAL_BASELINE else ("dd", "no-dd")
    print(
        f"[setup] Benchmark fingerprint: {directory.name}; shots {SHOTS}; seeds {list(BENCHMARK_SEEDS)}; CPU complex128"
    )
    print(
        f"[setup] model: T1 {base_noise.t1_us} us, Tphi {base_noise.tphi_us} us, detuning {DETUNING_KHZ} kHz"
    )
    print(
        f"[setup] cirq {cirq.__version__}; numpy {np.__version__}; calibration hash {signature['calibration_sha256'][:12]}"
    )
    done = 0
    expected = len(_expected_keys())
    print(TABLE_NOTE)
    print("[table] Cached rows reuse original build times and diagnostics; no resampling.")
    print(
        "[table] SUM adds each variant's stored rows, including cached build times and row score proxies; identifiers, fidelity, survival and rules are not summed."
    )
    prepared: dict[tuple[int, int, str], Prepared] = {}
    metadata: dict[tuple[int, int, str], dict] = {}
    probability_cache: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
    for seed in BENCHMARK_SEEDS:
        print(f"\n[seed] seed={seed}")
        print(table_header())
        for n, k in BENCHMARK_CASES:
            for mode in modes:
                key = result_key(n, k, seed, mode)
                done += 1
                if key in saved:
                    print(table_row(n, k, mode, saved[key]), flush=True)
                    continue
                maps = clean_cal if mode == "ideal" else cal
                prep_cfg = configs["dd"] if mode == "ideal" else configs[mode]
                prepared_key = (n, k, mode)
                if prepared_key not in prepared:
                    started = time.perf_counter()
                    prepared[prepared_key] = dp.create_dicke_state(n, k, *maps, config=prep_cfg)
                    elapsed = time.perf_counter() - started
                    circuit, qset = prepared[prepared_key]
                    fidelity = validate_preparation(circuit, qset, n, k, maps)
                    metadata[prepared_key] = {
                        "cz_count": sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                        "build_seconds": elapsed,
                        "fidelity": fidelity,
                        "rules": "ok",
                    }
                cfg = replace(base_noise, seed=seed, noise_seed=seed)
                if mode == "ideal":
                    cfg = replace(cfg, t1_us=1e12, tphi_us=1e12, detuning_khz=0.0)
                probability_key = (n, k, mode, cfg.noise_seed if cfg.detuning_khz else 0)
                if probability_key not in probability_cache:
                    circuit, qset = prepared[prepared_key]
                    probability_cache[probability_key] = simulate_probabilities(
                        circuit, sorted(qset), maps, cfg
                    )
                score, moments = score_instance(
                    n,
                    k,
                    maps,
                    cfg,
                    scorer,
                    prep_cfg,
                    prepared=prepared[prepared_key],
                    probabilities=probability_cache[probability_key],
                )
                record = {
                    **score_record(score, moments),
                    **metadata[prepared_key],
                    **score_diagnostics(
                        *probability_cache[probability_key],
                        n,
                        k,
                        shots=cfg.shots,
                        max_correlator_size=cfg.max_correlator_size,
                    ),
                    "shot_seed": seed,
                    "noise_seed": seed,
                }
                saved[key] = record
                atomic_write_json(checkpoint_path, checkpoint)
                print(table_row(n, k, mode, record), flush=True)
        print("-" * len(table_header().splitlines()[0]))
        for mode in modes:
            rows = [saved[result_key(n, k, seed, mode)] for n, k in BENCHMARK_CASES]
            print(table_totals(mode, rows), flush=True)
    aggregates = paired_aggregate(
        case_statistics({"signature": signature, "complete": True, "results": saved})
    )
    for mode in ("dd", "no_dd"):
        _, spread = mean_and_std(aggregates[mode + "_seed_means"])
        aggregates[mode + "_std"] = spread
    sha = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    payload = {
        "score_diagnostics_note": TABLE_NOTE,
        "signature": signature,
        "complete": set(saved) == _expected_keys(),
        "aggregate": aggregates,
        "results": saved,
        "provenance": {
            "git_commit": sha,
            "execution": "local CPU simulation",
            "note": "aggregate std is dispersion across matched seed means; difference_se is the paired standard error. Terminal E[s] is an inverse-mean-penalty proxy conditional on positive target Z count, not an expected reciprocal score.",
        },
    }
    atomic_write_json(results_path, payload)
    print(
        f"[done] {len(saved)}/{expected} records; nonfinite statuses {sum(r['score_status'] != 'finite' for r in saved.values())}"
    )
    print(f"[saved] {results_path}")
    return results_path


if __name__ == "__main__":
    main()
