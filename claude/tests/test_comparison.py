"""A common-model comparison saves all evidence and validates native circuits."""

import json
from pathlib import Path

import cirq
import numpy as np
import pytest


def test_comparison_saves_all_artifacts(tmp_path: Path, capsys) -> None:
    from claude.scripts.compare_solutions import compare_solutions
    from claude.scripts.noisy_benchmark import NoiseConfig

    report = compare_solutions(
        tmp_path,
        cases=((2, 1),),
        seeds=(1,),
        noise=NoiseConfig(shots=40, detuning_khz=0),
        include_upstream=False,
    )
    data = json.loads((report.parent / "comparison.json").read_text())
    assert len(data["resources"]) == 3
    assert all(row["fidelity"] > 1 - 1e-12 for row in data["resources"])
    assert all(len(row["output_qubits"]) == row["n"] for row in data["resources"])
    assert len(data["scores"]) == 3
    assert all("z_floor" in row and "x_floor" in row for row in data["scores"])
    terminal = capsys.readouterr().out
    assert "Zfloor" in terminal and "sampled" in terminal and "seed=1" in terminal
    assert (report.parent / "resources.csv").exists()
    assert (report.parent / "scores.csv").exists()
    assert len(list((report.parent / "sources").glob("*.py"))) >= 1
    root = Path(data["figure_dir"])
    assert root.is_relative_to(tmp_path / "figs")
    assert len(list(root.glob("*.png"))) == len(list(root.glob("*.pdf"))) == 2
    again = compare_solutions(
        tmp_path,
        cases=((2, 1),),
        seeds=(1,),
        noise=NoiseConfig(shots=40, detuning_khz=0),
        include_upstream=False,
    )
    assert report.parent != again.parent
    assert report.exists()


def test_optional_reference_failure_is_saved_and_does_not_abort(tmp_path: Path) -> None:
    from claude.scripts.compare_solutions import compare_solutions
    from claude.scripts.noisy_benchmark import NoiseConfig

    source = tmp_path / "broken_reference.py"
    source.write_text(
        'def create_dicke_state(*args):\n    raise IndexError("no candidate swaps")\n'
    )
    report = compare_solutions(
        tmp_path / "output",
        cases=((2, 1),),
        seeds=(1,),
        noise=NoiseConfig(shots=20, detuning_khz=0),
        include_upstream=False,
        baseline=source,
    )
    data = json.loads(report.with_name("comparison.json").read_text())
    failed = next(r for r in data["resources"] if r["variant"] == "baseline")
    assert failed["status"] == "error" and failed["error_type"] == "IndexError"
    assert "no candidate swaps" in Path(failed["error_log"]).read_text()
    assert len(data["scores"]) == 3 and all(r["variant"] != "baseline" for r in data["scores"])
    assert "Reference failures" in report.read_text()


def test_maintained_solver_errors_remain_fatal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claude import dicke_prep as dp
    from claude.scripts.compare_solutions import compare_solutions

    def fail(*args: object, **kwargs: object) -> None:
        raise IndexError("maintained failure")

    monkeypatch.setattr(dp, "create_dicke_state", fail)
    with pytest.raises(IndexError, match="maintained failure"):
        compare_solutions(tmp_path, cases=((2, 1),), seeds=(1,), include_upstream=False)


@pytest.mark.parametrize("excitations", (1, 2, 3, 4))
def test_minimal_reference_routes_five_qubit_star_without_global_patch(excitations: int) -> None:
    from claude.scripts.challenge_calibration import make_challenge_calibration
    from claude.scripts.compare_solutions import _builders
    from claude.validation import validate_preparation

    original_router = cirq.RouteCQC
    source = Path(__file__).resolve().parents[2] / "ryon/minimal_dicke.py"
    original_bytes = source.read_bytes()
    builders = _builders(None, True)
    _, build, _ = next(candidate for candidate in builders if candidate[0] == "minimal")
    calibration = make_challenge_calibration(1234)
    circuit, qubits = build(5, excitations, calibration)
    fidelity = validate_preparation(circuit, qubits, 5, excitations, calibration)
    assert np.isclose(fidelity, 1.0, atol=1e-12, rtol=1e-10)
    assert cirq.RouteCQC is original_router
    assert source.read_bytes() == original_bytes


def test_fixed_minimal_reference_is_scored_with_adapter_provenance(tmp_path: Path) -> None:
    from claude.scripts.compare_solutions import compare_solutions
    from claude.scripts.noisy_benchmark import NoiseConfig

    report = compare_solutions(
        tmp_path,
        cases=((5, 4),),
        seeds=(1,),
        noise=NoiseConfig(shots=20, detuning_khz=0),
        include_upstream=True,
    )
    data = json.loads(report.with_name("comparison.json").read_text())
    minimal = next(row for row in data["resources"] if row["variant"] == "minimal")
    assert minimal["status"] == "valid"
    assert data["reference_error_count"] == 0
    assert any(row["variant"] == "minimal" for row in data["scores"])
    assert "reference_routing" in data["sources"]
    assert "minimal" in data["reference_adapters"]
    assert "routing guard" in report.read_text().lower()
