"""Test reachable tutorial controls and consistency of the physical experiment."""

from __future__ import annotations

import ast
import json
import math
import runpy
import warnings
from pathlib import Path

import cirq
import matplotlib
import numpy as np
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from claude import dicke_prep as dp
from claude.scripts import noisy_benchmark as benchmark
from claude.scripts.challenge_calibration import make_challenge_calibration
from claude.validation import dicke_vector

REPO = Path(__file__).resolve().parents[2]


def tutorial_functions() -> tuple[dict, dict]:
    cells = runpy.run_path(str(REPO / "claude/scripts/build_tutorial.py"))["CELLS"]
    controls = {}

    def interactive(fn, **kwargs):
        controls[fn.__name__] = kwargs

    namespace = dict(
        cirq=cirq,
        np=np,
        math=math,
        dp=dp,
        nbm=benchmark,
        plt=plt,
        dicke_vector=dicke_vector,
        CAL=make_challenge_calibration(),
        FAST=dp.PrepConfig(beam_width=300, search_time_s=2),
        interactive=interactive,
    )
    for kind, source in cells:
        if kind != "code":
            continue
        tree = ast.parse(source)
        selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
        if any(
            getattr(node, "name", "")
            in ("line_program", "trace_states", "show_trace", "validate_simulated_solution")
            for node in selected
        ):
            # Definitions and their associated widget registration, without rendering.
            tree.body = [
                node for node in tree.body if not isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            exec(compile(tree, "tutorial control definitions", "exec"), namespace)
    return namespace, controls


def test_trace_control_can_reach_every_allowed_final_state() -> None:
    namespace, controls = tutorial_functions()
    for n in range(2, 8):
        for k in range(1, n):
            _, steps = namespace["line_program"](n, k)
            assert controls["show_trace"]["step"][1] >= len(steps) - 1


def test_validation_control_handles_its_full_allowed_range() -> None:
    namespace, _ = tutorial_functions()
    namespace["validate_simulated_solution"](2, 6)


def test_detuning_probabilities_can_change_final_weight_leakage() -> None:
    cal = make_challenge_calibration()
    clean = tuple({key: (0.0, 0.0) for key in mapping} for mapping in cal)
    circuit, qubits = dp.create_dicke_state(
        4, 2, *clean, config=dp.PrepConfig(use_dynamical_decoupling=False)
    )
    order = sorted(qubits)
    cfg = benchmark.NoiseConfig(t1_us=1e12, tphi_us=1e12, detuning_khz=50, noise_seed=2)
    pz, _ = benchmark.simulate_probabilities(circuit, order, clean, cfg)
    leakage = 1 - sum(probability for i, probability in enumerate(pz) if i.bit_count() == 2)
    assert leakage > 1e-5


def test_singleton_analysis_plot_and_nonfinite_statuses(tmp_path: Path) -> None:
    from claude.scripts import analyze_benchmark_results as analysis

    data = {
        "complete": True,
        "aggregate": {"dd_mean": 1.0, "dd_std": 0.0, "no_dd_mean": 2.0, "no_dd_std": 0.0},
        "results": {
            "2,1,1,dd": {"score": 1.0, "moments": 1},
            "2,1,1,no-dd": {"score": 2.0, "moments": 1},
            "3,1,1,dd": {"score": None, "score_status": "undefined", "moments": 3},
            "3,1,1,no-dd": {"score": 1.0, "score_status": "finite", "moments": 3},
        },
    }
    report = analysis.summarize(data)
    assert "undefined" in report.lower()
    analysis.write_insight_plot(data, tmp_path / "plot.png")
    assert (tmp_path / "plot.png").stat().st_size > 0


def test_mux_explanation_retains_complex_matrix_dtype() -> None:
    cells = runpy.run_path(str(REPO / "claude/scripts/build_tutorial.py"))["CELLS"]
    namespace = dict(cirq=cirq, np=np, math=math, dp=dp, bits=lambda j, n: format(j, f"0{n}b"))
    source = next(src for kind, src in cells if kind == "code" and "def mux_table" in src)
    tree = ast.parse(source)
    tree.body = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    exec(compile(tree, "mux explanation", "exec"), namespace)
    with warnings.catch_warnings():
        warnings.simplefilter("error", np.exceptions.ComplexWarning)
        namespace["mux_table"](0.9)


def test_analyzer_saves_figure_under_configured_figs_root(tmp_path: Path) -> None:
    from claude.scripts import analyze_benchmark_results as analysis

    source = tmp_path / "results.json"
    source.write_text(
        json.dumps(
            {
                "complete": True,
                "results": {
                    "2,1,1,dd": {"score": 1.0, "moments": 1},
                    "2,1,1,no-dd": {"score": 2.0, "moments": 1},
                },
            }
        )
    )
    report = analysis.main(source, tmp_path / "reports")
    figures = list((tmp_path / "figs" / "benchmarks").glob("*/noisy_benchmark_insights.png"))
    assert len(figures) == 1
    assert str(figures[0]) in report.read_text()
    assert not list(report.parent.glob("*.png"))


def test_complete_analysis_cannot_hide_missing_cases_or_seeds(tmp_path: Path) -> None:
    from claude.scripts import analyze_benchmark_results as analysis

    data = {
        "complete": True,
        "signature": {
            "schema_version": 2,
            "settings": {
                "benchmark_cases": [[2, 1], [3, 1]],
                "benchmark_seeds": [1, 2],
                "run_ideal_baseline": False,
            },
        },
        "results": {
            "2,1,1,dd": {"score": 1.0, "moments": 5},
            "2,1,1,no-dd": {"score": 2.0, "moments": 5},
        },
    }
    path = tmp_path / "incomplete.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="missing|incomplete"):
        analysis.load_results(path)
    with pytest.raises(ValueError, match="missing|incomplete"):
        analysis.summarize(data)


@pytest.mark.parametrize(
    "field", ["benchmark_cases", "benchmark_seeds", "shots", "run_ideal_baseline"]
)
def test_modern_signature_cannot_downgrade_missing_design_to_legacy(
    field: str, tmp_path: Path
) -> None:
    from claude.benchmark_statistics import has_complete_provenance
    from claude.scripts import analyze_benchmark_results as analysis

    signature = benchmark.benchmark_signature()
    del signature["settings"][field]
    data = {
        "complete": True,
        "signature": signature,
        "results": {
            "2,1,1,dd": {"score": 1.0, "moments": 5},
            "2,1,1,no-dd": {"score": 2.0, "moments": 5},
        },
    }
    path = tmp_path / "missing-design.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="missing|incomplete"):
        analysis.load_results(path)
    assert not has_complete_provenance(data)
