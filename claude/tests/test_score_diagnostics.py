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


def test_seed_totals_sum_stored_precision_and_only_additive_columns() -> None:
    from claude.score_diagnostics import table_totals

    row = dict(
        cz_count=3,
        moments=7,
        build_seconds=0.049,
        fidelity=1.0,
        f=0.9,
        z_floor=0.5004,
        z_bias=0.0004,
        x_penalty=0.0004,
        score_proxy=1.2344,
        score=2.3454,
        rules="ok",
        score_status="finite",
        score_proxy_status="finite",
    )
    fields = table_totals("dd", [row, row]).split()
    assert fields[:6] == ["SUM", "--", "dd", "6", "14", "0.1s"]
    assert fields[6:9] == ["--", "--", "--"]
    assert fields[9:] == ["1.001", "0.001", "0.001", "2.469", "4.691"]


@pytest.mark.parametrize(
    "status,expected", [("infinite", "inf"), ("undefined", "undef"), (None, "--")]
)
def test_seed_totals_preserve_unavailable_and_nonfinite_states(
    status: str | None, expected: str
) -> None:
    from claude.score_diagnostics import table_totals

    finite = dict(
        score=2.0, score_status="finite", score_proxy=3.0, score_proxy_status="finite", cz_count=1
    )
    missing = dict(score=None, score_proxy=None, cz_count=None)
    if status is not None:
        missing.update(score_status=status, score_proxy_status=status)
    fields = table_totals("no-dd", [finite, missing]).split()
    assert fields[3] == "--"
    assert fields[-2:] == [expected, expected]


def test_undefined_total_is_not_hidden_by_an_infinite_row() -> None:
    from claude.score_diagnostics import table_totals

    rows = [dict(score=None, score_status=status) for status in ("infinite", "undefined")]
    assert table_totals("ideal", rows).split()[-1] == "undef"
