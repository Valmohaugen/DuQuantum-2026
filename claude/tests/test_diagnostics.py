"""Analytical validation of diagnostic quantities, independent of figure styling."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from claude import diagnostic_metrics as metrics
from claude import dicke_prep as dp
from claude.scripts.challenge_calibration import make_challenge_calibration
from claude.validation import dicke_vector


def test_exact_metrics_remove_only_common_global_phase() -> None:
    target = dicke_vector(4, 2)
    observed = metrics.state_metrics(np.exp(0.7j) * target, 2)
    assert observed["fidelity"] == pytest.approx(1.0, abs=1e-12)
    assert observed["leakage"] == pytest.approx(0.0, abs=1e-12)
    assert observed["max_amplitude_error"] < 1e-12
    corrupted = target.astype(complex)
    corrupted[np.flatnonzero(target)[0]] *= -1
    assert metrics.state_metrics(corrupted, 2)["fidelity"] < 0.9


@pytest.mark.parametrize("n,k", [(2, 1), (4, 2), (3, 0), (3, 3), (6, 2), (6, 5)])
def test_exact_distribution_matches_analytical_correlators(n: int, k: int) -> None:
    state = dicke_vector(n, k)
    h = np.array([[1.0, 1.0], [1.0, -1.0]]) / math.sqrt(2)
    full_h = h
    for _ in range(n - 1):
        full_h = np.kron(full_h, h)
    result = metrics.distribution_metrics(
        abs(state) ** 2, abs(full_h @ state) ** 2, n, k, max_correlator_size=n
    )
    assert result["leakage"] == pytest.approx(0.0, abs=1e-12)
    assert result["z_total_variation"] < 1e-12
    np.testing.assert_allclose(result["x_observed"], result["x_expected"], atol=1e-12, rtol=1e-10)


def test_nonuniform_and_leaking_distributions_are_distinguished() -> None:
    ideal = np.array([0.0, 0.5, 0.5, 0.0])
    px = np.array([0.5, 0.0, 0.0, 0.5])
    leaking = metrics.distribution_metrics(np.array([0.2, 0.4, 0.4, 0.0]), px, 2, 1)
    skewed = metrics.distribution_metrics(np.array([0.0, 0.8, 0.2, 0.0]), px, 2, 1)
    assert leaking["leakage"] == pytest.approx(0.2)
    assert leaking["conditional_uniformity_tv"] < 1e-12
    assert skewed["leakage"] == pytest.approx(0.0)
    assert skewed["conditional_uniformity_tv"] == pytest.approx(0.3)
    assert metrics.distribution_metrics(ideal, px, 2, 1)["x_expected"] == [0.0, 1.0]


def test_circuit_counts_and_costs_are_consistent() -> None:
    cal = make_challenge_calibration()
    circuit, qubits = dp.create_dicke_state(
        3, 1, *cal, config=dp.PrepConfig(use_dynamical_decoupling=False)
    )
    result = metrics.circuit_metrics(circuit, qubits, cal)
    assert result["cz_count"] == 3
    assert sum(row["cz_count"] for row in result["couplers"]) == 3
    assert sum(row["oneq_count"] for row in result["qubits"]) == result["oneq_count"]
    assert result["duration_ns"] > 0
    assert result["gate_error_proxy"] >= 0
    schedule = np.array(result["schedule_types"])
    assert schedule.shape == (3, len(circuit))
    assert np.count_nonzero(schedule == 2) == 2 * result["cz_count"]


def test_student_interval_uses_seed_count_and_handles_singletons() -> None:
    result = metrics.mean_interval([1.0, 2.0, 3.0])
    assert result["mean"] == pytest.approx(2.0)
    assert result["lower"] == pytest.approx(-0.4841377117, abs=1e-8)
    assert result["upper"] == pytest.approx(4.4841377117, abs=1e-8)
    assert metrics.mean_interval([2.0])["lower"] is None
    assert metrics.mean_interval([])["mean"] is None


@pytest.mark.parametrize("state", [np.array([1.0, 1.0]), np.ones(3), np.array([np.nan, 0.0])])
def test_invalid_states_fail_loudly(state: np.ndarray) -> None:
    with pytest.raises(ValueError):
        metrics.state_metrics(state, 1)


def test_saved_report_contains_real_metrics_and_rendered_figures(tmp_path: Path) -> None:
    import json

    from claude.scripts.diagnose import build_report

    report = build_report(tmp_path, n=3, k=1, resource_sizes=(2, 4), detuning_levels=(0.0, 20.0))
    payload = json.loads((report.parent / "diagnostics.json").read_text())
    assert payload["state"]["fidelity"] == pytest.approx(1.0, abs=1e-12)
    assert payload["score_data_status"] == "unavailable"
    assert len(payload["figures"]) >= 5
    assert "2-realization" in report.read_text()
    figure_dir = Path(payload["figure_dir"])
    assert figure_dir == tmp_path / "figs" / "diagnostics" / report.parent.name
    for name in payload["figures"]:
        for suffix in (".png", ".pdf"):
            assert (figure_dir / (name + suffix)).stat().st_size > 1000
            assert str(figure_dir / (name + suffix)) in report.read_text()
    assert not list(report.parent.glob("*.png"))
    assert not list(report.parent.glob("*.pdf"))
    assert (report.parent / "resources.csv").stat().st_size > 0


def test_nonreal_probabilities_are_not_silently_cast() -> None:
    with pytest.raises(ValueError):
        metrics.distribution_metrics(np.array([0.5 + 0.1j, 0.5 - 0.1j]), np.array([0.5, 0.5]), 1, 0)


def test_tiny_leakage_is_summed_without_cancellation() -> None:
    state = dicke_vector(2, 1).astype(complex)
    state[0] = 1e-10
    state /= np.linalg.norm(state)
    assert metrics.state_metrics(state, 1)["leakage"] == pytest.approx(1e-20, rel=1e-10, abs=1e-30)
    result = metrics.distribution_metrics(abs(state) ** 2, np.array([0.5, 0.0, 0.0, 0.5]), 2, 1)
    assert result["leakage"] == pytest.approx(1e-20, rel=1e-10, abs=1e-30)


def test_paired_plot_labels_first_available_observations(monkeypatch, tmp_path: Path) -> None:
    import warnings

    from claude import diagnostic_plots as plots

    rows = [
        {"n": 2, "k": 1, "n_pairs": 0, "excluded": 1, "dd_scores": [], "no_dd_scores": []},
        {"n": 3, "k": 1, "n_pairs": 1, "excluded": 0, "dd_scores": [1.2], "no_dd_scores": [1.0]},
    ]
    labels = []

    def capture_figure(figure, root: Path, stem: str) -> str:
        labels.extend(figure.axes[0].get_legend_handles_labels()[1])
        return stem

    monkeypatch.setattr(plots, "_save", capture_figure)
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        plots._paired({"comparison": {"cases": rows}}, tmp_path)
    assert labels == ["dd", "no-dd"]


def test_undefined_score_bundle_does_not_invent_uncertainty(monkeypatch, tmp_path: Path) -> None:
    import json
    import warnings

    from claude.scripts import noisy_benchmark as benchmark
    from claude.scripts.diagnose import build_report

    monkeypatch.setattr(benchmark, "BENCHMARK_CASES", ((2, 1),))
    monkeypatch.setattr(benchmark, "BENCHMARK_SEEDS", (1,))
    monkeypatch.setattr(benchmark, "RUN_IDEAL_BASELINE", False)
    data = {
        "complete": True,
        "signature": benchmark.benchmark_signature(),
        "results": {
            "2,1,1,dd": {
                "score": None,
                "score_status": "infinite",
                "moments": 5,
                "shot_seed": 1,
                "noise_seed": 1,
            },
            "2,1,1,no-dd": {
                "score": 1.0,
                "score_status": "finite",
                "moments": 5,
                "shot_seed": 1,
                "noise_seed": 1,
            },
        },
    }
    source = tmp_path / "scores.json"
    source.write_text(json.dumps(data))
    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        report = build_report(
            tmp_path / "report",
            n=2,
            k=1,
            results_path=source,
            resource_sizes=(2,),
            detuning_levels=(0.0,),
        )
    payload = json.loads((report.parent / "diagnostics.json").read_text())
    assert payload["comparison"]["aggregate"]["n_pairs"] == 0
    assert "[unavailable, unavailable]" in report.read_text()
