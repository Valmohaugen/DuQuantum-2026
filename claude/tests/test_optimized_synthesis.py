"""Exact state-specific synthesis must save gates without weakening the solver."""

from __future__ import annotations

import json
import math
import runpy
from pathlib import Path

import cirq
import numpy as np
import pytest

from claude import dicke_prep as dp
from claude.scripts.challenge_calibration import make_challenge_calibration
from claude.validation import dicke_vector, validate_preparation


@pytest.mark.parametrize(
    "alpha,beta",
    [
        (0.0, 0.0),
        (0.0, math.pi / 2),
        (math.pi / 2, 0.0),
        (math.pi / 2, math.pi / 2),
        (math.pi / 4, math.pi / 4),
        (0.27, 1.13),
    ],
)
def test_four_cz_split_pair_has_common_positive_phase(alpha: float, beta: float) -> None:
    q = cirq.LineQubit.range(3)
    circuit = cirq.Circuit(dp._split_pair_ops(*q, alpha, beta))
    unitary = circuit.unitary(qubit_order=q)
    expected = np.zeros((8, 3), dtype=complex)
    expected[0, 0] = 1
    expected[1, 1], expected[2, 1] = math.cos(beta), math.sin(beta)
    expected[3, 2], expected[6, 2] = math.cos(alpha), math.sin(alpha)
    np.testing.assert_allclose(unitary[:, [0, 1, 3]], expected, atol=1e-12, rtol=1e-10)
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 4


def test_default_square_saves_cz_and_preserves_exact_state() -> None:
    cal = make_challenge_calibration()
    circuit, qubits = dp.create_dicke_state(4, 2, *cal)
    validate_preparation(circuit, qubits, 4, 2, cal)
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 5
    assert len(circuit) <= 9


def test_optimized_line_saves_cz_beyond_downloaded_full_blocks() -> None:
    cal = make_challenge_calibration()
    circuit, qubits = dp.create_dicke_state(6, 3, *cal)
    validate_preparation(circuit, qubits, 6, 3, cal)
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 29


@pytest.mark.parametrize("n,k", [(4, 2), (6, 2), (6, 3), (7, 4), (10, 5), (12, 7)])
def test_line_edge_counts_match_emitted_gates(n: int, k: int) -> None:
    q = cirq.LineQubit.range(n)
    for construction in ("optimized", "analytic"):
        ops = dp.build_line_ops(q, k, construction=construction)
        actual = [
            sum(op.gate == cirq.CZ and set(op.qubits) == {q[i], q[i + 1]} for op in ops)
            for i in range(n - 1)
        ]
        assert dp.line_edge_cz_counts(n, k, construction=construction) == actual
        state = cirq.final_state_vector(cirq.Circuit(ops), qubit_order=q, dtype=np.complex128)
        target = dicke_vector(n, k)
        state *= np.exp(-1j * np.angle(np.vdot(target, state)))
        np.testing.assert_allclose(state, target, atol=1e-12, rtol=1e-10)


@pytest.mark.parametrize("n,k,cz", [(4, 2, 12), (6, 3, 35)])
def test_analytic_constructor_remains_available(n: int, k: int, cz: int) -> None:
    cal = make_challenge_calibration()
    circuit, qubits = dp.create_dicke_state(
        n, k, *cal, config=dp.PrepConfig(construction="analytic")
    )
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == cz
    validate_preparation(circuit, qubits, n, k, cal)


def test_cli_selects_construction() -> None:
    from claude.scripts.run_solution import parse_args

    assert parse_args([]).preparation.construction == "optimized"
    assert parse_args(["--construction", "analytic"]).preparation.construction == "analytic"


def _square_calibration() -> tuple[dict, dict, dict, dict]:
    q = [cirq.GridQubit(3, 3), cirq.GridQubit(3, 4), cirq.GridQubit(4, 3), cirq.GridQubit(4, 4)]
    one = {p: (0.001, 0.0) for p in q}
    two = {(q[a], q[b]): (0.002, 0.0) for a, b in ((0, 1), (0, 2), (1, 3), (2, 3))}
    return two, one, one, one


@pytest.mark.parametrize("rotation", range(4))
@pytest.mark.parametrize("direction", [1, -1])
def test_square_identity_preserves_positive_amplitudes_in_all_orientations(
    rotation: int, direction: int
) -> None:
    q = sorted(_square_calibration()[1])
    cycle = [q[0], q[1], q[3], q[2]]
    ring = [cycle[(rotation + direction * i) % 4] for i in range(4)]
    labels = [ring[0], ring[1], ring[3], ring[2]]
    circuit = cirq.Circuit(dp._square_ops(labels))
    state = cirq.final_state_vector(circuit, qubit_order=q, dtype=np.complex128)
    np.testing.assert_allclose(state, dicke_vector(4, 2), atol=1e-12, rtol=1e-10)


def test_missing_square_edge_uses_exact_line_fallback() -> None:
    two, one, zero, excited = _square_calibration()
    two.pop(next(iter(two)))
    cal = (two, one, zero, excited)
    circuit, q = dp.create_dicke_state(4, 2, *cal)
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 9
    validate_preparation(circuit, q, 4, 2, cal)


def test_costly_square_does_not_displace_a_better_calibrated_path() -> None:
    two, one, _, _ = _square_calibration()
    two = {pair: (0.2, 0.0) for pair in two}
    line = [cirq.GridQubit(6, 8), cirq.GridQubit(7, 8), cirq.GridQubit(7, 9), cirq.GridQubit(8, 9)]
    one.update({q: (0.001, 0.0) for q in line})
    two.update({pair: (0.0001, 0.0) for pair in zip(line, line[1:])})
    cal = (two, one, one, one)
    circuit, q = dp.create_dicke_state(4, 2, *cal)
    assert q == set(line)
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 9
    validate_preparation(circuit, q, 4, 2, cal)


def test_square_survives_an_unrelated_path_search_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise NotImplementedError("deliberate beam-search failure")

    monkeypatch.setattr(dp, "find_line", fail)
    cal = _square_calibration()
    circuit, q = dp.create_dicke_state(4, 2, *cal)
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 5
    validate_preparation(circuit, q, 4, 2, cal)


def test_old_recorded_settings_keep_the_original_constructor() -> None:
    from claude.scripts import noisy_benchmark as benchmark
    from claude.scripts.diagnose import resolve_report_settings

    signature = benchmark.benchmark_signature()
    for settings in signature["preparation"].values():
        settings.pop("construction")
    _, _, config = resolve_report_settings({"signature": signature})
    assert config.construction == "analytic"


def test_invalid_construction_fails_before_building() -> None:
    with pytest.raises(ValueError, match="construction"):
        dp.PrepConfig(construction="typo")


def test_legacy_dataset_also_retains_original_synthesis(tmp_path: Path) -> None:
    from claude.scripts.analyze_benchmark_results import load_results
    from claude.scripts.diagnose import resolve_report_settings

    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "signature": {"calibration_seed": 1234},
                "complete": True,
                "results": {
                    "4,2,1,dd": {"score": 1.0, "moments": 21},
                    "4,2,1,no-dd": {"score": 1.0, "moments": 21},
                },
            }
        )
    )
    _, _, config = resolve_report_settings(load_results(path))
    assert config.construction == "analytic"
    assert resolve_report_settings()[2].construction == "optimized"


def test_configured_export_applies_search_and_construction_to_bonus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claude.scripts.build_submission import build_submission

    config = dp.PrepConfig(construction="analytic", beam_width=17, search_time_s=1.0)
    exported = runpy.run_path(
        str(build_submission(tmp_path / "submission.py", configuration=config))
    )
    bonus = exported["create_dicke_state_adaptive"]
    globals_dict = bonus.__globals__
    create = globals_dict["create_dicke_state"]
    seen = []

    def capture(*args: object) -> tuple:
        seen.append(args[-1])
        return create(*args)

    monkeypatch.setitem(globals_dict, "create_dicke_state", capture)
    circuit, q = bonus(4, 2)
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 12
    assert seen[0].construction == "analytic" and seen[0].beam_width == 17
    assert seen[0].search_time_s == pytest.approx(1.0)
    assert not seen[0].use_dynamical_decoupling
    validate_preparation(circuit, q, 4, 2)
