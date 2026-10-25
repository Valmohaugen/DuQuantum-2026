"""PORT023 finite-strength W reranking; research only, frozen before seed 33.

Use exact density probabilities under assumed noise and Monte Carlo finite-shot
E[1/penalty]. No quantum circuit or calibration is changed by the simulation.
"""
import time
import numpy as np

from .w_density_candidates import select as candidates, baseline
from .w_stress_noise import probabilities as stress_probabilities
from .w_heterogeneous_noise import probabilities as signed_probabilities
from .w_hardware_probe import score_samples

SCENARIO_SEED = 90210
SCORE_SEED = 90211
REPLICATES = 8192
SOFT_SECONDS = 45.


def select(n, cal):
    start = time.monotonic()
    ref, rqs, analytic, aqs, screen = candidates(n, cal)
    native = screen.pop('native_candidates', [(ref, rqs, screen.get('selected', {}))])
    first = native[0]
    # Keep the analytic winner first, then lowest robust surrogate costs.
    others = sorted(native[1:], key=lambda row: (row[0] != analytic, row[2]['cost']))
    pool = [first] + others[:3 if n == 8 else 1]
    models = ('nominal', 'coherent', 'zz', 'signed_zz') if n == 8 else ('nominal', 'zz', 'signed_zz')
    draws = 2
    rows, values, elapsed_calls = [], [], []
    chosen = 0
    timed_out = False
    if n not in (8, 10) or len(pool) == 1:
        return ref, rqs, analytic, aqs, dict(seconds=time.monotonic()-start, fallback='no distinct finalists or outside domain', screen=screen, rows=[])
    for i, (circuit, qs, source) in enumerate(pool):
        samples = {}
        model_rows = {}
        for model in models:
            # Refuse optional work when the observed worst call with 50% margin
            # would cross the soft deadline. A single call is not preemptible.
            estimate = max(elapsed_calls, default=3. if n == 10 else .5)*1.5
            if time.monotonic()-start + estimate > SOFT_SECONDS:
                timed_out = True
                break
            tick = time.monotonic()
            fn = signed_probabilities if model == 'signed_zz' else stress_probabilities
            pz, px = fn(circuit, qs, cal, SCENARIO_SEED, model, realizations=draws)
            sampled = score_samples(pz, px, n, SCORE_SEED, replicates=REPLICATES)
            if not all(np.isfinite(v).all() for v in sampled.values()):
                timed_out = True
                break
            samples[model] = sampled
            elapsed_calls.append(time.monotonic()-tick)
            model_rows[model] = {str(k): dict(mean=float(v.mean()), mc_se=float(v.std(ddof=1)/np.sqrt(len(v)))) for k, v in sampled.items()}
        if timed_out:
            break
        values.append(samples)
        row = dict(index=i, source=source, models=model_rows, eligible=i == 0)
        if i:
            deltas = np.stack([samples[m][k]-values[0][m][k] for m in models for k in (4, n)])
            means = deltas.mean(axis=1)
            errors = deltas.std(axis=1, ddof=1)/np.sqrt(REPLICATES)
            pooled = deltas.mean(axis=0)
            gain = float(pooled.mean())
            se = float(pooled.std(ddof=1)/np.sqrt(REPLICATES))
            # A numerical uncertainty guard, not a confidence bound on unknown
            # hardware. No modeled endpoint may lose more than two MC SE.
            eligible = bool(np.all(means >= -2*errors) and gain > 2*se)
            row.update(eligible=eligible, mean_gain=gain, paired_mc_se=se,
                       endpoint_gains=means.tolist(), endpoint_mc_se=errors.tolist())
            if eligible and (chosen == 0 or gain > rows[chosen]['mean_gain']):
                chosen = i
        rows.append(row)
    # Any incomplete comparison restores baseline, avoiding time-order bias.
    if timed_out:
        chosen = 0
    c, qs, _ = pool[chosen]
    return ref, rqs, c, qs, dict(seconds=time.monotonic()-start, screen=screen,
                               rows=rows, selected_index=chosen, timed_out=timed_out,
                               requested_candidates=len(pool), completed_candidates=len(rows),
                               models=models, draws=draws, max_model_seconds=max(elapsed_calls, default=0.))
