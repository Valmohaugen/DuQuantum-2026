"""Analytical fixtures for diagnostic score components, including sampling variance."""

from __future__ import annotations

import json

import numpy as np
import pytest


def test_leaky_two_state_floor_uses_conditional_binomial_counts() -> None:
    from claude.score_diagnostics import score_diagnostics

    d = score_diagnostics(
        np.array([0.5, 0.25, 0.25, 0.0]),
        np.array([0.5, 0.0, 0.0, 0.5]),
        2,
        1,
        shots=2,
        max_correlator_size=2,
    )
    assert d["f"] == pytest.approx(0.5)
    assert d["z_floor"] == pytest.approx(5 / 6)
    assert d["z_bias"] == pytest.approx(0.0)
    assert d["x_penalty"] == pytest.approx(0.5)
    assert d["score_proxy"] == pytest.approx(0.75)
    assert d["zero_sector_probability"] == pytest.approx(0.25)


def test_full_survival_and_nonuniformity_have_independent_components() -> None:
    from claude.score_diagnostics import score_diagnostics

    d = score_diagnostics(
        np.array([0.0, 0.75, 0.25, 0.0]),
        np.array([0.5, 0.0, 0.0, 0.5]),
        2,
        1,
        shots=4,
        max_correlator_size=2,
    )
    assert d["z_floor"] == pytest.approx(0.375)
    assert d["z_bias"] == pytest.approx(0.5)
    assert d["x_penalty"] == pytest.approx(0.25)
    assert d["score_proxy"] == pytest.approx(8 / 9)


def test_empty_sector_is_explicit_and_strict_json_safe() -> None:
    from claude.score_diagnostics import score_diagnostics

    d = score_diagnostics(
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.array([0.5, 0.0, 0.0, 0.5]),
        2,
        1,
        shots=4,
        max_correlator_size=2,
    )
    assert d["f"] == pytest.approx(0.0)
    assert d["z_floor"] is None and d["score_proxy"] is None
    assert d["zero_sector_probability"] == pytest.approx(1.0)
    json.dumps(d, allow_nan=False)


@pytest.mark.parametrize("pz", [np.array([0.2, 0.3, 0.2, 0.2]), np.array([np.nan, 0.0, 0.0, 1.0])])
def test_invalid_probabilities_fail_early(pz: np.ndarray) -> None:
    from claude.score_diagnostics import score_diagnostics

    with pytest.raises(ValueError):
        score_diagnostics(pz, np.array([0.5, 0.0, 0.0, 0.5]), 2, 1, shots=4, max_correlator_size=2)


def test_missing_fields_do_not_inherit_infinite_proxy_status() -> None:
    from claude.score_diagnostics import table_row

    text = table_row(
        2,
        1,
        "sparse",
        {
            "score": None,
            "score_status": "undefined",
            "score_proxy": None,
            "score_proxy_status": "infinite",
        },
    )
    fields = text.split()
    assert fields[7:12] == ["--"] * 5
    assert fields[-2:] == ["inf", "undef"]


def test_proxy_overflow_is_explicit_and_json_safe() -> None:
    from claude.score_diagnostics import score_diagnostics

    d = score_diagnostics(
        np.array([1.0, 0.0, 0.0, 0.0]),
        np.array([1e-320, 0.5, 0.5, 0.0]),
        2,
        0,
        shots=1,
        max_correlator_size=1,
    )
    assert d["score_proxy"] is None
    assert d["score_proxy_status"] == "infinite"
    json.dumps(d, allow_nan=False)
