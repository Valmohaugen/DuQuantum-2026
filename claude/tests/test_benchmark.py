"""Regression tests for experimental configuration and result integrity."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from types import SimpleNamespace

import cirq
import cirq_google
import numpy as np
import pytest

from claude.scripts import challenge_calibration as calibration
from claude.scripts import noisy_benchmark as benchmark


def test_same_topology_same_seed_has_identical_calibration(monkeypatch: pytest.MonkeyPatch) -> None:
    metadata = cirq_google.Willow105.metadata
    first = calibration.make_challenge_calibration(1234)
    reordered = frozenset(reversed(list(metadata.qubit_pairs)))
    device = SimpleNamespace(
        metadata=SimpleNamespace(qubit_set=metadata.qubit_set, qubit_pairs=reordered)
    )
    monkeypatch.setattr(calibration.cirq_google, "Willow105", device)
    second = calibration.make_challenge_calibration(1234)
    for index, (a, b) in enumerate(zip(first, second)):
        if index == 0:
            a = {frozenset(key): value for key, value in a.items()}
            b = {frozenset(key): value for key, value in b.items()}
        assert a == b


def test_signature_covers_effective_noise_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    original = benchmark.benchmark_signature()

    @dataclasses.dataclass(frozen=True)
    class DifferentNoise(benchmark.NoiseConfig):
        t1_us: float = 1.0

    monkeypatch.setattr(benchmark, "NoiseConfig", DifferentNoise)
    assert benchmark.benchmark_signature() != original


def test_signature_covers_actual_calibration() -> None:
    maps = calibration.make_challenge_calibration()
    changed = tuple(dict(item) for item in maps)
    q = next(iter(changed[1]))
    changed[1][q] = (0.02, 0.0)
    assert benchmark.benchmark_signature(maps) != benchmark.benchmark_signature(changed)


def test_runtime_shot_override_reaches_sampling_and_preserves_legacy(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    monkeypatch.setattr(benchmark, "SHOTS", 37)
    monkeypatch.setattr(benchmark, "BENCHMARK_SEEDS", (1,))
    monkeypatch.setattr(benchmark, "BENCHMARK_CASES", ((2, 1),))
    monkeypatch.setattr(benchmark, "OUTPUT_DIR", tmp_path)
    legacy = tmp_path / "noisy_benchmark_results.json"
    legacy.write_text("historical result must be preserved")
    seen = []
    original = benchmark.sample_bits

    def observe(probs: np.ndarray, n: int, shots: int, rng: np.random.Generator) -> np.ndarray:
        seen.append(shots)
        return original(probs, n, shots, rng)

    monkeypatch.setattr(benchmark, "sample_bits", observe)
    result_path = benchmark.main()
    assert seen == [37] * 6
    assert legacy.read_text() == "historical result must be preserved"
    data = json.loads(result_path.read_text())
    assert data["signature"]["settings"]["shots"] == 37
    assert data["complete"]
    assert result_path.parent != tmp_path
    assert all("z_floor" in row and "fidelity" in row for row in data["results"].values())
    assert "Zfloor" in capsys.readouterr().out

    def forbid_resampling(*args, **kwargs):
        raise AssertionError("resuming should use saved scores and table diagnostics")

    monkeypatch.setattr(benchmark, "score_instance", forbid_resampling)
    benchmark.main()
    assert "Zfloor" in capsys.readouterr().out


def test_shot_seed_does_not_change_physical_noise_probabilities() -> None:
    q = cirq.GridQubit(5, 5)
    maps = ({}, {q: (0.0, 0.0)}, {q: (0.0, 0.0)}, {q: (0.0, 0.0)})
    circuit = cirq.Circuit(cirq.H(q), cirq.I(q), cirq.H(q))
    first = benchmark.NoiseConfig(detuning_khz=50, seed=1, noise_seed=9)
    second = dataclasses.replace(first, seed=2)
    a = benchmark.simulate_probabilities(circuit, [q], maps, first)
    b = benchmark.simulate_probabilities(circuit, [q], maps, second)
    np.testing.assert_allclose(a, b, atol=1e-12, rtol=1e-10)


@pytest.mark.parametrize(
    "score,status", [(np.inf, "infinite"), (np.nan, "undefined"), (2.0, "finite")]
)
def test_nonfinite_scores_have_explicit_strict_json_records(
    score: float, status: str, tmp_path: Path
) -> None:
    record = benchmark.score_record(score, 4)
    assert record["score_status"] == status
    assert (record["score"] is None) == (status != "finite")
    path = tmp_path / "record.json"
    benchmark.atomic_write_json(path, record)
    json.loads(
        path.read_text(), parse_constant=lambda value: pytest.fail(f"nonstandard JSON {value}")
    )


def test_zero_noise_local_x_transform_matches_dense() -> None:
    q = cirq.GridQubit(5, 5)
    maps = ({}, {q: (0.0, 0.0)}, {q: (0.0, 0.0)}, {q: (0.0, 0.0)})
    circuit = cirq.Circuit(cirq.ry(0.7)(q))
    cfg = benchmark.NoiseConfig(t1_us=1e12, tphi_us=1e12)
    z, x = benchmark.simulate_probabilities(circuit, [q], maps, cfg)
    expected = np.array([np.cos(0.7 / 2), np.sin(0.7 / 2)])
    np.testing.assert_allclose(z, abs(expected) ** 2, atol=1e-12, rtol=1e-10)
    np.testing.assert_allclose(x, abs(cirq.unitary(cirq.H) @ expected) ** 2, atol=1e-12, rtol=1e-10)


def test_invalid_probability_input_fails_loudly() -> None:
    with pytest.raises(ValueError):
        benchmark.sample_bits(np.array([np.nan, 1.0]), 1, 10, np.random.default_rng(7))


def test_signature_tracks_source_content(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = tmp_path / "implementation.py"
    source.write_text("version one")
    monkeypatch.setattr(benchmark, "SOURCE_PATHS", {"implementation": source})
    before = benchmark.benchmark_signature()
    source.write_text("version two")
    assert benchmark.benchmark_signature() != before


def test_strict_json_failure_preserves_prior_file(tmp_path: Path) -> None:
    path = tmp_path / "results.json"
    path.write_text("original")
    with pytest.raises(ValueError):
        benchmark.atomic_write_json(path, {"score": float("nan")})
    assert path.read_text() == "original"


def test_corrupt_or_legacy_checkpoints_are_not_reused(tmp_path: Path) -> None:
    signature = benchmark.benchmark_signature()
    path = tmp_path / "checkpoint.json"
    for invalid in (
        '{"score": NaN}',
        json.dumps({"signature": signature, "results": {"2,1,1,dd": {"score": 1.0, "moments": 3}}}),
    ):
        path.write_text(invalid)
        assert benchmark.load_checkpoint(signature, path)["results"] == {}
        assert path.read_text() == invalid


def test_x_transform_matches_dense_for_complex_mixed_states() -> None:
    rng = np.random.default_rng(20261024)
    matrix = rng.normal(size=(8, 8)) + 1j * rng.normal(size=(8, 8))
    rho = matrix @ matrix.conj().T
    rho /= np.trace(rho)
    np.testing.assert_allclose(rho, rho.conj().T, atol=1e-12, rtol=1e-10)
    assert np.linalg.eigvalsh(rho).min() >= -1e-12
    h = np.kron(np.kron(cirq.unitary(cirq.H), cirq.unitary(cirq.H)), cirq.unitary(cirq.H))
    expected = np.diag(h @ rho @ h.conj().T).real
    np.testing.assert_allclose(
        benchmark.x_basis_probabilities(rho, 3), expected, atol=1e-12, rtol=1e-10
    )


@pytest.mark.parametrize(
    "change",
    [
        {"score": True},
        {"moments": 1.5},
        {"moments": 999999},
        {"moments": False},
        {"shot_seed": 99},
        {"noise_seed": 99},
    ],
)
def test_checkpoint_rejects_invalid_record_metadata(change: dict, tmp_path: Path) -> None:
    signature = benchmark.benchmark_signature()
    record = {"score": 1.0, "score_status": "finite", "moments": 5, "shot_seed": 1, "noise_seed": 1}
    record.update(change)
    payload = {"signature": signature, "results": {"2,1,1,dd": record}}
    path = tmp_path / "checkpoint.json"
    path.write_text(json.dumps(payload))
    assert benchmark.load_checkpoint(signature, path)["results"] == {}


def test_checkpoint_array_is_rejected_without_crashing(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    path.write_text("[]")
    assert benchmark.load_checkpoint(benchmark.benchmark_signature(), path)["results"] == {}


def test_rng_domains_are_distinct_even_for_equal_numeric_seeds() -> None:
    shots = benchmark.make_rng(7, "shots").random(16)
    noise = benchmark.make_rng(7, "noise").random(16)
    np.testing.assert_array_equal(shots, benchmark.make_rng(7, "shots").random(16))
    assert not np.allclose(shots, noise, atol=1e-12, rtol=1e-10)
