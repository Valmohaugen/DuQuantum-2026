"""Small-instance layout ranking by the expected sampled challenge score.

This is deliberately limited to N <= 4, where exact density evolution and
randomized low-dimensional quadrature for E[1 / (Z + X)] are practical.
"""
from __future__ import annotations

import importlib
import functools
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binom, qmc

# The fast evaluator is shared with the ryon solution. Temporarily add its
# directory for notebook-style imports where only the toby directory is on
# sys.path, then remove the path change after loading its dependencies.
_RYON_DIR = str(Path(__file__).resolve().parents[1] / "ryon")
if _RYON_DIR not in sys.path:
    sys.path.insert(0, _RYON_DIR)
    try:
        fast_eval = importlib.import_module("fast_eval")
    finally:
        sys.path.remove(_RYON_DIR)
else:
    fast_eval = importlib.import_module("fast_eval")


@functools.lru_cache(maxsize=None)
def _score_kernel(n_qubits, n_exc):
    weights = np.array([i.bit_count() for i in range(2**n_qubits)])
    in_sector = weights == n_exc
    sector_size = math.comb(n_qubits, n_exc)
    choose = lambda a, b: math.comb(a, b) if 0 <= b <= a else 0
    kraw = np.array([
        [sum((-1) ** j * choose(w, j) * choose(n_qubits - w, k - j)
             for j in range(k + 1)) / math.comb(n_qubits, k)
         for k in range(1, n_qubits + 1)]
        for w in range(n_qubits + 1)
    ])
    ideal = np.array([
        choose(k, k // 2) * choose(n_qubits - k, n_exc - k // 2) / sector_size
        if k % 2 == 0 else 0.0
        for k in range(1, n_qubits + 1)
    ])
    return weights, in_sector, sector_size, kraw, ideal


def _score_from_uniforms(pz, px, n_qubits, n_exc, uniforms, shots=10_000):
    """Estimate E[1/(Z+X)] from grouped multinomial sufficient statistics."""
    weights, in_sector, sector_size, kraw, ideal = _score_kernel(n_qubits, n_exc)

    points = np.clip(uniforms, 1e-12, 1 - 1e-12)
    pz_sector = np.asarray(pz[in_sector], dtype=float)
    pz_sector = pz_sector / np.asarray(pz).sum()
    # Sequential conditional binomials exactly sample the C valid outcomes
    # and the aggregate outside-sector bucket using C uniforms.
    z_counts = np.zeros((len(points), sector_size), dtype=np.int64)
    remaining = np.full(len(points), shots, dtype=np.int64)
    remaining_probability = 1.0
    for j, probability in enumerate(pz_sector):
        conditional = min(1.0, probability / max(remaining_probability, 1e-300))
        draws = binom.ppf(points[:, j], remaining, conditional).astype(np.int64)
        z_counts[:, j] = draws
        remaining -= draws
        remaining_probability = max(0.0, remaining_probability - probability)
    accepted = z_counts.sum(axis=1)
    expected = accepted[:, None] / sector_size
    chi2 = ((z_counts - expected) ** 2 / np.maximum(expected, 1e-300)).sum(axis=1)
    z_score = chi2 / sector_size / (np.maximum(accepted, 1) / shots)

    # X correlators depend only on Hamming weight, so sample N+1 buckets
    # instead of all 2**N bitstrings.
    x_weights = np.bincount(weights, weights=px, minlength=n_qubits + 1).astype(float)
    x_weights /= x_weights.sum()
    x_hist = np.zeros((len(points), n_qubits + 1), dtype=np.int64)
    remaining = np.full(len(points), shots, dtype=np.int64)
    remaining_probability = 1.0
    for j, probability in enumerate(x_weights[:-1]):
        conditional = min(1.0, probability / max(remaining_probability, 1e-300))
        draws = binom.ppf(points[:, sector_size + j], remaining, conditional).astype(np.int64)
        x_hist[:, j] = draws
        remaining -= draws
        remaining_probability = max(0.0, remaining_probability - probability)
    x_hist[:, -1] = remaining
    moments = (x_hist / shots) @ kraw
    x_score = np.where(
        ideal[None, :] != 0,
        (ideal[None, :] - moments) ** 2 / np.where(ideal[None, :] != 0, ideal[None, :] ** 2, 1),
        (ideal[None, :] - moments) ** 2,
    ).sum(axis=1)
    scores = 1.0 / (z_score + x_score)
    valid = accepted > 0
    return float(scores[valid].mean()) if np.any(valid) else 0.0


def select_layout(candidates, baseline, cal, n_qubits, n_exc, *, shortlist=20,
                  screen_power=8, refine_power=12,
                  screen_scrambles=2, refine_scrambles=8,
                  confirmation_power=12, confirmation_scrambles=8):
    """Pick from candidates using E[1/(Z+X)] under the calibrated noise model.

    Screen with a small direct QMC estimate and add proxy-ranked layouts to the
    finalist set. Refine the finalists on more points, then confirm the winner
    against the baseline on independent scrambles. Four seeded detuning
    realizations approximate the quasistatic noise average in each layout.
    """
    entries = []
    seed = [n_qubits, n_exc, 2026]
    for circuit, qubits in candidates:
        pz, px = fast_eval.noisy_probs(
            circuit, qubits, cal, np.random.default_rng(seed), realisations=4
        )
        proxy = fast_eval.expected_score(pz, px, n_qubits, n_exc, n_qubits, 10_000)[-1]
        entries.append((circuit, qubits, pz, px, proxy))

    base_circuit, base_qubits = baseline
    if not any(circuit == base_circuit and qubits == base_qubits for _, circuit, qubits, *_ in entries):
        pz, px = fast_eval.noisy_probs(
            base_circuit, base_qubits, cal, np.random.default_rng(seed), realisations=4
        )
        proxy = fast_eval.expected_score(pz, px, n_qubits, n_exc, n_qubits, 10_000)[-1]
        entries.append((base_circuit, base_qubits, pz, px, proxy))

    dimension = math.comb(n_qubits, n_exc) + n_qubits
    screen_sets = [
        qmc.Sobol(dimension, scramble=True, seed=10_000 + i).random_base2(screen_power)
        for i in range(screen_scrambles)
    ]
    scored = []
    for circuit, qubits, pz, px, proxy in entries:
        estimate = np.mean([
            _score_from_uniforms(pz, px, n_qubits, n_exc, points)
            for points in screen_sets
        ])
        scored.append((estimate, proxy, circuit, qubits, pz, px))
    finalists = sorted(scored, key=lambda row: row[0], reverse=True)[:shortlist]
    proxy_finalists = sorted(scored, key=lambda row: row[1], reverse=True)[: max(3, shortlist // 2)]
    for candidate in proxy_finalists:
        if not any(row[2] == candidate[2] and row[3] == candidate[3] for row in finalists):
            finalists.append(candidate)
    baseline_entry = next(
        (row for row in scored if row[2] == base_circuit and row[3] == base_qubits), None
    )
    if baseline_entry is not None and not any(
        row[2] == base_circuit and row[3] == base_qubits for row in finalists
    ):
        finalists.append(baseline_entry)

    refine_sets = [
        qmc.Sobol(dimension, scramble=True, seed=20_000 + i).random_base2(refine_power)
        for i in range(refine_scrambles)
    ]
    refined = []
    for row in finalists:
        scores = np.array([
            _score_from_uniforms(row[4], row[5], n_qubits, n_exc, points)
            for points in refine_sets
        ])
        refined.append((float(scores.mean()), scores, row[2], row[3]))

    best = max(refined, key=lambda result: result[0])
    if best[2] == base_circuit and best[3] == base_qubits:
        return base_circuit, base_qubits

    chosen_entry = next(
        row for row in scored if row[2] == best[2] and row[3] == best[3]
    )
    baseline_entry = next(
        row for row in scored if row[2] == base_circuit and row[3] == base_qubits
    )
    confirmation_sets = [
        qmc.Sobol(dimension, scramble=True, seed=30_000 + i).random_base2(confirmation_power)
        for i in range(confirmation_scrambles)
    ]
    chosen_scores = np.array([
        _score_from_uniforms(chosen_entry[4], chosen_entry[5], n_qubits, n_exc, points)
        for points in confirmation_sets
    ])
    baseline_scores = np.array([
        _score_from_uniforms(baseline_entry[4], baseline_entry[5], n_qubits, n_exc, points)
        for points in confirmation_sets
    ])
    paired = chosen_scores - baseline_scores
    uncertainty = paired.std(ddof=1) / math.sqrt(len(paired))
    if paired.mean() <= 2 * uncertainty:
        return base_circuit, base_qubits
    return best[2], best[3]
