"""Check the revised objective against notebook statistics, including shot noise."""

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from claude.scripts.evaluate_candidates import builders, penalties, summary


@pytest.mark.parametrize("n,k", [(2, 1), (3, 1), (4, 1), (4, 2), (5, 2), (6, 3)])
def test_count_penalties_match_notebook(n, k):
    path = Path(__file__).resolve().parents[2] / "ryon/judge.py"
    spec = importlib.util.spec_from_file_location("eval_judge_test", path)
    judge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(judge)
    rng = np.random.default_rng(117)
    z = rng.integers(0, 2, size=(100, n))
    x = rng.integers(0, 2, size=(100, n))
    sector = z.sum(axis=1) == k
    states = [i for i in range(2**n) if i.bit_count() == k]
    encoded = z @ (2 ** np.arange(n))
    z_counts = np.array([sum(encoded == i) for i in states] + [sum(~sector)])
    x_counts = np.bincount(x.sum(axis=1), minlength=n + 1)
    expected = judge.check_z_bitstring_distribution(z, k) + judge.check_x_bitstring_distribution(
        x, k, n
    )
    assert penalties(z_counts, x_counts, n, k) == pytest.approx(expected, abs=1e-12)
    assert penalties(np.stack([z_counts] * 2), np.stack([x_counts] * 2), n, k) == pytest.approx(
        [expected] * 2
    )


def test_undefined_z_draw_fails():
    with pytest.raises(ValueError, match="no in-sector"):
        penalties(np.array([0, 0, 10]), np.array([2, 6, 2]), 2, 1)


def test_harmonic_objective_weights_low_scores():
    rows = [
        dict(
            N=n,
            n=1,
            seed=0,
            mean_penalty=p,
            mean_score=1 / p,
            proxy=1 / p,
            moments=10,
            cz=2,
            oneq=4,
        )
        for n, p in [(2, 1), (3, 3)]
    ]
    result = summary(rows)
    assert result["harmonic_sampled"] == pytest.approx(0.5)
    assert result["arithmetic_score"] == pytest.approx(2 / 3)
    assert result["worst_case_mean_score"] == pytest.approx(1 / 3)


def test_candidate_module_supports_dataclasses(tmp_path):
    source = tmp_path / "candidate.py"
    source.write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\nclass Config:\n    value: int = 7\n"
        "def create_dicke_state(*args):\n    return Config().value\n"
    )
    assert builders({"dataclass_candidate": source})["dataclass_candidate"](2, 1, ()) == 7
