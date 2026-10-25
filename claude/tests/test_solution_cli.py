"""One command must apply options, save every stage, and preserve module state."""

from __future__ import annotations

import inspect
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_cli_presets_and_explicit_overrides() -> None:
    from claude.scripts.run_solution import parse_args

    args = parse_args(
        [
            "--preset",
            "quick",
            "--cases",
            "2,1",
            "4,2",
            "--seed",
            "42",
            "--shots",
            "37",
            "--dd-strategy",
            "sparse",
        ]
    )
    assert args.cases == ((2, 1), (4, 2))
    assert args.seeds == (42,)
    assert args.noise.shots == 37 and args.noise.n_realizations == 1
    assert args.preparation.dd_strategy == "sparse"
    assert parse_args([]).mode == "all"


def test_default_is_full_and_covers_all_stages_and_bonus_cases() -> None:
    from claude.scripts.run_solution import _stages, parse_args

    config = parse_args([])
    assert config.preset == "full" and config.check and config.bonus_check
    assert config.cases == tuple((n, k) for n in range(2, 9) for k in range(1, n))
    assert config.seeds == (1, 2, 3, 4, 5)
    assert config.noise.shots == 10000 and config.noise.n_realizations == 2
    assert config.noise.max_correlator_size == 8
    assert config.diagnostic_case == (8, 4)
    assert config.bonus_cases == tuple((n, k) for n in range(2, 16) for k in range(n + 1))
    assert len(config.bonus_cases) == 133
    stages = _stages(config)
    assert stages == [
        "checks",
        "validation",
        "submission",
        "bonus_validation",
        "benchmark",
        "analysis",
        "diagnostics",
        "comparison",
    ]


def test_focused_runs_skip_broad_suites_unless_requested() -> None:
    from claude.scripts.run_solution import parse_args

    for argv in (
        ["--preset", "quick"],
        ["--preset", "standard"],
        ["--cases", "4,2"],
        ["--mode", "validate", "--cases", "15,7"],
    ):
        cfg = parse_args(argv)
        assert not cfg.check and not cfg.bonus_check
    cfg = parse_args(["--cases", "4,2"])
    assert cfg.resource_sizes == (4,)
    cfg = parse_args(["--cases", "4,2", "--check", "--bonus-check"])
    assert cfg.check and cfg.bonus_check and cfg.bonus_cases == ((4, 2),)
    cfg = parse_args(["--no-check", "--no-bonus-check", "--max-correlator-size", "3"])
    assert not cfg.check and not cfg.bonus_check and cfg.noise.max_correlator_size == 3


def test_bonus_coverage_checks_actual_configured_export(tmp_path: Path) -> None:
    from claude.scripts.build_submission import build_submission
    from claude.scripts.run_solution import _bonus_validation, parse_args

    config = parse_args(["--preset", "quick", "--construction", "analytic"])
    export = build_submission(tmp_path / "submission.py", configuration=config.preparation)
    report = _bonus_validation(config, tmp_path, export, cases=((2, 0), (2, 1), (2, 2), (4, 2)))
    data = json.loads(report.with_name("results.json").read_text())
    assert data["complete"] and len(data["results"]) == 8
    assert {row["entrypoint"] for row in data["results"]} == {"main", "bonus"}
    assert all(row["fidelity"] == pytest.approx(1.0, abs=1e-10) for row in data["results"])
    assert all(row["cz_count"] == 12 for row in data["results"] if row["n"] == 4)
    assert report.with_name("results.csv").exists()


def test_bonus_failure_keeps_partial_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claude.scripts import run_solution
    from claude.scripts.build_submission import build_submission

    config = run_solution.parse_args(["--preset", "quick"])
    export = build_submission(tmp_path / "submission.py", configuration=config.preparation)

    def fail(*args: object, **kwargs: object) -> None:
        raise ValueError("deliberate exact-state failure")

    monkeypatch.setattr(run_solution, "validate_preparation", fail)
    with pytest.raises(ValueError, match=r"main D\(2,1\)"):
        run_solution._bonus_validation(config, tmp_path, export, cases=((2, 1),))
    data = json.loads((tmp_path / "bonus_validation/results.json").read_text())
    assert not data["complete"] and data["results"][0]["rules"] == "failed"
    assert "deliberate exact-state failure" in data["results"][0]["error"]
    assert (tmp_path / "bonus_validation/results.csv").exists()


@pytest.mark.parametrize("excitations", [0, 1])
def test_focused_single_qubit_validation_is_still_supported(excitations: int) -> None:
    from claude.scripts.run_solution import parse_args

    cfg = parse_args(["--mode", "validate", "--cases", f"1,{excitations}"])
    assert cfg.cases == ((1, excitations),) and cfg.resource_sizes == (2,)


def test_bonus_interrupt_keeps_completed_csv_rows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claude.scripts import run_solution
    from claude.scripts.build_submission import build_submission

    cfg = run_solution.parse_args(["--preset", "quick"])
    export = build_submission(tmp_path / "submission.py", configuration=cfg.preparation)
    validate = run_solution.validate_preparation
    seen = 0

    def interrupt(*args: object, **kwargs: object) -> float | None:
        nonlocal seen
        seen += 1
        if seen == 2:
            raise KeyboardInterrupt()
        return validate(*args, **kwargs)

    monkeypatch.setattr(run_solution, "validate_preparation", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run_solution._bonus_validation(cfg, tmp_path, export, cases=((2, 1),))
    data = json.loads((tmp_path / "bonus_validation/results.json").read_text())
    assert not data["complete"] and len(data["results"]) == 1
    csv = (tmp_path / "bonus_validation/results.csv").read_text().splitlines()
    assert len(csv) == 2 and "main" in csv[1]


@pytest.mark.parametrize(
    "argv",
    [
        ["--shots", "0"],
        ["--seeds", "1,1"],
        ["--cases", "2,3"],
        ["--preset", "quick", "--cases", "2,1", "--nmax", "4"],
        ["--t1-us", "-1"],
        ["--mode", "benchmark", "--cases", "15,7"],
        ["--mode", "compare", "--bonus-check"],
        ["--mode", "validate", "--cases", "16,8", "--bonus-check"],
    ],
)
def test_invalid_cli_options_are_rejected(argv: list[str]) -> None:
    from claude.scripts.run_solution import parse_args

    with pytest.raises(SystemExit) as exc:
        parse_args(argv)
    assert exc.value.code == 2


def test_help_and_plan_do_not_launch_experiments(tmp_path: Path) -> None:
    from claude.scripts import run_solution  # feature must exist before executing the entry point

    assert run_solution is not None
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    for args in (
        ["--help"],
        ["--plan", "--output-dir", str(tmp_path / "data")],
        ["--preset", "quick", "--plan", "--output-dir", str(tmp_path / "data")],
    ):
        result = subprocess.run(
            [sys.executable, str(REPO / "solution.py"), *args],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        assert "[seed]" not in result.stdout
    assert not (tmp_path / "data").exists()


def test_existing_data_does_not_silently_ignore_explicit_model_options(tmp_path: Path) -> None:
    from claude.scripts.run_solution import parse_args

    path = tmp_path / "data.json"
    path.write_text("{}")
    with pytest.raises(SystemExit) as exc:
        parse_args(["--mode", "diagnose", "--results", str(path), "--shots", "37"])
    assert exc.value.code == 2


def test_effective_model_and_preparation_changes_cannot_reuse_a_checkpoint(tmp_path: Path) -> None:
    from claude.scripts import noisy_benchmark as benchmark
    from claude.scripts.run_solution import _settings, parse_args

    paths = []
    for override in (
        [],
        ["--shots", "37"],
        ["--realizations", "3"],
        ["--dd-strategy", "sparse"],
        ["--calibration-seed", "8"],
    ):
        config = parse_args(["--preset", "quick", "--output-dir", str(tmp_path), *override])
        with _settings(config, tmp_path / "figs"):
            paths.append(benchmark.run_directory(benchmark.benchmark_signature()))
    assert len(set(paths)) == len(paths)
    assert not (tmp_path / "runs").exists()


def test_one_command_runs_every_stage_and_restores_options(tmp_path: Path) -> None:
    from claude.scripts import noisy_benchmark as benchmark
    from claude.scripts.compare_solutions import CALIBRATION_SEED
    from claude.scripts.run_solution import main

    before = (
        benchmark.SHOTS,
        benchmark.BENCHMARK_CASES,
        benchmark.CALIBRATION_SEED,
        CALIBRATION_SEED,
        os.environ.get("DUQUANTUM_FIGURES_DIR"),
    )
    args = [
        "--preset",
        "quick",
        "--cases",
        "2,1",
        "--seed",
        "7",
        "--shots",
        "37",
        "--realizations",
        "1",
        "--calibration-seed",
        "8",
        "--dd-strategy",
        "sparse",
        "--resource-sizes",
        "2",
        "--detuning-levels",
        "0",
        "--no-upstream",
        "--no-ideal",
        "--output-dir",
        str(tmp_path / "data"),
        "--figures-dir",
        str(tmp_path / "figs"),
    ]
    assert main(args) == 0
    manifests = list((tmp_path / "data" / "solution_runs").glob("*/run.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text())
    assert manifest["status"] == "complete"
    assert set(manifest["outputs"]) >= {
        "validation",
        "benchmark",
        "analysis",
        "diagnostics",
        "comparison",
        "submission",
    }
    for path in manifest["outputs"].values():
        assert Path(path).exists(), path
    raw = json.loads(Path(manifest["outputs"]["benchmark"]).read_text())
    assert raw["signature"]["settings"]["shots"] == 37
    assert raw["signature"]["settings"]["calibration_seed"] == 8
    assert raw["signature"]["preparation"]["True"]["dd_strategy"] == "sparse"
    report = json.loads(
        (Path(manifest["outputs"]["diagnostics"]).parent / "diagnostics.json").read_text()
    )
    assert report["calibration_seed"] == 8 and report["noise"]["shots"] == 37
    assert report["preparation"]["dd"]["dd_strategy"] == "sparse"
    assert len(report["figures"]) == 8
    exported = runpy.run_path(manifest["outputs"]["submission"])
    assert exported["CONFIG"].dd_strategy == "sparse"
    assert (
        inspect.signature(exported["create_dicke_state"]).parameters["config"].default
        == exported["CONFIG"]
    )
    assert (manifests[0].parent / "terminal-output.log").stat().st_size > 0
    assert before == (
        benchmark.SHOTS,
        benchmark.BENCHMARK_CASES,
        benchmark.CALIBRATION_SEED,
        CALIBRATION_SEED,
        os.environ.get("DUQUANTUM_FIGURES_DIR"),
    )
    # Existing-data plans and manifests must describe the actual recorded model.
    from claude.scripts.run_solution import parse_args

    resumed = parse_args(["--mode", "diagnose", "--results", manifest["outputs"]["benchmark"]])
    assert resumed.calibration_seed == 8
    assert resumed.noise.shots == 37 and resumed.noise.n_realizations == 1
    assert resumed.preparation.dd_strategy == "sparse"
    assert resumed.cases == ((2, 1),) and resumed.seeds == (7,)
    assert resumed.diagnostic_case == (2, 1)


def test_failed_run_saves_traceback_and_restores_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claude import dicke_prep as dp
    from claude.scripts import noisy_benchmark as benchmark
    from claude.scripts.run_solution import main

    before = (
        benchmark._NOISE_OVERRIDE,
        benchmark._PREPARATION_OVERRIDE,
        benchmark.SHOTS,
        os.environ.get("DUQUANTUM_FIGURES_DIR"),
    )

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("deliberate constructor failure")

    monkeypatch.setattr(dp, "create_dicke_state", fail)
    assert (
        main(
            ["--mode", "validate", "--cases", "2,1", "--shots", "37", "--output-dir", str(tmp_path)]
        )
        == 1
    )
    manifest_path = next((tmp_path / "solution_runs").glob("*/run.json"))
    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "failed" and "deliberate constructor failure" in manifest["error"]
    assert "Traceback" in (manifest_path.parent / "terminal-output.log").read_text()
    assert (manifest_path.parent / "report.md").exists()
    assert before == (
        benchmark._NOISE_OVERRIDE,
        benchmark._PREPARATION_OVERRIDE,
        benchmark.SHOTS,
        os.environ.get("DUQUANTUM_FIGURES_DIR"),
    )
