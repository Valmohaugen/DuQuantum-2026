"""Analysis regressions independent of notebooks and private documentation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude.scripts import noisy_benchmark as benchmark


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
