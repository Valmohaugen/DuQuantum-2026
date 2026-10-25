"""Run the local solution workflow through one explicit, reproducible command."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import runpy
import subprocess
import sys
import threading
import time
import traceback
import uuid
from contextlib import ExitStack, contextmanager, redirect_stderr, redirect_stdout
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence, TextIO

import cirq
from tqdm import tqdm

from claude import dicke_prep as dp
from claude.output_paths import figure_root
from claude.scripts import analyze_benchmark_results as analyzer
from claude.scripts import noisy_benchmark as benchmark
from claude.scripts.build_submission import build_submission
from claude.scripts.challenge_calibration import make_challenge_calibration
from claude.scripts.compare_solutions import compare_solutions
from claude.scripts.diagnose import SCORE_CASES, build_report, resolve_report_settings
from claude.validation import MAX_EXACT_QUBITS, validate_preparation

REPO = Path(__file__).resolve().parents[2]
CHECK_POLL_SECONDS = 0.05
CHECK_STOP_SECONDS = 5.0
FULL_CASES = tuple((n, k) for n in range(2, 9) for k in range(1, n))
BONUS_CASES = tuple((n, k) for n in range(2, 16) for k in range(n + 1))
PRESETS = {
    "quick": (((2, 1), (4, 2)), (1,), 1_000, 1, (2, 4, 8)),
    "standard": (SCORE_CASES, (1, 2, 3), 10_000, 2, (4, 8, 16, 30, 60)),
    "full": (FULL_CASES, (1, 2, 3, 4, 5), 10_000, 2, (2, 4, 8, 15, 16, 30, 60, 90)),
}


@dataclass(frozen=True)
class RunConfig:
    """Validated run options, including effective physics settings and absolute paths.

    Instances come from parse_args; counts, seeds and model parameters are checked
    before directories are created. All values are saved in the run manifest.
    """

    mode: str
    preset: str
    cases: tuple[tuple[int, int], ...]
    seeds: tuple[int, ...]
    calibration_seed: int
    noise: benchmark.NoiseConfig
    preparation: dp.PrepConfig
    resource_sizes: tuple[int, ...]
    detuning_levels: tuple[float, ...]
    diagnostic_case: tuple[int, int]
    output_dir: Path
    figures_dir: Path
    results: Path | None
    baseline: Path | None
    fresh: bool
    ideal: bool
    upstream: bool
    comparison: bool
    check: bool
    bonus_check: bool
    bonus_cases: tuple[tuple[int, int], ...]
    plan: bool


def _case(value: str) -> tuple[int, int]:
    parts = tuple(int(item) for item in value.split(","))
    if len(parts) != 2 or not 1 <= parts[0] <= 105 or not 0 <= parts[1] <= parts[0]:
        raise ValueError(f"invalid case {value!r}: require N,n with 1<=N<=105 and 0<=n<=N")
    return parts


def _numbers(value: str, kind: type[int] | type[float]) -> tuple:
    values = tuple(kind(item) for item in value.split(","))
    if not values or len(set(values)) != len(values):
        raise ValueError("comma-separated lists must be nonempty and contain no duplicates")
    return values


def _diagnostic_case(cases: tuple[tuple[int, int], ...]) -> tuple[int, int]:
    """Prefer the largest supported, most balanced selected state for diagnostics."""
    return max(
        (case for case in cases if case[0] <= 10),
        key=lambda case: (case[0], min(case[1], case[0] - case[1]), -case[1]),
        default=(6, 3),
    )


def parse_args(argv: Sequence[str] | None = None) -> RunConfig:
    """Resolve CLI presets and overrides without running experiments or writing files.

    Parameters
    ----------
    argv : sequence of str or None
        Explicit arguments, or process arguments when None.

    Returns
    -------
    RunConfig
        Fully resolved settings. Invalid combinations exit through argparse with
        status 2; --help exits with status 0. Density simulations are capped at 10
        qubits; validate/compare support larger structural constructor checks.
    """
    parser = argparse.ArgumentParser(
        description="Validate, benchmark, compare, export and diagnose the local Dicke solution.",
        epilog="Examples: python -u solution.py --preset quick | python -u solution.py --plan",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--mode", choices=("all", "benchmark", "compare", "diagnose", "validate"), default="all"
    )
    parser.add_argument(
        "--preset",
        choices=PRESETS,
        default="full",
        help="full default: all nontrivial N=2–8 cases plus complete checks; quick/standard are smaller",
    )
    parser.add_argument(
        "--cases", nargs="+", metavar="N,n", help="explicit cases, e.g. 2,1 4,2 6,3"
    )
    parser.add_argument("--nmin", type=int, help="first N in generated range; default 2")
    parser.add_argument("--nmax", type=int, help="last N in generated range")
    parser.add_argument(
        "--all-excitations",
        action="store_true",
        help="range generation includes n=1 through N, rather than floor(N/2)",
    )
    seeds = parser.add_mutually_exclusive_group()
    seeds.add_argument("--seeds", help="comma-separated independent replicate seeds")
    seeds.add_argument("--seed", type=int, help="one replicate seed")
    parser.add_argument("--calibration-seed", type=int, default=1234)
    parser.add_argument("--shots", type=int, help="shots per basis per replicate")
    parser.add_argument(
        "--realizations", type=int, help="detuning realizations within each replicate"
    )
    parser.add_argument(
        "--max-correlator-size",
        "--correlator-size",
        type=int,
        help="full preset defaults to every order; quick/standard default to 4",
    )
    parser.add_argument("--detuning-khz", type=float, default=20.0)
    parser.add_argument("--t1-us", type=float, default=68.0)
    parser.add_argument("--tphi-us", type=float, default=100.0)
    parser.add_argument("--gate-1q-ns", type=float, default=25.0)
    parser.add_argument("--gate-cz-ns", type=float, default=42.0)
    parser.add_argument(
        "--dd-strategy",
        choices=("dense", "sparse"),
        default="dense",
        help="DD-on benchmark policy; paired no-DD is always included",
    )
    parser.add_argument("--beam-width", type=int, default=dp.CONFIG.beam_width)
    parser.add_argument("--search-seconds", type=float, default=dp.CONFIG.search_time_s)
    parser.add_argument(
        "--sparse-min-idle-slots", type=int, default=dp.CONFIG.sparse_min_idle_slots
    )
    parser.add_argument("--max-routing-qubits", type=int, default=dp.CONFIG.max_routing_qubits)
    parser.add_argument(
        "--construction",
        choices=("optimized", "analytic"),
        default=dp.CONFIG.construction,
        help="optimized four-CZ/square synthesis or the previous analytical constructor",
    )
    parser.add_argument("--resource-sizes", help="comma-separated constructor-only scaling probes")
    parser.add_argument(
        "--detuning-levels",
        default="0,10,20,50",
        help="comma-separated diagnostic sensitivity levels in kHz",
    )
    parser.add_argument(
        "--diagnostic-case", metavar="N,n", help="illustrative distribution/circuit case, N<=10"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="run a new benchmark instead of resuming a matching checkpoint",
    )
    parser.add_argument(
        "--no-ideal", action="store_true", help="omit the ideal finite-shot baseline"
    )
    parser.add_argument(
        "--no-upstream",
        action="store_true",
        help="compare only the three maintained hybrid variants",
    )
    comparison = parser.add_mutually_exclusive_group()
    comparison.add_argument(
        "--comparison", action="store_true", help="include solution comparison in all mode"
    )
    comparison.add_argument(
        "--skip-comparison", action="store_true", help="omit comparison (the default in all mode)"
    )
    parser.add_argument(
        "--results",
        type=Path,
        help="existing raw benchmark JSON, only with --mode diagnose; recorded model settings take precedence",
    )
    parser.add_argument(
        "--baseline", type=Path, help="optional frozen module to include in the comparison"
    )
    parser.add_argument("--output-dir", type=Path, default=REPO / "benchmark_outputs")
    parser.add_argument("--figures-dir", type=Path, default=figure_root())
    parser.add_argument(
        "--check",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Python software checks; on for an unfocused full all-mode run",
    )
    parser.add_argument(
        "--bonus-check",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="check both exported entry points through N=15; on for an unfocused full all-mode run",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="print resolved settings and stages without writing or running",
    )
    tokens = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(tokens)
    try:
        preset_cases, preset_seeds, shots, realizations, resources = PRESETS[args.preset]
        if args.cases and (args.nmin is not None or args.nmax is not None or args.all_excitations):
            raise ValueError("choose --cases or generated-range options, not both")
        if args.nmin is not None and args.nmax is None:
            raise ValueError("--nmin requires --nmax")
        if args.all_excitations and args.nmax is None:
            raise ValueError("--all-excitations requires --nmax")
        if args.nmax is not None:
            nmin = args.nmin if args.nmin is not None else 2
            if not 2 <= nmin <= args.nmax <= 105:
                raise ValueError("generated range requires 2<=nmin<=nmax<=105")
            cases = tuple(
                (n, k)
                for n in range(nmin, args.nmax + 1)
                for k in range(1, (n if args.all_excitations else n // 2) + 1)
            )
        else:
            cases = tuple(_case(value) for value in args.cases) if args.cases else preset_cases
        if len(set(cases)) != len(cases):
            raise ValueError("duplicate cases are not allowed")
        if args.mode in {"all", "benchmark"} and any(not 2 <= n <= 10 or k == 0 for n, k in cases):
            raise ValueError(
                "benchmark/all cases require 2<=N<=10 and n>=1; use validate/compare for larger circuits"
            )
        selected_seeds = (
            _numbers(args.seeds, int)
            if args.seeds is not None
            else (args.seed,)
            if args.seed is not None
            else preset_seeds
        )
        if min(selected_seeds) < 0 or args.calibration_seed < 0:
            raise ValueError("seeds must be nonnegative integers")
        focused_cases = args.cases is not None or args.nmax is not None
        thorough = args.preset == "full" and args.mode == "all" and not focused_cases
        check = thorough if args.check is None else args.check
        bonus_check = thorough if args.bonus_check is None else args.bonus_check
        if bonus_check and args.mode not in {"all", "validate"}:
            raise ValueError("--bonus-check requires --mode all or validate")
        bonus_cases = (cases if focused_cases else BONUS_CASES) if bonus_check else ()
        if any(not 2 <= n <= 15 for n, k in bonus_cases):
            raise ValueError("bonus checks require cases with 2<=N<=15")
        noise = benchmark.NoiseConfig(
            t1_us=args.t1_us,
            tphi_us=args.tphi_us,
            t_1q_ns=args.gate_1q_ns,
            t_cz_ns=args.gate_cz_ns,
            detuning_khz=args.detuning_khz,
            n_realizations=args.realizations if args.realizations is not None else realizations,
            shots=args.shots if args.shots is not None else shots,
            max_correlator_size=args.max_correlator_size
            if args.max_correlator_size is not None
            else max(n for n, _ in cases)
            if args.preset == "full"
            else 4,
            seed=selected_seeds[0],
            noise_seed=selected_seeds[0],
        )
        preparation = dp.PrepConfig(
            beam_width=args.beam_width,
            search_time_s=args.search_seconds,
            dd_strategy=args.dd_strategy,
            sparse_min_idle_slots=args.sparse_min_idle_slots,
            max_routing_qubits=args.max_routing_qubits,
            construction=args.construction,
        )
        sizes = (
            _numbers(args.resource_sizes, int)
            if args.resource_sizes is not None
            else tuple(sorted({n for n, _ in cases if n >= 2})) or (2,)
            if focused_cases
            else resources
        )
        if min(sizes) < 2 or max(sizes) > 105:
            raise ValueError("resource sizes must be between 2 and 105")
        levels = _numbers(args.detuning_levels, float)
        if any(not (0 <= value < float("inf")) for value in levels):
            raise ValueError("detuning levels must be finite and nonnegative")
        diagnostic_case = (
            _case(args.diagnostic_case) if args.diagnostic_case else _diagnostic_case(cases)
        )
        if diagnostic_case[0] > 10:
            raise ValueError("diagnostic case requires N<=10")
        if args.results is not None and args.mode != "diagnose":
            raise ValueError("--results is only supported with --mode diagnose")
        recorded_options = {
            "--construction",
            "--calibration-seed",
            "--shots",
            "--realizations",
            "--max-correlator-size",
            "--correlator-size",
            "--detuning-khz",
            "--t1-us",
            "--tphi-us",
            "--gate-1q-ns",
            "--gate-cz-ns",
            "--dd-strategy",
            "--beam-width",
            "--search-seconds",
            "--sparse-min-idle-slots",
            "--max-routing-qubits",
        }
        if args.results is not None and any(
            token.split("=", 1)[0] in recorded_options for token in tokens
        ):
            raise ValueError(
                "--results uses its recorded model and preparation settings; start a new benchmark to change them"
            )
        for path in (args.results, args.baseline):
            if path is not None and not path.is_file():
                raise ValueError(f"input file does not exist: {path}")
        if args.results is not None:
            dataset = analyzer.load_results(args.results)
            if analyzer.has_complete_provenance(dataset):
                recorded = dataset["signature"]["settings"]
                if args.seed is None and args.seeds is None:
                    selected_seeds = tuple(recorded["benchmark_seeds"])
                if args.cases is None and args.nmax is None:
                    cases = tuple(tuple(case) for case in recorded["benchmark_cases"])
            args.calibration_seed, noise, preparation = resolve_report_settings(
                dataset, diagnostic_seed=selected_seeds[0]
            )
            if args.diagnostic_case is None:
                diagnostic_case = _diagnostic_case(cases)
    except (TypeError, ValueError) as exc:
        parser.error(str(exc))
    return RunConfig(
        mode=args.mode,
        preset=args.preset,
        cases=cases,
        seeds=selected_seeds,
        calibration_seed=args.calibration_seed,
        noise=noise,
        preparation=preparation,
        resource_sizes=sizes,
        detuning_levels=levels,
        diagnostic_case=diagnostic_case,
        output_dir=args.output_dir.expanduser().resolve(),
        figures_dir=args.figures_dir.expanduser().resolve(),
        results=args.results.resolve() if args.results is not None else None,
        baseline=args.baseline.resolve() if args.baseline is not None else None,
        fresh=args.fresh,
        ideal=not args.no_ideal,
        upstream=not args.no_upstream,
        comparison=args.comparison,
        check=check,
        bonus_check=bonus_check,
        bonus_cases=bonus_cases,
        plan=args.plan,
    )


def _stages(config: RunConfig) -> list[str]:
    stages = ["checks"] if config.check else []
    if config.mode in {"all", "benchmark", "validate"}:
        stages.append("validation")
    if config.bonus_check:
        stages.extend(("submission", "bonus_validation"))
    if config.mode in {"all", "benchmark"}:
        stages.extend(("benchmark", "diagnostics"))
    if config.mode == "diagnose":
        stages.append("diagnostics")
    if config.mode == "compare" or (config.mode == "all" and config.comparison):
        stages.append("comparison")
    if config.mode == "all" and not config.bonus_check:
        stages.append("submission")
    return stages


@contextmanager
def _settings(config: RunConfig, figures: Path) -> Iterator[None]:
    overrides = {
        "OUTPUT_DIR": config.output_dir,
        "RESUME_FROM_CHECKPOINT": not config.fresh,
        "CALIBRATION_SEED": config.calibration_seed,
        "BENCHMARK_SEEDS": config.seeds,
        "BENCHMARK_CASES": config.cases,
        "DETUNING_KHZ": config.noise.detuning_khz,
        "SHOTS": config.noise.shots,
        "RUN_IDEAL_BASELINE": config.ideal,
        "_NOISE_OVERRIDE": config.noise,
        "_PREPARATION_OVERRIDE": config.preparation,
    }
    previous = {name: getattr(benchmark, name) for name in overrides}
    previous_figures = os.environ.get("DUQUANTUM_FIGURES_DIR")
    try:
        for name, value in overrides.items():
            setattr(benchmark, name, value)
        os.environ["DUQUANTUM_FIGURES_DIR"] = str(figures)
        yield
    finally:
        for name, value in previous.items():
            setattr(benchmark, name, value)
        if previous_figures is None:
            os.environ.pop("DUQUANTUM_FIGURES_DIR", None)
        else:
            os.environ["DUQUANTUM_FIGURES_DIR"] = previous_figures


class _Tee:
    def __init__(self, console: TextIO, log: TextIO) -> None:
        self.console, self.log = console, log

    def write(self, value: str) -> int:
        self.console.write(value)
        self.log.write(value)
        self.flush()
        return len(value)

    def flush(self) -> None:
        self.console.flush()
        self.log.flush()

    def isatty(self) -> bool:
        return False


def _checks(
    root: Path,
    *,
    commands: Sequence[tuple[str, list[str]]] | None = None,
    console: TextIO | None = None,
    log: TextIO | None = None,
) -> Path:
    """Run gates with compact terminal progress and complete, separately saved output."""
    events_path = root / "check-progress.jsonl"
    events_path.write_text("")
    commands = (
        commands
        if commands is not None
        else [
            ("lint", [sys.executable, "-u", "-m", "claude.scripts.check_quality", "lint"]),
            ("format", [sys.executable, "-u", "-m", "claude.scripts.check_quality", "format"]),
            ("artifacts", [sys.executable, "-u", "-m", "claude.scripts.check_artifacts"]),
            (
                "pytest",
                [
                    sys.executable,
                    "-u",
                    "-m",
                    "claude.scripts.check_quality",
                    "pytest",
                    "--progress-file",
                    str(events_path),
                    "--",
                    "claude/tests",
                    "-v",
                ],
            ),
        ]
    )
    console = console if console is not None else sys.stderr
    preliminary = sum(name != "pytest" for name, _ in commands)
    state = {
        "status": "running",
        "commands": [cmd for _, cmd in commands],
        "completed_checks": 0,
        "total_checks": None,
        "tests_completed": 0,
        "progress_events": str(events_path),
    }
    path = root / "checks.json"
    with ExitStack() as stack:
        log = (
            log if log is not None else stack.enter_context((root / "checks-output.log").open("w"))
        )
        events = stack.enter_context(events_path.open())
        bar = tqdm(
            total=None,
            desc="[checks]",
            unit="check",
            file=console,
            dynamic_ncols=True,
            disable=not console.isatty(),
        )
        pending = ""
        interrupted = False

        def consume_progress() -> None:
            nonlocal pending, interrupted
            pending += events.read()
            while "\n" in pending:
                line, pending = pending.split("\n", 1)
                if not line:
                    continue
                event = json.loads(line)
                if event["event"] == "collected" and not event["errors"]:
                    state["total_checks"] = preliminary + event["total"]
                    bar.total = state["total_checks"]
                elif event["event"] == "completed":
                    completed = event["completed"]
                    bar.update(completed - state["tests_completed"])
                    state["tests_completed"] = completed
                    state["completed_checks"] = preliminary + completed
                elif event["event"] == "interrupted":
                    interrupted = event["keyboard"]
                bar.refresh()

        try:
            for name, command in commands:
                bar.set_description(f"[checks] {name}")
                if bar.disable:
                    print(f"[check] {name}: running", file=console, flush=True)
                log.write(f"[check] {' '.join(command)}\n")
                log.flush()
                lines: list[str] = []
                read_errors: list[Exception] = []
                with subprocess.Popen(
                    command,
                    cwd=REPO,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                ) as process:
                    assert process.stdout is not None

                    def drain() -> None:
                        try:
                            for line in process.stdout:
                                lines.append(line)
                                log.write(line)
                                log.flush()
                        except Exception as exc:
                            read_errors.append(exc)

                    reader = threading.Thread(target=drain, daemon=True)
                    reader.start()
                    try:
                        while process.poll() is None:
                            consume_progress()
                            if read_errors:
                                raise RuntimeError("could not save check output") from read_errors[
                                    0
                                ]
                            time.sleep(CHECK_POLL_SECONDS)
                        reader.join()
                        consume_progress()
                        if read_errors:
                            raise RuntimeError("could not save check output") from read_errors[0]
                        if interrupted:
                            raise KeyboardInterrupt()
                        if process.returncode:
                            raise RuntimeError(f"quality check failed: {name}: {' '.join(command)}")
                    except BaseException:
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=CHECK_STOP_SECONDS)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                        reader.join()
                        consume_progress()
                        bar.clear()
                        console.write("".join(lines))
                        console.flush()
                        raise
                if name != "pytest":
                    state["completed_checks"] += 1
                    bar.update(1)
                elif (
                    state["total_checks"] is None
                    or state["completed_checks"] != state["total_checks"]
                ):
                    raise RuntimeError("pytest progress did not account for all collected tests")
                if bar.disable:
                    print(f"[check] {name}: passed", file=console, flush=True)
            state["status"] = "passed"
        except BaseException as exc:
            state["status"] = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
            state["error"] = f"{type(exc).__name__}: {exc}"
            bar.set_description(f"[checks] {state['status']}")
            raise
        finally:
            bar.close()
            benchmark.atomic_write_json(path, state)
    print(f"[check] Passed; {state['tests_completed']} tests completed", file=console, flush=True)
    return path


def _validate(config: RunConfig, destination: Path) -> Path:
    cal = make_challenge_calibration(config.calibration_seed)
    rows = []
    for n, k in config.cases:
        started = time.perf_counter()
        circuit, qubits = dp.create_dicke_state(n, k, *cal, config=config.preparation)
        fidelity = validate_preparation(
            circuit, qubits, n, k, cal, check_state=n <= MAX_EXACT_QUBITS
        )
        rows.append(
            {
                "n": n,
                "k": k,
                "fidelity": fidelity,
                "rules": "ok",
                "moments": len(circuit),
                "cz_count": sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                "build_seconds": time.perf_counter() - started,
                "state_check": "exact" if fidelity is not None else "not simulated: N>16",
            }
        )
        print(
            f"[valid] D({n},{k}): rules ok; {len(circuit)} moments; fidelity {fidelity if fidelity is not None else 'not simulated'}",
            flush=True,
        )
    benchmark.atomic_write_json(
        destination,
        {
            "calibration_seed": config.calibration_seed,
            "preparation": asdict(config.preparation),
            "cases": rows,
        },
    )
    return destination


def _bonus_validation(
    config: RunConfig,
    root: Path,
    submission: Path,
    *,
    cases: tuple[tuple[int, int], ...] = BONUS_CASES,
) -> Path:
    """Validate both actual exported functions exactly; save complete/partial evidence.

    Inputs are resolved settings, a unique run root, a standalone export and
    explicit (N,n) cases within the confirmed 2–15 range. Main uses the selected
    calibration; bonus uses its allowed full-device construction. State vectors
    are at most 2**15. JSON/CSV preserve partial results on failure; invalid
    construction, state or native-device behavior raises with the failing case.
    Returns the saved coverage report. No hardware or Git writes occur.
    """
    if (
        not cases
        or len(set(cases)) != len(cases)
        or any(not 2 <= n <= 15 or not 0 <= k <= n for n, k in cases)
    ):
        raise ValueError("bonus cases must be unique with 2<=N<=15 and 0<=n<=N")
    destination = root / "bonus_validation"
    destination.mkdir(parents=True, exist_ok=False)
    module = runpy.run_path(str(submission), run_name="_validated_submission")
    cal = make_challenge_calibration(config.calibration_seed)
    data = {
        "complete": False,
        "requested_cases": cases,
        "entrypoints": ["main", "bonus"],
        "calibration_seed": config.calibration_seed,
        "preparation": asdict(config.preparation),
        "submission_sha256": hashlib.sha256(submission.read_bytes()).hexdigest(),
        "results": [],
    }
    fields = (
        "entrypoint",
        "n",
        "k",
        "rules",
        "fidelity",
        "cz_count",
        "moments",
        "build_seconds",
        "error",
    )

    def save_csv() -> None:
        with (destination / "results.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(data["results"])

    print(
        f"[bonus] Exact/rule validation of both exported entry points: {len(cases)} cases, {2 * len(cases)} circuits.",
        flush=True,
    )
    for n, k in cases:
        for label, function in (
            ("main", "create_dicke_state"),
            ("bonus", "create_dicke_state_adaptive"),
        ):
            row = {"entrypoint": label, "n": n, "k": k}
            started = time.perf_counter()
            try:
                circuit, qubits = (
                    module[function](n, k, *cal) if label == "main" else module[function](n, k)
                )
                build_seconds = time.perf_counter() - started
                fidelity = validate_preparation(
                    circuit, qubits, n, k, cal if label == "main" else None
                )
                row.update(
                    rules="ok",
                    fidelity=fidelity,
                    cz_count=sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                    moments=len(circuit),
                    build_seconds=build_seconds,
                )
            except Exception as exc:
                row.update(rules="failed", error=f"{type(exc).__name__}: {exc}")
                data["results"].append(row)
                benchmark.atomic_write_json(destination / "results.json", data)
                save_csv()
                raise ValueError(
                    f"bonus-range validation failed for {label} D({n},{k}): {exc}"
                ) from exc
            data["results"].append(row)
            benchmark.atomic_write_json(destination / "results.json", data)
            save_csv()
            print(
                f"[bonus {len(data['results'])}/{2 * len(cases)}] {label} D({n},{k}): {row['cz_count']} CZ; {row['moments']} moments; fidelity {fidelity:.12f}; rules ok",
                flush=True,
            )
    data["complete"] = True
    benchmark.atomic_write_json(destination / "results.json", data)
    save_csv()
    lines = [
        "# Exported main and bonus validation",
        "",
        f"All {len(data['results'])} circuits passed exact state and native-device checks across {len(cases)} cases.",
        "",
        "Main uses the selected calibration. Bonus uses the challenge's allowed full-device, noise-independent construction. Both use the actual configured standalone export. No density-noise score is inferred from these pure-state checks.",
        "",
        "[All numeric results](results.json) · [CSV](results.csv)",
        "",
        "| N | n | Entry point | CZ | Moments | Exact fidelity |",
        "| ---: | ---: | --- | ---: | ---: | ---: |",
    ]
    lines.extend(
        f"| {r['n']} | {r['k']} | {r['entrypoint']} | {r['cz_count']} | {r['moments']} | {r['fidelity']:.12f} |"
        for r in data["results"]
    )
    report = destination / "report.md"
    report.write_text("\n".join(lines) + "\n")
    return report


def main(argv: Sequence[str] | None = None) -> int:
    """Execute selected stages, saving a manifest/log/index and returning exit status.

    Parameters
    ----------
    argv : sequence of str or None
        CLI arguments; None reads sys.argv. --plan is side-effect free.

    Returns
    -------
    int
        0 on success, 1 on stage failure, 130 on interruption. Failures retain the full traceback,
        partial output paths and a failed run.json. Temporary module/environment
        overrides are restored on failure as well as success. No hardware or Git
        writes occur. Invalid options use argparse's SystemExit(2).
    """
    config = parse_args(argv)
    resolved = json.loads(json.dumps(asdict(config), default=str, allow_nan=False))
    stages = _stages(config)
    if config.plan:
        print(json.dumps({"stages": stages, "configuration": resolved}, indent=2, allow_nan=False))
        return 0
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    root = config.output_dir / "solution_runs" / run_id
    root.mkdir(parents=True, exist_ok=False)
    figures = config.figures_dir / "solution_runs" / run_id
    manifest = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "running",
        "configuration": resolved,
        "stages": stages,
        "outputs": {},
        "figures_dir": str(figures),
        "python": platform.python_version(),
        "runtime": {
            name: importlib.metadata.version(name)
            for name in ("cirq", "cirq-google", "numpy", "scipy", "networkx", "matplotlib")
        },
        "hardware": f"local CPU; {platform.machine()}",
        "git_commit": subprocess.run(
            ["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "working_tree_dirty": bool(
            subprocess.run(
                ["git", "-C", str(REPO), "status", "--porcelain"], capture_output=True, text=True
            ).stdout.strip()
        ),
        "sources": {
            str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                Path(__file__).resolve(),
                REPO / "solution.py",
                REPO / "claude/dicke_prep.py",
                REPO / "claude/validation.py",
                REPO / "claude/scripts/build_submission.py",
            )
        },
    }
    benchmark.atomic_write_json(root / "run.json", manifest)
    started = time.perf_counter()
    result = 0
    with (
        (root / "terminal-output.log").open("w") as log,
        redirect_stdout(_Tee(sys.stdout, log)),
        redirect_stderr(_Tee(sys.stderr, log)),
        _settings(config, figures),
    ):
        print(
            f"[setup] Run: {root}\n[setup] Figures: {figures}\n[setup] Seeds: {config.seeds}; calibration seed: {config.calibration_seed}"
        )
        print(
            f"[setup] Preset {config.preset}; {config.noise.shots} shots; {config.noise.n_realizations} detuning realizations; DD={config.preparation.dd_strategy}; construction={config.preparation.construction}"
        )
        print(
            f"[setup] {len(config.cases)} benchmark cases; X cutoff={config.noise.max_correlator_size}; software checks={config.check}; bonus cases={len(config.bonus_cases)}",
            flush=True,
        )
        if config.results is not None:
            print(
                "[data] Existing dataset selected: diagnostics will use its recorded model and preparation settings."
            )
        try:
            for index, stage in enumerate(stages, 1):
                print(f"\n[{index}/{len(stages)}] {stage}", flush=True)
                if stage == "checks":
                    path = _checks(root, console=sys.stderr.console, log=log)
                elif stage == "validation":
                    path = _validate(config, root / "validation.json")
                elif stage == "bonus_validation":
                    path = _bonus_validation(
                        config,
                        root,
                        Path(manifest["outputs"]["submission"]),
                        cases=config.bonus_cases,
                    )
                elif stage == "benchmark":
                    path = benchmark.main()
                    manifest["outputs"][stage] = str(path)
                    benchmark.atomic_write_json(root / "run.json", manifest)
                    with redirect_stdout(log), redirect_stderr(log):
                        analysis_path = analyzer.main(path, root / "analysis")
                    manifest["outputs"]["analysis"] = str(analysis_path)
                elif stage == "diagnostics":
                    data_path = (
                        Path(manifest["outputs"]["benchmark"])
                        if "benchmark" in manifest["outputs"]
                        else config.results
                    )
                    overrides = (
                        {}
                        if data_path is not None
                        else {
                            "noise_config": config.noise,
                            "calibration_seed": config.calibration_seed,
                            "preparation_config": config.preparation,
                        }
                    )
                    path = build_report(
                        root / "diagnostics",
                        *config.diagnostic_case,
                        results_path=data_path,
                        resource_sizes=config.resource_sizes,
                        detuning_levels=config.detuning_levels,
                        diagnostic_seed=config.seeds[0],
                        **overrides,
                    )
                elif stage == "comparison":
                    path = compare_solutions(
                        output_dir=root / "comparisons",
                        cases=config.cases,
                        seeds=config.seeds,
                        noise=config.noise,
                        include_upstream=config.upstream,
                        baseline=config.baseline,
                        calibration_seed=config.calibration_seed,
                        hybrid_config=config.preparation,
                    )
                    comparison_data = json.loads(path.with_name("comparison.json").read_text())
                    manifest["reference_error_count"] = comparison_data.get(
                        "reference_error_count", 0
                    )
                else:
                    path = build_submission(
                        root / "submission.py", configuration=config.preparation
                    )
                    print(f"[saved] Local Python export: {path}", flush=True)
                manifest["outputs"][stage] = str(path)
                benchmark.atomic_write_json(root / "run.json", manifest)
            manifest["status"] = "complete"
        except (Exception, KeyboardInterrupt) as exc:
            result = 130 if isinstance(exc, KeyboardInterrupt) else 1
            manifest["status"] = "failed"
            manifest["error"] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
            print(f"[failed] Partial results and traceback saved in {root}", flush=True)
        manifest["elapsed_seconds"] = time.perf_counter() - started
        benchmark.atomic_write_json(root / "run.json", manifest)
        lines = [
            "# Solution run",
            "",
            f"Status: **{manifest['status']}**. Run `{run_id}`.",
            "",
            f"Elapsed: {manifest['elapsed_seconds']:.2f} s. CPU simulation. Seeds {config.seeds}; calibration seed {config.calibration_seed}.",
            "",
            "Resolved configuration and source hashes: [run.json](run.json). Full terminal output: [terminal-output.log](terminal-output.log).",
            "",
        ]
        lines.extend(f"- [{name}]({path})" for name, path in manifest["outputs"].items())
        if manifest.get("reference_error_count"):
            lines.extend(
                (
                    "",
                    f"Optional reference failures: **{manifest['reference_error_count']}**. Failed requests were excluded from scoring; the comparison report links their complete tracebacks.",
                )
            )
        lines.extend(
            (
                "",
                f"All saved figures for this invocation: `{figures}`.",
                "",
                "Benchmark checkpoints live under the configured output root and can be reused only when their source/configuration fingerprints match. Use --fresh for a separate repeat. Finite-shot scores are noisy and E[s] is a proxy, not an expected reciprocal score.",
            )
        )
        if result:
            lines.extend(
                (
                    "",
                    f"Failure: `{manifest['error']}`. Inspect terminal-output.log for the complete traceback.",
                )
            )
        (root / "report.md").write_text("\n".join(lines) + "\n")
        print(
            f"[{'done' if not result else 'failed'}] Run index: {root / 'report.md'}\n[saved] Terminal log: {root / 'terminal-output.log'}"
        )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
