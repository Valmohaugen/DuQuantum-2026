"""Compare hybrid and upstream preparations using identical calibration, noise and RNG seeds.

python -m claude.scripts.compare_solutions
python -m claude.scripts.compare_solutions --cases 4,2 6,3 --seeds 1,2,3 --shots 10000
All evidence is saved; no hardware, Git mutation or publication occurs.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import importlib.util
import json
import platform
import sys
import time
import traceback
import uuid
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import cirq
import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from claude import dicke_prep as dp
from claude.diagnostic_metrics import circuit_metrics, mean_interval
from claude.output_paths import figure_root
from claude.reference_routing import with_safe_reference_routing
from claude.score_diagnostics import TABLE_NOTE, score_diagnostics, table_header, table_row
from claude.scripts import noisy_benchmark as benchmark
from claude.scripts.challenge_calibration import make_challenge_calibration
from claude.validation import validate_preparation

REPO = Path(__file__).resolve().parents[2]
CASES = ((2, 1), (4, 1), (4, 2), (6, 3), (8, 4), (15, 7))
SEEDS = (1, 2, 3)
MAX_NOISE_QUBITS = 6
MAX_EXACT_QUBITS = 16
PAIRED_LINEAR_THRESHOLD = 0.1
CALIBRATION_SEED = 1234
VARIANT_DESCRIPTIONS = {
    "hybrid dense": "Maintained solver with dense DD in eligible idle slots.",
    "hybrid sparse": "The same maintained solver with canceling X-pulse pairs only in sufficiently long idle windows.",
    "hybrid off": "The same maintained solver with DD disabled.",
    "upstream sparse": "ryon/dicke_solution.py with that reference's sparse echo policy.",
    "upstream off": "ryon/dicke_solution.py with DD disabled.",
    "minimal": "The separate ryon/minimal_dicke.py reference constructor, using a local Cirq empty-candidate routing guard. Its logical construction and source remain unchanged.",
    "baseline": "An additional user-selected preparation module, retaining its own defaults.",
}
Builder = Callable[[int, int, tuple], tuple[cirq.Circuit, set[cirq.GridQubit]]]


def _load(path: Path) -> object:
    name = "_comparison_" + hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load comparison module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _builders(
    baseline: Path | None, upstream: bool, config: dp.PrepConfig | None = None
) -> list[tuple[str, Builder, Path]]:
    result = []
    base = config if config is not None else dp.PrepConfig()
    for label, config in (
        ("hybrid dense", replace(base, use_dynamical_decoupling=True, dd_strategy="dense")),
        ("hybrid sparse", replace(base, use_dynamical_decoupling=True, dd_strategy="sparse")),
        ("hybrid off", replace(base, use_dynamical_decoupling=False)),
    ):

        def build(n: int, k: int, cal: tuple, config: dp.PrepConfig = config) -> tuple:
            return dp.create_dicke_state(n, k, *cal, config=config)

        result.append((label, build, REPO / "claude/dicke_prep.py"))
    if upstream:
        source = REPO / "ryon/dicke_solution.py"
        other = _load(source)
        for label, strategy in (("upstream sparse", "sparse"), ("upstream off", None)):

            def build(n: int, k: int, cal: tuple, strategy: str | None = strategy) -> tuple:
                return other.create_dicke_state(n, k, *cal, dd_schema=strategy)

            result.append((label, build, source))
        minimal_source = REPO / "ryon/minimal_dicke.py"
        minimal = _load(minimal_source)
        minimal_builder = with_safe_reference_routing(minimal.create_dicke_state)
        result.append(("minimal", lambda n, k, cal: minimal_builder(n, k, *cal), minimal_source))
    if baseline is not None:
        module = _load(baseline)
        result.append(
            ("baseline", lambda n, k, cal: module.create_dicke_state(n, k, *cal), baseline)
        )
    return result


def _csv(path: Path, rows: list[dict]) -> None:
    columns = sorted({key for row in rows for key in row})
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _reference_failure(root: Path, data: dict, row: dict, exc: Exception, elapsed: float) -> None:
    """Save an optional candidate's failure explicitly without inventing a score."""
    directory = root / "errors"
    directory.mkdir(exist_ok=True)
    path = directory / f"N{row['n']}-k{row['k']}-{row['variant'].replace(' ', '-')}.txt"
    path.write_text("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    row.update(
        status="error",
        reason=str(exc),
        error_type=type(exc).__name__,
        error_log=str(path),
        build_seconds=elapsed,
    )
    data["resources"].append(row)
    print(
        f"[warn] Reference {row['variant']} D({row['n']},{row['k']}) failed: {type(exc).__name__}: {exc}; traceback {path}",
        flush=True,
    )
    print(table_row(row["n"], row["k"], row["variant"], {**row, "rules": "FAIL"}), flush=True)


def _plots(data: dict, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    labels = data["variants"]
    cases = [tuple(case) for case in data["cases"]]
    colors = mpl.colormaps["tab10"]
    width = 0.8 / len(labels)
    figure = Figure(figsize=(14, 9), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 2)
    for index, label in enumerate(labels):
        rows = {(r["n"], r["k"]): r for r in data["resources"] if r["variant"] == label}
        for axis, key, title in zip(
            axes.flat,
            ("cz_count", "moments", "gate_error_proxy", "build_seconds"),
            (
                "Native CZ gates",
                "Native moments",
                "Additive gate-error proxy",
                "Construction time [s]",
            ),
        ):
            axis.bar(
                np.arange(len(cases)) + width * (index - (len(labels) - 1) / 2),
                [rows[c].get(key, np.nan) for c in cases],
                width,
                color=colors(index),
                label=label,
            )
            axis.set_title(title)
            axis.set_xticks(
                range(len(cases)),
                [f"D({n},{k})" for n, k in cases],
                rotation=90 if len(cases) > 10 else 30,
                fontsize=9,
            )
            axis.grid(axis="y", alpha=0.2)
    axes[1, 1].set_yscale("log")
    handles, names = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, names, loc="outside lower center", ncol=4)
    figure.suptitle("Common-calibration resource comparison; unsupported cases remain explicit")
    for suffix in (".png", ".pdf"):
        figure.savefig(root / ("01_resources" + suffix), dpi=180)
    figure.clear()
    figure = Figure(figsize=(14, 8), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(2, 1)
    scored = sorted({(r["n"], r["k"]) for r in data["scores"]})
    for index, label in enumerate(labels):
        for j, (n, k) in enumerate(scored):
            selected = {
                r["seed"]: r
                for r in data["scores"]
                if r["variant"] == label and (r["n"], r["k"]) == (n, k)
            }
            values = [r["score"] for r in selected.values() if r["score_status"] == "finite"]
            x = j + width * (index - (len(labels) - 1) / 2)
            if values:
                axes[0].scatter(
                    np.full(len(values), x),
                    values,
                    s=18,
                    color=colors(index),
                    label=label if j == 0 else None,
                )
            reference = {
                r["seed"]: r
                for r in data["scores"]
                if r["variant"] == "hybrid dense" and (r["n"], r["k"]) == (n, k)
            }
            pairs = [
                r["score"] - reference[seed]["score"]
                for seed, r in selected.items()
                if seed in reference
                and r["score_status"] == "finite"
                and reference[seed]["score_status"] == "finite"
            ]
            interval = mean_interval(pairs)
            if interval["mean"] is not None:
                error = (
                    [[interval["mean"] - interval["lower"]], [interval["upper"] - interval["mean"]]]
                    if interval["lower"] is not None
                    else None
                )
                axes[1].errorbar(
                    x, interval["mean"], yerr=error, fmt="o", color=colors(index), capsize=3
                )
    for axis in axes:
        axis.set_xticks(range(len(scored)), [f"D({n},{k})" for n, k in scored])
        axis.grid(axis="y", alpha=0.2)
        if not scored:
            axis.text(
                0.5, 0.5, "No finite-shot cases requested", transform=axis.transAxes, ha="center"
            )
    axes[0].set(
        ylabel="Official finite sampled score",
        title="Individual observations; nonfinite outcomes retained in JSON/CSV",
    )
    finite = [r["score"] for r in data["scores"] if r["score_status"] == "finite"]
    if finite and min(finite) > 0:
        axes[0].set_yscale("log")
    axes[1].axhline(0, color="black", lw=0.7)
    axes[1].set_yscale("symlog", linthresh=PAIRED_LINEAR_THRESHOLD)
    axes[1].set(
        ylabel="Variant minus hybrid dense [symlog]",
        title="Matched-seed mean difference and approximate 95% t interval",
    )
    figure.legend(handles, names, loc="outside lower center", ncol=4)
    figure.suptitle(
        f"Shared noise model and calibration; {len(data['seeds'])} exploratory seed replicates"
    )
    for suffix in (".png", ".pdf"):
        figure.savefig(root / ("02_scores" + suffix), dpi=180)
    figure.clear()


def compare_solutions(
    output_dir: Path,
    *,
    cases: tuple = CASES,
    seeds: tuple = SEEDS,
    noise: benchmark.NoiseConfig = benchmark.NoiseConfig(detuning_khz=20),
    baseline: Path | None = None,
    include_upstream: bool = True,
    noise_max_qubits: int = MAX_NOISE_QUBITS,
    calibration_seed: int = CALIBRATION_SEED,
    hybrid_config: dp.PrepConfig | None = None,
) -> Path:
    """Validate and compare candidates, saving raw evidence, source snapshots and figures.

    Inputs are explicit cases (N,k), unique nonnegative seeds and the shared noise
    model. Density simulation is bounded to noise_max_qubits<=6; selected larger
    cases are exact-checked through16 and otherwise structurally checked. Unexpected
    maintained-constructor and shared scoring failures raise. Optional reference
    construction/validation failures retain error rows and tracebacks without scores;
    unsupported requests are recorded separately. Every invocation gets a new folder
    so previous results survive. Returns the saved Markdown report path.
    """
    if (
        not cases
        or len(set(cases)) != len(cases)
        or any(
            not isinstance(n, int) or not isinstance(k, int) or n < 1 or not 0 <= k <= n
            for n, k in cases
        )
    ):
        raise ValueError("cases must be unique integer (N,k) with N>=1 and 0<=k<=N")
    if (
        not seeds
        or len(set(seeds)) != len(seeds)
        or any(not isinstance(s, int) or s < 0 for s in seeds)
        or not 0 <= noise_max_qubits <= MAX_NOISE_QUBITS
    ):
        raise ValueError("use unique nonnegative integer seeds and noise bound0..6")
    candidates = _builders(baseline, include_upstream, hybrid_config)
    cal = make_challenge_calibration(calibration_seed)
    sources = {
        **benchmark.SOURCE_PATHS,
        "comparison": Path(__file__),
        "validation": REPO / "claude/validation.py",
        "metrics": REPO / "claude/diagnostic_metrics.py",
        "paths": REPO / "claude/output_paths.py",
    }
    sources.update({label: path for label, _, path in candidates})
    if include_upstream:
        sources["reference_routing"] = REPO / "claude/reference_routing.py"
    identity = {
        "score_diagnostics_note": TABLE_NOTE,
        "cases": cases,
        "seeds": seeds,
        "noise": asdict(noise),
        "noise_max_qubits": noise_max_qubits,
        "calibration_seed": calibration_seed,
        "hybrid_preparation": asdict(
            hybrid_config if hybrid_config is not None else dp.PrepConfig()
        ),
        "reference_adapters": (
            {"minimal": "local RouteCQC empty-candidate routing guard"} if include_upstream else {}
        ),
        "calibration_sha256": benchmark.calibration_fingerprint(cal),
        "sources": {
            label: hashlib.sha256(path.read_bytes()).hexdigest() for label, path in sources.items()
        },
        "scoring_sha256": hashlib.sha256(benchmark.scoring_source().encode()).hexdigest(),
        "runtime": {
            "python": platform.python_version(),
            "cirq": cirq.__version__,
            "numpy": np.__version__,
            "cirq_google": importlib.metadata.version("cirq-google"),
            "networkx": importlib.metadata.version("networkx"),
            "scipy": importlib.metadata.version("scipy"),
            "matplotlib": mpl.__version__,
            "machine": platform.machine(),
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(identity, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()[:12]
    run_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + fingerprint
        + "-"
        + uuid.uuid4().hex[:6]
    )
    root = Path(output_dir).resolve() / run_id
    root.mkdir(parents=True, exist_ok=False)
    (root / "sources").mkdir()
    (root / "circuits").mkdir()
    for index, (name, path) in enumerate(sources.items()):
        (root / "sources" / f"{index:02}-{path.name}").write_bytes(path.read_bytes())
    figures = figure_root() / "comparisons" / run_id
    data = {
        **identity,
        "run_id": run_id,
        "figure_dir": str(figures),
        "variants": [c[0] for c in candidates],
        "resources": [],
        "scores": [],
    }
    scorer = benchmark.load_scoring()
    print(
        f"[setup] comparison {run_id}; seeds={seeds}; local CPU; shared calibration={calibration_seed}"
    )
    print(TABLE_NOTE)
    print(f"[seed] seed={seeds[0]}")
    print(table_header())
    for n, k in cases:
        for label, build, source in candidates:
            started = time.perf_counter()
            row = {"n": n, "k": k, "variant": label}
            try:
                circuit, qubits = build(n, k, cal)
            except NotImplementedError as exc:
                row.update(
                    status="unsupported",
                    reason=str(exc),
                    build_seconds=time.perf_counter() - started,
                )
                data["resources"].append(row)
                print(table_row(n, k, label, {**row, "rules": "unsup"}), flush=True)
                continue
            except Exception as exc:
                if source.resolve() == (REPO / "claude/dicke_prep.py").resolve():
                    raise
                _reference_failure(root, data, row, exc, time.perf_counter() - started)
                continue
            elapsed = time.perf_counter() - started
            if elapsed >= 60.0:
                row.update(
                    status="invalid",
                    reason="construction exceeded the 60-second challenge limit",
                    build_seconds=elapsed,
                )
                data["resources"].append(row)
                print(table_row(n, k, label, {**row, "rules": "FAIL"}), flush=True)
                continue
            try:
                fidelity = validate_preparation(
                    circuit, qubits, n, k, cal, check_state=n <= MAX_EXACT_QUBITS
                )
                costs = circuit_metrics(circuit, qubits, cal, k, noise)
            except Exception as exc:
                if source.resolve() == (REPO / "claude/dicke_prep.py").resolve():
                    raise
                _reference_failure(root, data, row, exc, elapsed)
                continue
            row.update(
                status="valid",
                fidelity=fidelity,
                build_seconds=elapsed,
                **{
                    key: costs[key]
                    for key in ("cz_count", "oneq_count", "moments", "gate_error_proxy")
                },
            )
            data["resources"].append(row)
            row["output_qubits"] = [[q.row, q.col] for q in sorted(qubits)]
            circuit_path = root / "circuits" / f"N{n}-k{k}-{label.replace(' ', '-')}.json"
            cirq.to_json(circuit, circuit_path)
            row["circuit_json"] = str(circuit_path)
            if n <= noise_max_qubits and k >= 1:
                for seed in seeds:
                    cfg = replace(noise, seed=seed, noise_seed=seed)
                    probabilities = benchmark.simulate_probabilities(
                        circuit, sorted(qubits), cal, cfg
                    )
                    score, moments = benchmark.score_instance(
                        n,
                        k,
                        cal,
                        cfg=cfg,
                        overall_score=scorer,
                        prepared=(circuit, qubits),
                        probabilities=probabilities,
                    )
                    record = {
                        "n": n,
                        "k": k,
                        "variant": label,
                        "seed": seed,
                        **benchmark.score_record(score, moments),
                        **score_diagnostics(
                            *probabilities,
                            n,
                            k,
                            shots=cfg.shots,
                            max_correlator_size=cfg.max_correlator_size,
                        ),
                    }
                    data["scores"].append(record)
                    if seed == seeds[0]:
                        print(table_row(n, k, label, {**row, **record, "rules": "ok"}), flush=True)
            else:
                print(table_row(n, k, label, {**row, "rules": "ok"}), flush=True)
    indexed = {(row["n"], row["k"], row["variant"]): row for row in data["resources"]}
    for seed in seeds[1:]:
        print(f"\n[seed] seed={seed}")
        print(table_header())
        for record in data["scores"]:
            if record["seed"] == seed:
                n, k, label = record["n"], record["k"], record["variant"]
                print(
                    table_row(n, k, label, {**indexed[n, k, label], **record, "rules": "ok"}),
                    flush=True,
                )
    data["paired"] = []
    for n, k in sorted({(r["n"], r["k"]) for r in data["scores"]}):
        reference = {
            r["seed"]: r
            for r in data["scores"]
            if r["variant"] == "hybrid dense" and (r["n"], r["k"]) == (n, k)
        }
        for label in data["variants"]:
            selected = [
                r for r in data["scores"] if r["variant"] == label and (r["n"], r["k"]) == (n, k)
            ]
            differences = [
                r["score"] - reference[r["seed"]]["score"]
                for r in selected
                if r["seed"] in reference
                and r["score_status"] == reference[r["seed"]]["score_status"] == "finite"
            ]
            data["paired"].append(
                {
                    "n": n,
                    "k": k,
                    "variant": label,
                    "excluded": len(seeds) - len(differences),
                    **mean_interval(differences),
                }
            )
    failures = [row for row in data["resources"] if row["status"] == "error"]
    data["reference_error_count"] = len(failures)
    _plots(data, figures)
    benchmark.atomic_write_json(root / "comparison.json", data)
    _csv(root / "resources.csv", data["resources"])
    _csv(root / "scores.csv", data["scores"])
    lines = [
        "# Shared-model solution comparison",
        "",
        f"Run {run_id}; calibration seed{calibration_seed}; replicate seeds{seeds}.",
        "",
        "Every candidate uses the same calibration, density-noise model, measurement settings and domain-separated paired seeds. Exact state/rule checks precede scores. Source snapshots and hashes are saved alongside this report.",
        "",
        "| State | Variant | Status | CZ | 1q | Moments | Fidelity | Build s |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in data["resources"]:
        lines.append(
            f"| D({row['n']},{row['k']}) | {row['variant']} | {row['status']} | {row.get('cz_count', '—')} | {row.get('oneq_count', '—')} | {row.get('moments', '—')} | {row.get('fidelity', 'unavailable')} | {row['build_seconds']:.3f} |"
        )
    lines += [
        "",
        "## Variant labels",
        "",
        "DD means dynamical decoupling: echo pulses inserted during idle periods to reduce sensitivity to detuning. The maintained scheduler preserves the ideal unitary; additional pulses can still add noise. Dense DD is not assumed to be better than sparse DD or no DD.",
        "",
        "Hybrid labels identify the maintained solver and its combined construction strategies; they do not combine implementations during a benchmark. Sparse policies in different implementations need not produce the same pulse sequence.",
        "",
        "| Variant | Meaning |",
        "| --- | --- |",
    ]
    lines.extend(f"| {label} | {VARIANT_DESCRIPTIONS[label]} |" for label in data["variants"])
    if failures:
        lines += [
            "",
            "## Reference failures",
            "",
            "These optional reference requests did not produce validated circuits and were not scored. Unexpected maintained-solver exceptions remain fatal; explicit unsupported requests remain recorded separately.",
            "",
        ]
        lines.extend(
            f"- {row['variant']} D({row['n']},{row['k']}): {row['error_type']}; [full traceback]({row['error_log']})."
            for row in failures
        )
    lines += [
        "",
        "Finite-shot scores are exploratory, not fidelity. Paired t intervals are approximate for reciprocal, potentially heavy-tailed scores. Nonfinite outcomes are explicit; finite-pair exclusions can alter the compared cohort. Noise simulation is bounded; large cases supply structural/exact evidence only. Source variants, runtime, all individual scores and statuses are in comparison.json and CSV.",
        "",
        "No score is taken from the upstream harness's analytical E[s] proxy, and no hardware-wide DD policy is inferred. The optional sparse strategy is not automatically made the default.",
        TABLE_NOTE,
        "",
    ]
    for stem in ("01_resources", "02_scores"):
        lines += [
            f"![{stem}]({figures / (stem + '.png')})",
            "",
            f"[Vector PDF]({figures / (stem + '.pdf')})",
            "",
        ]
    report = root / "report.md"
    report.write_text("\n".join(lines))
    print(f"[saved] {report}\n[figures] {figures}")
    return report


def main() -> None:
    """Run the bounded shared-model comparison from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", default=[f"{n},{k}" for n, k in CASES])
    parser.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    parser.add_argument("--shots", type=int, default=10000)
    parser.add_argument("--correlator-size", type=int, default=4)
    parser.add_argument("--detuning-khz", type=float, default=20.0)
    parser.add_argument("--realizations", type=int, default=2)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--output-dir", type=Path, default=REPO / "benchmark_outputs/comparisons")
    parser.add_argument("--no-noise", action="store_true")
    args = parser.parse_args()
    compare_solutions(
        args.output_dir,
        cases=tuple(tuple(map(int, c.split(","))) for c in args.cases),
        seeds=tuple(map(int, args.seeds.split(","))),
        noise=benchmark.NoiseConfig(
            shots=args.shots,
            detuning_khz=args.detuning_khz,
            max_correlator_size=args.correlator_size,
            n_realizations=args.realizations,
        ),
        baseline=args.baseline,
        noise_max_qubits=0 if args.no_noise else MAX_NOISE_QUBITS,
    )


if __name__ == "__main__":
    main()
