"""Finite-shot score diagnostics and the shared terminal table.

Derivation from the protected original challenge scoring cell.
Z=S/M^2 sum_i(A_i-M/C)^2. For A|M~Multinomial(M,q),
E[Z|M>0]=S E[1/M|M>0](1-sum q_i^2)+S sum(q_i-1/C)^2.
For X, per-shot average subset parity h_r has mean mu and variance v;
E[(mean(h_r)-e_r)^2]=(mu-e_r)^2+v/S. Subset correlations are retained.
The inverse of this mean penalty is a proxy, not the mean reciprocal score.
Limits: f=1 gives Zfloor=1-sum q^2; C=1 gives zero Zfloor/Zbias.
Ideal D(2,1) has X order1 variance1/S and order2 zero; at S=2,f=.5,
uniform q gives Zfloor5/6. Empty target sectors are explicitly undefined.
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Sequence

import numpy as np
from scipy.special import logsumexp
from scipy.stats import binom

ATOL = 1e-12
RTOL = 1e-10
TABLE_NOTE = (
    "[table] E[s] = 1 / (Zfloor + Zbias + X), assuming at least one target-sector Z shot.\n"
    "[table] E[s] is a score proxy; sampled is the score from the drawn measurements.\n"
    "[table] Averaging scores differs from taking the reciprocal of the mean penalty.\n"
    "[table] X includes finite-shot sampling variance; -- unavailable, inf infinite, undef undefined."
)


def _probabilities(values: np.ndarray, n: int) -> np.ndarray:
    raw = np.asarray(values)
    if (
        raw.shape != (2**n,)
        or not np.all(np.isfinite(raw))
        or (np.iscomplexobj(raw) and np.any(abs(raw.imag) > ATOL))
    ):
        raise ValueError("diagnostic probabilities must be finite real length-2**N vectors")
    p = raw.real.astype(float)
    if np.min(p) < -ATOL or not np.isclose(p.sum(), 1, atol=ATOL, rtol=RTOL):
        raise ValueError("diagnostic probabilities must be normalized and nonnegative")
    p = np.clip(p, 0, None)
    return p / p.sum()


def score_diagnostics(
    pz: np.ndarray, px: np.ndarray, n: int, k: int, *, shots: int, max_correlator_size: int
) -> dict:
    """Return exact conditional mean-penalty components for supplied Z/X probabilities.

    Inputs are observed probabilities, shape(2**N,), including modeled readout;
    integer N>=1, 0<=k<=N, shots>=1, and positive correlator cutoff (clamped to N).
    Returns JSON-safe f, Zfloor/Zbias/X, score_proxy/status and probability of no
    target-sector Z shots. Invalid inputs raise ValueError. Work is O(shots)
    plus O(2**N+N**2*r**2); no state simulation or RNG is performed.
    Binomial API: https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.binom.html
    """
    if (
        any(
            isinstance(v, (bool, np.bool_)) or not isinstance(v, numbers.Integral)
            for v in (n, k, shots, max_correlator_size)
        )
        or n < 1
        or not 0 <= k <= n
        or shots < 1
        or max_correlator_size < 1
    ):
        raise ValueError("invalid diagnostic sizes, shots or correlator cutoff")
    z, x = _probabilities(pz, n), _probabilities(px, n)
    weights = np.fromiter((i.bit_count() for i in range(2**n)), dtype=int, count=2**n)
    f = min(1.0, float(z[weights == k].sum()))
    pw = np.bincount(weights, weights=x, minlength=n + 1)

    def comb(a: int, b: int) -> int:
        return math.comb(a, b) if 0 <= b <= a else 0

    x_bias, x_floor = 0.0, 0.0
    for r in range(1, min(n, max_correlator_size) + 1):
        h = np.array(
            [
                sum((-1) ** j * comb(w, j) * comb(n - w, r - j) for j in range(r + 1))
                / math.comb(n, r)
                for w in range(n + 1)
            ]
        )
        mu = float(pw @ h)
        variance = float(pw @ ((h - mu) ** 2))
        expected = (
            comb(r, r // 2) * comb(n - r, k - r // 2) / math.comb(n, k) if r % 2 == 0 else 0.0
        )
        denominator = expected**2 if abs(expected) > 0 else 1.0
        x_bias += (mu - expected) ** 2 / denominator
        x_floor += variance / (shots * denominator)
    result = {
        "f": f,
        "z_floor": None,
        "z_bias": None,
        "x_penalty": x_bias + x_floor,
        "x_bias": x_bias,
        "x_floor": x_floor,
        "score_proxy": None,
        "score_proxy_status": "undefined",
        "zero_sector_probability": 1.0,
    }
    if f <= 0:
        return result
    q = z[weights == k] / f
    m = np.arange(1, shots + 1)
    log_weights = binom.logpmf(m, shots, f)
    conditional = np.exp(log_weights - logsumexp(log_weights))
    inverse_count = float(conditional @ (1 / m))
    suffix = np.cumsum(q[::-1])[::-1]
    multinomial_variance = float(2 * np.dot(q[:-1], suffix[1:]))
    floor = shots * inverse_count * multinomial_variance
    bias = float(shots * np.sum((q - 1 / math.comb(n, k)) ** 2))
    penalty = floor + bias + x_bias + x_floor
    proxy = 1 / penalty if penalty > 0 else math.inf
    finite_proxy = math.isfinite(proxy)
    result.update(
        z_floor=floor,
        z_bias=bias,
        score_proxy=proxy if finite_proxy else None,
        score_proxy_status="finite" if finite_proxy else "infinite",
        zero_sector_probability=float(np.exp(shots * np.log1p(-f))) if f < 1 else 0.0,
    )
    return result


def table_header() -> str:
    """Return the requested aligned terminal columns and separator."""
    header = f"{'N':>3} {'n':>2} {'var':>15} {'CZ':>4} {'mom':>4} {'build':>6} {'rules':>5} {'ideal':>7} {'f':>6} {'Zfloor':>6} {'Zbias':>6} {'X':>6} {'E[s]':>7} {'sampled':>7}"
    return header + "\n" + "-" * len(header)


def table_row(n: int | str, k: int | str, variant: str, record: dict) -> str:
    """Format real resource/diagnostic values, keeping nonfinite/missing states explicit."""

    def number(key: str, width: int = 6, decimals: int = 3) -> str:
        value = record.get(key)
        if value is None:
            status = (
                record.get("score_status", "")
                if key == "score"
                else record.get("score_proxy_status", "")
                if key == "score_proxy"
                else record.get(key + "_status", "")
            )
            word = "inf" if status == "infinite" else "undef" if status == "undefined" else "--"
            return f"{word:>{width}}"
        text = f"{value:.{decimals}f}"
        return f"{text:>{width}}" if len(text) <= width else f"{value:>{width}.3g}"

    cz = "--" if record.get("cz_count") is None else str(record["cz_count"])
    moments = "--" if record.get("moments") is None else str(record["moments"])
    build = "--" if record.get("build_seconds") is None else f"{record['build_seconds']:.1f}s"
    return f"{n:>3} {k:>2} {variant:>15} {cz:>4} {moments:>4} {build:>6} {record.get('rules', '--'):>5} {number('fidelity', 7, 5)} {number('f')} {number('z_floor')} {number('z_bias')} {number('x_penalty')} {number('score_proxy', 7)} {number('score', 7)}"


def table_totals(variant: str, records: Sequence[dict]) -> str:
    """Format arithmetic sums of stored additive columns for one seed and variant.

    Parameters
    ----------
    variant : str
        Display label for one DD/no-DD/ideal variant.
    records : sequence of dict
        Stored rows for one seed, with native counts, build times in seconds,
        dimensionless penalties/scores and explicit nonfinite score statuses.

    Returns
    -------
    str
        An aligned SUM row. Missing, undefined and infinite contributors remain
        explicit. Build time includes cached values. Fidelity, survival, rule
        labels and case identifiers are not additive. No diagnostics, simulation
        or sampling are performed.

    Raises
    ------
    ValueError
        If no records are supplied.
    """
    if not records:
        raise ValueError("seed totals require at least one record")
    totals = {}
    for key in (
        "cz_count",
        "moments",
        "build_seconds",
        "z_floor",
        "z_bias",
        "x_penalty",
        "score_proxy",
        "score",
    ):
        status_key = "score_status" if key == "score" else key + "_status"
        statuses = [row.get(status_key) for row in records]
        values = [row.get(key) for row in records]
        totals[key] = None
        if "undefined" in statuses or any(
            value is not None and math.isnan(value) for value in values
        ):
            totals[status_key] = "undefined"
        elif any(value is None and status != "infinite" for value, status in zip(values, statuses)):
            continue
        elif "infinite" in statuses or any(
            value is not None and math.isinf(value) for value in values
        ):
            totals[status_key] = "infinite"
        else:
            try:
                totals[key] = sum(values) if key in {"cz_count", "moments"} else math.fsum(values)
            except OverflowError:
                totals[status_key] = "infinite"
    return table_row("SUM", "--", variant, totals)
