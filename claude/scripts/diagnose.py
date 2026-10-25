"""Build current-code diagnostic reports, figures and machine-readable metrics.

Examples:
    python -m claude.scripts.diagnose --benchmark
    python -m claude.scripts.diagnose --results path/to/results.json
    python -m claude.scripts.diagnose --qubits 4 --excitations 2
No hardware jobs are submitted. A benchmark is explicit and bounded by default.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import cirq
import cirq_google
import numpy as np
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from claude import diagnostic_metrics as metrics  # noqa: E402
from claude import dicke_prep as dp  # noqa: E402
from claude.benchmark_statistics import (  # noqa: E402
    case_statistics,
    has_complete_provenance,
    paired_aggregate,
)
from claude.diagnostic_plots import render_figures  # noqa: E402
from claude.output_paths import figure_root  # noqa: E402
from claude.scripts import noisy_benchmark as benchmark  # noqa: E402
from claude.scripts.analyze_benchmark_results import latest_results, load_results  # noqa: E402
from claude.scripts.challenge_calibration import make_challenge_calibration  # noqa: E402

RESOURCE_SIZES = (2, 4, 8, 16, 30, 60, 90)
DETUNING_LEVELS = (0.0, 10.0, 20.0, 50.0)
SCORE_CASES = ((2, 1), (4, 1), (4, 2), (6, 1), (6, 2), (6, 3))
SCORE_SEEDS = (1, 2, 3, 4, 5)
DEFAULT_OUTPUT = REPO / "benchmark_outputs/diagnostics"
FIGURE_CAPTIONS = {
    "01_exact_state": "Exact amplitudes, relative phases, fidelity, leakage, and numerical residuals.",
    "02_distributions": "Hamming-weight leakage, conditional Z uniformity, X correlations and signed residuals.",
    "03_layout_and_cost": "Physical placement, actual CZ use, single-qubit overhead, and idle time.",
    "04_schedule": "Native single-qubit/CZ activity against modeled physical time, with and without DD.",
    "05_resource_scaling": "CZ/depth/error-proxy scaling and measured construction time; unsupported cases are explicit.",
    "06_noise_sensitivity": "Population leakage and coherence sensitivity to detuning for a fixed physical ensemble.",
    "07_paired_scores": "Individual finite scores, matched differences, exclusions and approximate Student-t intervals.",
    "08_seed_convergence": "Sensitivity of aggregate comparisons and uncertainty to the number of paired seed replicates.",
}


def _csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    columns = fields if fields is not None else list(rows[0]) if rows else ["no_records"]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _resource_sweep(
    cal: tuple,
    sizes: tuple[int, ...],
    noise: benchmark.NoiseConfig,
    preparation: dp.PrepConfig = dp.CONFIG,
) -> list[dict]:
    rows = []
    cache = {}
    for n in tqdm(sizes, desc="[resources]", unit="size"):
        if not isinstance(n, int) or n < 2:
            raise ValueError("resource sizes must be integers >=2")
        for family, k in (("W", 1), ("balanced", n // 2)):
            if (n, k) not in cache:
                started = time.perf_counter()
                try:
                    circuit, qset = dp.create_dicke_state(n, k, *cal, config=preparation)
                    costs = metrics.circuit_metrics(circuit, qset, cal, k, noise)
                    cache[n, k] = {
                        "status": "supported",
                        "moments": costs["moments"],
                        "cz_count": costs["cz_count"],
                        "oneq_count": costs["oneq_count"],
                        "duration_ns": costs["duration_ns"],
                        "gate_error_proxy": costs["gate_error_proxy"],
                        "error": None,
                    }
                except NotImplementedError as exc:
                    cache[n, k] = {
                        "status": "unsupported",
                        "moments": None,
                        "cz_count": None,
                        "oneq_count": None,
                        "duration_ns": None,
                        "gate_error_proxy": None,
                        "error": str(exc),
                    }
                    print(f"[warn] structural request D({n},{k}): {exc}")
                cache[n, k]["seconds"] = time.perf_counter() - started
            rows.append({"family": family, "n": n, "k": k, **cache[n, k]})
    return rows


def _number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.6g}"


def _report(data: dict, root: Path) -> str:
    state = data["state"]
    noise = data["noise"]
    n, k = state["n"], state["k"]
    lines = [
        f"# DuQuantum diagnostics — D({n},{k})",
        "",
        f"Generated: {data['generated_at']}. Bundle `{data['bundle_id']}`. Local CPU simulation.",
        "",
        "## What this run establishes",
        "",
        f"- Exact-state fidelity: **{state['fidelity']:.12f}**; infidelity {state['infidelity']:.3e}; leakage {state['leakage']:.3e}.",
        f"- Maximum aligned amplitude error: {_number(state['max_amplitude_error'])}; relative phase error {_number(state['max_phase_error_rad'])} rad.",
        f"- This example uses a {noise['n_realizations']}-realization nonzero-detuning ensemble with noise seed {noise['noise_seed']}; zero detuning is deterministic.",
        "- Distribution plots are exact for that finite physical ensemble. They have no measurement shot noise and do not estimate a hardware-wide noise average.",
        "- Structural scaling cases use the production constructor; large states are not densely simulated.",
        "",
        "## Effective settings",
        "",
        f"- Calibration seed {data['calibration_seed']}; content SHA-256 `{data['provenance']['calibration_sha256']}`.",
        f"- T1 {noise['t1_us']} µs; Tphi {noise['tphi_us']} µs; detuning std {noise['detuning_khz']} kHz.",
        f"- Single-qubit/CZ durations {noise['t_1q_ns']}/{noise['t_cz_ns']} ns. These are model assumptions.",
        f"- Maximum X-correlator order {noise['max_correlator_size']}; circuit cap 1,750 moments.",
        f"- Preparation: {data['preparation']['dd']['construction']}; DD policy {data['preparation']['dd']['dd_strategy']}, minimum sparse idle slots {data['preparation']['dd']['sparse_min_idle_slots']}.",
        f"- Runtime: Python {data['provenance']['runtime']['python']}, Cirq {cirq.__version__}, NumPy {np.__version__}, CPU {platform.machine()}.",
        "- Full source hashes, runtime, example settings and score-dataset provenance are in `diagnostics.json`.",
        "- Calibration-rate uncertainties are not propagated; comparisons are conditional on the selected synthetic rate map.",
        "",
        "## Noise and circuit comparison",
        "",
        "| Mode | Leakage | Z total variation | Conditional Z TV | X residual RMS | Moments | CZ | 1q | Model duration µs |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in ("dd", "no-dd"):
        dist = data["distributions"][mode]
        cost = data["circuits"][mode]
        rms = float(np.sqrt(np.mean(np.asarray(dist["x_residuals"]) ** 2)))
        lines.append(
            f"| {mode} | {dist['leakage']:.6f} | {dist['z_total_variation']:.6f} | {_number(dist['conditional_uniformity_tv'])} | {rms:.6f} | {cost['moments']} | {cost['cz_count']} | {cost['oneq_count']} | {cost['duration_ns'] / 1000:.3f} |"
        )
    lines += [
        "",
        "Leakage and conditional nonuniformity are different failure modes. The official reciprocal score is not fidelity. Additive calibrated error sums are cost heuristics, not error probabilities.",
        "",
        "## Paired score data",
        "",
    ]
    if data["comparison"] is None:
        lines += [
            "No raw score dataset was supplied. Paired-score and convergence figures are unavailable, rather than inferred from summaries.",
            "Run `python -m claude.scripts.diagnose --benchmark` for a new bounded, provenance-recorded experiment.",
        ]
    else:
        comparison = data["comparison"]
        aggregate = comparison["aggregate"]
        delta = np.asarray(aggregate["dd_seed_means"]) - np.asarray(aggregate["no_dd_seed_means"])
        interval = metrics.mean_interval(delta)
        lines += [
            f"Current raw dataset: [{data['score_data_path']}]({data['score_data_path']}).",
            f"Provenance structure verified: {data['score_provenance_verified']}; {len(comparison['cases'])} cases; {aggregate['n_pairs']} common finite paired seeds.",
            f"Paired aggregate DD minus no-DD: **{_number(interval['mean'])}**; standard error {_number(interval['standard_error'])}; approximate 95% t interval [{_number(interval['lower'])}, {_number(interval['upper'])}].",
            "The interval assumes approximately normal independent replicate means. Reciprocal scores can be heavy-tailed; few seeds and one synthetic calibration limit inference. This is not a hardware-wide DD recommendation.",
            "",
            "| N | n | Finite pairs | Excluded | DD mean | no-DD mean | Difference | Paired SE |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for row in comparison["cases"]:
            lines.append(
                f"| {row['n']} | {row['k']} | {row['n_pairs']} | {row['excluded']} | {_number(row['dd_mean'])} | {_number(row['no_dd_mean'])} | {_number(row['difference'])} | {_number(row['difference_se'])} |"
            )
        scores = np.array(
            [
                value
                for row in comparison["cases"]
                for key in ("dd_scores", "no_dd_scores")
                for value in row[key]
            ]
        )
        if len(scores):
            lines += [
                "",
                f"Matched finite DD/no-DD score range: {scores.min():.6g}–{scores.max():.6g}; median {np.median(scores):.6g}.",
                "Inspect isolated large reciprocal scores: they can dominate pooled means. The paired-difference view shows whether those values affect the DD comparison.",
            ]
    lines += ["", "## Coverage and unsupported requests", ""]
    failures = [row for row in data["resources"] if row["status"] != "supported"]
    if failures:
        lines += [f"- D({row['n']},{row['k']}): {row['error']}" for row in failures]
    else:
        lines.append("Every requested structural case returned a valid supported circuit.")
    lines += [
        "",
        "## Historical data",
        "",
        "The original report and PNG survive. The original 240 raw records are unavailable after the documented regression-test incident. The user chose to retain the surviving summaries only; they have not been reconstructed or relabeled as current data.",
        f"See [incident record]({REPO / 'claude/docs/DATA_RECOVERY_2026-10-24.md'}).",
        "",
        "## Machine-readable outputs",
        "",
        "- `diagnostics.json`: metrics, example probabilities, comparison samples, source hashes, and settings.",
        "- `resources.csv`, `qubits.csv`, `couplers.csv`: reusable circuit-cost tables.",
        "- Every figure is available as PNG and vector PDF.",
        f"- Figure directory: `{data['figure_dir']}`.",
        "",
        "## Figures",
        "",
    ]
    for name in data["figures"]:
        lines += [
            f"### {FIGURE_CAPTIONS[name]}",
            "",
            f"![{FIGURE_CAPTIONS[name]}]({Path(data['figure_dir']) / (name + '.png')})",
            "",
            f"[Vector PDF]({Path(data['figure_dir']) / (name + '.pdf')})",
            "",
        ]
    return "\n".join(lines) + "\n"


def resolve_report_settings(
    dataset: dict | None = None, *, diagnostic_seed: int = 7
) -> tuple[int, benchmark.NoiseConfig, dp.PrepConfig]:
    """Resolve the actual calibration, noise and DD-on preparation for a report.

    A validated modern dataset supplies its recorded settings. Legacy reports
    use the documented default noise model and original analytical preparation;
    state-only reports use current defaults. Legacy calibration seeds are reused
    when present. The nonnegative diagnostic seed controls the
    illustrative ensemble only. Returns (calibration_seed, noise, preparation).
    Invalid model settings or seeds raise ValueError; this function writes no files.
    """
    if (
        isinstance(diagnostic_seed, bool)
        or not isinstance(diagnostic_seed, int)
        or diagnostic_seed < 0
    ):
        raise ValueError("diagnostic_seed must be a nonnegative integer")
    verified = has_complete_provenance(dataset) if dataset is not None else False
    signature = dataset.get("signature", {}) if dataset is not None else {}
    settings = signature.get("settings", signature)
    noise = (
        benchmark.NoiseConfig(**signature["noise"])
        if verified
        else benchmark.NoiseConfig(detuning_khz=20.0)
    )
    recorded_preparation = signature.get("preparation", {}).get("True") if verified else None
    # Before optimized synthesis existed, omitted construction meant analytical.
    preparation = (
        dp.PrepConfig(**{"construction": "analytic", **recorded_preparation})
        if recorded_preparation
        else dp.PrepConfig(construction="analytic")
        if dataset is not None
        else dp.PrepConfig()
    )
    return (
        int(settings.get("calibration_seed", 1234)),
        replace(noise, seed=diagnostic_seed, noise_seed=diagnostic_seed),
        preparation,
    )


def build_report(
    output_dir: Path,
    n: int = 6,
    k: int = 3,
    *,
    results_path: Path | None = None,
    resource_sizes: tuple[int, ...] = RESOURCE_SIZES,
    detuning_levels: tuple[float, ...] = DETUNING_LEVELS,
    noise_config: benchmark.NoiseConfig | None = None,
    calibration_seed: int | None = None,
    preparation_config: dp.PrepConfig | None = None,
    diagnostic_seed: int = 7,
) -> Path:
    """Save a bounded diagnostic bundle and return its Markdown report path.

    Parameters
    ----------
    output_dir : pathlib.Path
        Parent of a source/config/data-addressed bundle; legacy files are untouched.
    n, k : int
        Illustrative case, 1<=N<=10 and 0<=k<=N. No large density matrices are built.
    results_path : pathlib.Path or None
        Optional completed raw experiment; None explicitly means no paired score data.
        Modern model/calibration settings are reused; unverified data is labeled.
    resource_sizes : tuple[int,...]
        Larger constructor-only probes. Unsupported requests are recorded explicitly.
    detuning_levels : tuple[float,...]
        Nonnegative kHz standard deviations for a fixed-seed sensitivity experiment.
    noise_config, calibration_seed, preparation_config : optional
        Explicit settings for a state-only report. A verified scored dataset uses
        its recorded settings instead and rejects these overrides. Preparation
        settings also apply to constructor-only scaling probes.
    diagnostic_seed : int
        Nonnegative physical ensemble/shot seed for illustrative distributions;
        existing individual benchmark records and their scores are preserved.

    Returns
    -------
    pathlib.Path
        Saved report alongside strict JSON/CSV; PNG/PDF go under the shared
        figs root and are linked by the report. Invalid inputs or unexpected
        physics/numerical failures raise; no hardware is accessed.
    """
    if not 1 <= n <= metrics.MAX_DISTRIBUTION_QUBITS or not 0 <= k <= n:
        raise ValueError("diagnostic examples require 1<=N<=10 and 0<=k<=N")
    dataset = load_results(results_path) if results_path is not None else None
    verified = has_complete_provenance(dataset) if dataset is not None else False
    signature = dataset.get("signature", {}) if dataset is not None else {}
    if verified and any(
        value is not None for value in (noise_config, calibration_seed, preparation_config)
    ):
        raise ValueError(
            "scored-data reports use recorded noise/calibration/preparation settings; omit overrides"
        )
    seed, noise, on_config = resolve_report_settings(dataset, diagnostic_seed=diagnostic_seed)
    seed = seed if calibration_seed is None else calibration_seed
    noise = noise if noise_config is None else noise_config
    noise = replace(noise, seed=diagnostic_seed, noise_seed=diagnostic_seed)
    on_config = on_config if preparation_config is None else preparation_config
    preparations = {
        mode: replace(on_config, use_dynamical_decoupling=mode == "dd") for mode in ("dd", "no-dd")
    }
    cal = make_challenge_calibration(seed)
    prepared = {
        mode: dp.create_dicke_state(n, k, *cal, config=preparations[mode])
        for mode in ("dd", "no-dd")
    }
    circuit, qset = prepared["dd"]
    state = cirq.final_state_vector(circuit, qubit_order=sorted(qset), dtype=np.complex128)
    source_paths = {
        **benchmark.SOURCE_PATHS,
        "metrics": REPO / "claude/diagnostic_metrics.py",
        "plots": REPO / "claude/diagnostic_plots.py",
        "driver": Path(__file__).resolve(),
        "validation": REPO / "claude/validation.py",
        "analyzer": REPO / "claude/scripts/analyze_benchmark_results.py",
        "output_paths": REPO / "claude/output_paths.py",
    }
    provenance = {
        "sources": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in source_paths.items()
        },
        "calibration_sha256": benchmark.calibration_fingerprint(cal),
        "runtime": {
            "python": platform.python_version(),
            "cirq": cirq.__version__,
            "numpy": np.__version__,
            "cirq_google": cirq_google.__version__,
            "scipy": importlib.metadata.version("scipy"),
            "matplotlib": importlib.metadata.version("matplotlib"),
            "networkx": importlib.metadata.version("networkx"),
            "machine": platform.machine(),
        },
        "git_commit": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "working_tree_dirty": bool(
            subprocess.run(
                ["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True, text=True
            ).stdout.strip()
        ),
        "score_data_sha256": hashlib.sha256(results_path.read_bytes()).hexdigest()
        if results_path is not None
        else None,
    }
    identity = {
        "preparation": {mode: asdict(config) for mode, config in preparations.items()},
        "n": n,
        "k": k,
        "noise": asdict(noise),
        "resources": resource_sizes,
        "detuning_levels": detuning_levels,
        "provenance": provenance,
    }
    bundle = hashlib.sha256(
        json.dumps(identity, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()[:12]
    root = Path(output_dir).resolve() / f"D{n}_{k}-{bundle}"
    figures = figure_root() / "diagnostics" / root.name
    root.mkdir(parents=True, exist_ok=True)
    print(f"[setup] diagnostic bundle {root}")
    probabilities = {}
    distributions = {}
    circuits = {}
    for mode, (circuit, qset) in prepared.items():
        probabilities[mode] = benchmark.simulate_probabilities(circuit, sorted(qset), cal, noise)
        distributions[mode] = metrics.distribution_metrics(
            *probabilities[mode], n, k, noise.max_correlator_size
        )
        circuits[mode] = metrics.circuit_metrics(circuit, qset, cal, k, noise)
        print(
            f"[noise] {mode}: leakage={distributions[mode]['leakage']:.5f}, Z TV={distributions[mode]['z_total_variation']:.5f}; {len(circuit)} moments"
        )
    sensitivity = []
    for detuning in tqdm(detuning_levels, desc="[detuning]", unit="level"):
        cfg = replace(noise, detuning_khz=detuning)
        for mode, (circuit, qset) in prepared.items():
            probs = (
                probabilities[mode]
                if np.isclose(detuning, noise.detuning_khz, atol=1e-12, rtol=1e-10)
                else benchmark.simulate_probabilities(circuit, sorted(qset), cal, cfg)
            )
            result = metrics.distribution_metrics(*probs, n, k, noise.max_correlator_size)
            sensitivity.append(
                {
                    "mode": mode,
                    "detuning_khz": detuning,
                    "leakage": result["leakage"],
                    "x_rms_error": float(np.sqrt(np.mean(np.asarray(result["x_residuals"]) ** 2))),
                }
            )
    device = cirq_google.Willow105.metadata
    comparison = None
    if dataset is not None:
        rows = case_statistics(dataset)
        comparison = {"cases": rows, "aggregate": paired_aggregate(rows)}
    data = {
        "bundle_id": bundle,
        "generated_at": datetime.now(ZoneInfo("America/New_York")).isoformat(timespec="seconds"),
        "state": metrics.state_metrics(state, k),
        "noise": asdict(noise),
        "calibration_seed": seed,
        "preparation": {mode: asdict(config) for mode, config in preparations.items()},
        "provenance": provenance,
        "distributions": distributions,
        "circuits": circuits,
        "sensitivity": sensitivity,
        "resources": _resource_sweep(cal, resource_sizes, noise, on_config),
        "device": {
            "qubits": [[q.row, q.col] for q in sorted(device.qubit_set)],
            "usable_qubits": [[q.row, q.col] for q in sorted(cal[1])],
            "pairs": [
                [[q.row, q.col] for q in sorted(pair)]
                for pair in sorted(tuple(sorted(p)) for p in device.qubit_pairs)
            ],
        },
        "score_data_status": "available" if dataset is not None else "unavailable",
        "score_data_path": str(results_path.resolve()) if results_path is not None else None,
        "score_provenance_verified": verified,
        "benchmark_signature": signature if dataset is not None else None,
        "comparison": comparison,
        "figures": [],
        "figure_dir": str(figures),
    }
    _csv(root / "resources.csv", data["resources"])
    _csv(
        root / "qubits.csv",
        [{"mode": mode, **row} for mode in circuits for row in circuits[mode]["qubits"]],
    )
    _csv(
        root / "couplers.csv",
        [
            {
                "mode": mode,
                "a_row": row["a"][0],
                "a_col": row["a"][1],
                "b_row": row["b"][0],
                "b_col": row["b"][1],
                "cz_count": row["cz_count"],
                "cz_error": row["cz_error"],
            }
            for mode in circuits
            for row in circuits[mode]["couplers"]
        ],
        fields=["mode", "a_row", "a_col", "b_row", "b_col", "cz_count", "cz_error"],
    )
    print(f"[figures] rendering scientific PNG and vector PDF views to {figures}")
    data["figures"] = render_figures(data, figures)
    benchmark.atomic_write_json(root / "diagnostics.json", data)
    report = root / "report.md"
    report.write_text(_report(data, root))
    print(
        f"[state] fidelity={data['state']['fidelity']:.12f}; relative phase error={_number(data['state']['max_phase_error_rad'])} rad"
    )
    print(
        f"[cost] DD/no-DD one-qubit gates: {circuits['dd']['oneq_count']}/{circuits['no-dd']['oneq_count']}; CZ gates: {circuits['dd']['cz_count']}/{circuits['no-dd']['cz_count']}"
    )
    if comparison is not None:
        aggregate = comparison["aggregate"]
        interval = metrics.mean_interval(
            np.asarray(aggregate["dd_seed_means"]) - aggregate["no_dd_seed_means"]
        )
        print(
            f"[compare] common finite seed pairs={aggregate['n_pairs']}; DD-noDD={_number(interval['mean'])}; paired SE={_number(interval['standard_error'])}; approximate 95% t interval=[{_number(interval['lower'])}, {_number(interval['upper'])}]"
        )
    print(f"[done] {len(data['figures'])} figures in PNG/PDF, JSON, three CSV tables")
    print(f"[saved] {report}")
    return report


def main() -> None:
    """Run an optional explicit bounded benchmark, then create a diagnostic bundle."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(os.environ.get("DUQUANTUM_DIAGNOSTICS_DIR", str(DEFAULT_OUTPUT))),
    )
    parser.add_argument("--results", type=Path)
    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="run/resume six cases and five paired seeds locally",
    )
    parser.add_argument(
        "--full-benchmark", action="store_true", help="use all sixteen default cases through N=8"
    )
    parser.add_argument("--qubits", type=int, default=6)
    parser.add_argument("--excitations", type=int, default=3)
    args = parser.parse_args()
    results = args.results
    if args.benchmark or args.full_benchmark:
        names = ("BENCHMARK_CASES", "BENCHMARK_SEEDS")
        previous = {name: getattr(benchmark, name) for name in names}
        try:
            if not args.full_benchmark:
                benchmark.BENCHMARK_CASES = SCORE_CASES
            benchmark.BENCHMARK_SEEDS = SCORE_SEEDS
            results = benchmark.main()
        finally:
            for name, value in previous.items():
                setattr(benchmark, name, value)
    elif results is None:
        try:
            results = latest_results()
        except FileNotFoundError:
            print("[data] no current raw score dataset; generating state/circuit diagnostics only")
    build_report(args.output_dir, args.qubits, args.excitations, results_path=results)


if __name__ == "__main__":
    main()
