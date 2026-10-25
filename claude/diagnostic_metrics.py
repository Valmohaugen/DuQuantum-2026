"""Scientific diagnostics independent of plotting and notebook presentation.

The X-correlator formula follows the original challenge scoring cell: flipping
r selected bits preserves total weight only when r is even and exactly r/2
selected bits were one. There are C(r,r/2) C(N-r,k-r/2) such weight-k strings,
out of C(N,k). Thus the ideal average is that ratio (zero for odd r). For
r=0 it gives one; k=0 or k=N gives zero for every nonempty correlator; D(2,1)
has <XX>=1. Distribution tests exercise these limits independently.
"""

from __future__ import annotations

import itertools
import math
from collections import Counter
from collections.abc import Sequence

import cirq
import numpy as np
from scipy.stats import t

from claude.scripts.noisy_benchmark import NoiseConfig
from claude.validation import ATOL, RTOL, dicke_vector

MAX_CORRELATOR_SIZE = 4
MAX_DISTRIBUTION_QUBITS = 10
CONFIDENCE = 0.95
PHASE_EPS = 1e-12


def state_metrics(state: np.ndarray, k: int) -> dict:
    """Measure exact-state fidelity, leakage and globally aligned phase/amplitude errors.

    Parameters
    ----------
    state : numpy.ndarray
        Normalized complex state vector of shape (2**N,), N<=16. Its first
        qubit is the most significant bit. Invalid norm/shape/NaN raises ValueError.
    k : int
        Excitation number. The target is the positive-amplitude symmetric Dicke state.

    Returns
    -------
    dict
        JSON-ready scalar metrics and target-subspace amplitudes/phases.
        Global phase is removed using target overlap; if overlap is zero,
        aligned phase errors are unavailable. Roundoff norm error is retained.
    """
    state = np.asarray(state, dtype=np.complex128)
    if (
        state.ndim != 1
        or len(state) < 2
        or len(state) & (len(state) - 1)
        or not np.all(np.isfinite(state))
    ):
        raise ValueError("state must be a finite length-2**N vector, N>=1")
    n = len(state).bit_length() - 1
    target = dicke_vector(n, k)
    norm = float(np.vdot(state, state).real)
    if not np.isclose(norm, 1.0, atol=ATOL, rtol=RTOL):
        raise ValueError(f"state norm squared {norm:.16g} is not one")
    state = state / np.sqrt(norm)
    overlap = np.vdot(target, state)
    reference = abs(overlap) > PHASE_EPS
    aligned = state * np.exp(-1j * np.angle(overlap)) if reference else state
    indices = np.flatnonzero(target)
    fidelity = min(1.0, float(abs(overlap) ** 2))
    probabilities = abs(state) ** 2
    outside = np.ones(len(state), dtype=bool)
    outside[indices] = False
    leakage = float(probabilities[outside].sum())
    phases = np.angle(aligned[indices])
    phase_defined = abs(aligned[indices]) > PHASE_EPS
    return {
        "n": n,
        "k": k,
        "dimension": len(state),
        "norm_squared": norm,
        "fidelity": fidelity,
        "infidelity": max(0.0, 1 - fidelity),
        "leakage": leakage,
        "phase_reference_defined": bool(reference),
        "max_amplitude_error": float(np.max(abs(aligned - target))) if reference else None,
        "max_phase_error_rad": float(np.max(abs(phases[phase_defined])))
        if reference and np.any(phase_defined)
        else None,
        "basis_indices": indices.tolist(),
        "target_amplitude": float(target[indices[0]]),
        "aligned_real": aligned[indices].real.tolist(),
        "aligned_imag": aligned[indices].imag.tolist(),
        "phase_errors_rad": [
            float(p) if defined and reference else None for p, defined in zip(phases, phase_defined)
        ],
    }


def _distribution(probs: np.ndarray, n: int) -> np.ndarray:
    raw = np.asarray(probs)
    if not np.all(np.isfinite(raw)) or (np.iscomplexobj(raw) and np.any(abs(raw.imag) > ATOL)):
        raise ValueError("probabilities must be finite and real")
    values = raw.real.astype(float)
    if values.shape != (2**n,) or not np.all(np.isfinite(values)) or np.min(values) < -ATOL:
        raise ValueError("probabilities must be finite, nonnegative and have shape (2**N,)")
    if not np.isclose(values.sum(), 1, atol=ATOL, rtol=RTOL):
        raise ValueError(f"probability mass {values.sum():.16g} is not one")
    values = np.clip(values, 0, None)
    return values / values.sum()


def distribution_metrics(
    pz: np.ndarray, px: np.ndarray, n: int, k: int, max_correlator_size: int = MAX_CORRELATOR_SIZE
) -> dict:
    """Separate leakage, conditional Z nonuniformity, and average X-correlator errors.

    Z/X inputs are observed probabilities (including readout), shape (2**N,),
    not sampled bitstrings. N<=10 is a deliberate computation bound. Returns
    exact metrics for the supplied ensemble, not estimates of hardware fidelity.
    Conditional uniformity is unavailable when no mass remains in weight k.
    """
    if not 1 <= n <= MAX_DISTRIBUTION_QUBITS or not 0 <= k <= n or max_correlator_size < 1:
        raise ValueError("invalid distribution request or N exceeds diagnostic bound")
    z, x = _distribution(pz, n), _distribution(px, n)
    target = abs(dicke_vector(n, k)) ** 2
    weights = np.array([i.bit_count() for i in range(2**n)])
    in_subspace = weights == k
    mass = float(z[in_subspace].sum())
    weight_probs = np.bincount(weights, weights=z, minlength=n + 1)
    bit_array = (np.arange(2**n)[:, None] >> np.arange(n - 1, -1, -1)) & 1
    orders = list(range(1, min(n, max_correlator_size) + 1))
    expected, observed = [], []

    def comb(a: int, b: int) -> int:
        return math.comb(a, b) if 0 <= b <= a else 0

    for r in orders:
        expected.append(
            comb(r, r // 2) * comb(n - r, k - r // 2) / math.comb(n, k) if r % 2 == 0 else 0.0
        )
        values = []
        for indices in itertools.combinations(range(n), r):
            signs = 1 - 2 * (bit_array[:, indices].sum(axis=1) % 2)
            values.append(float(x @ signs))
        observed.append(float(np.mean(values)))
    return {
        "n": n,
        "k": k,
        "leakage": float(z[~in_subspace].sum()),
        "subspace_probability": mass,
        "weight_probabilities": weight_probs.tolist(),
        "z_total_variation": float(0.5 * np.abs(z - target).sum()),
        "conditional_uniformity_tv": float(
            0.5 * np.abs(z[in_subspace] / mass - 1 / math.comb(n, k)).sum()
        )
        if mass > ATOL
        else None,
        "x_orders": orders,
        "x_expected": expected,
        "x_observed": observed,
        "x_residuals": (np.array(observed) - expected).tolist(),
        "z_probabilities": z.tolist(),
        "x_probabilities": x.tolist(),
    }


def circuit_metrics(
    circuit: cirq.Circuit,
    qubits: set[cirq.GridQubit],
    cal: tuple,
    k: int | None = None,
    noise: NoiseConfig = NoiseConfig(),
) -> dict:
    """Count native gates, calibrated error proxies and idle times for a scheduled circuit.

    Parameters
    ----------
    circuit, qubits
        Native preparation and all output qubits, including untouched outputs.
    cal : tuple
        Four challenge calibration maps. Missing gate calibration raises KeyError.
    k : int or None
        If supplied, ideal occupancy k/N weights the readout proxy; otherwise 1/2.
    noise : NoiseConfig
        Moment durations in ns. Parallel moments use their slowest native gate.

    Returns
    -------
    dict
        JSON-ready totals, per-qubit and per-coupler records. Error proxies are
        sums of count*error, not probabilities or fidelity predictions.
    """
    if not qubits or not circuit.all_qubits() <= qubits:
        raise ValueError("a nonempty output set must contain every circuit qubit")
    if k is not None and not 0 <= k <= len(qubits):
        raise ValueError("invalid ideal excitation count")
    oneq = Counter()
    pairs = Counter()
    busy = Counter()
    durations = []
    order = sorted(qubits)
    position = {q: i for i, q in enumerate(order)}
    schedule = np.zeros((len(order), len(circuit)), dtype=int)
    for moment_index, moment in enumerate(circuit):
        dt = noise.t_cz_ns if any(len(op.qubits) == 2 for op in moment) else noise.t_1q_ns
        durations.append(dt)
        for op in moment:
            if op.gate == cirq.CZ:
                pairs[tuple(sorted(op.qubits))] += 1
            elif isinstance(op.gate, cirq.PhasedXZGate):
                oneq[op.qubits[0]] += 1
            else:
                raise ValueError(f"unsupported native diagnostic gate: {op}")
            for q in op.qubits:
                busy[q] += dt
                schedule[position[q], moment_index] = 2 if op.gate == cirq.CZ else 1
    duration = float(sum(durations))
    cz_rates = {frozenset(pair): rate for pair, (rate, _) in cal[0].items()}
    p1 = k / len(qubits) if k is not None else 0.5
    qubit_rows = []
    for q in sorted(qubits):
        e0, e1 = cal[2].get(q, (0.0, 0.0))[0], cal[3].get(q, (0.0, 0.0))[0]
        qubit_rows.append(
            {
                "row": q.row,
                "col": q.col,
                "label": f"{q.row},{q.col}",
                "oneq_count": oneq[q],
                "oneq_error": float(cal[1][q][0]),
                "idle_ns": duration - float(busy[q]),
                "idle_fraction": 1 - float(busy[q]) / duration if duration else None,
                "readout_proxy": float((1 - p1) * e0 + p1 * e1),
            }
        )
    couplers = [
        {
            "a": [a.row, a.col],
            "b": [b.row, b.col],
            "cz_count": count,
            "cz_error": float(cz_rates[frozenset((a, b))]),
        }
        for (a, b), count in sorted(pairs.items())
    ]
    error = sum(row["cz_count"] * row["cz_error"] for row in couplers) + sum(
        row["oneq_count"] * row["oneq_error"] for row in qubit_rows
    )
    return {
        "moments": len(circuit),
        "cz_count": sum(pairs.values()),
        "oneq_count": sum(oneq.values()),
        "duration_ns": duration,
        "gate_error_proxy": float(error),
        "readout_error_proxy": sum(row["readout_proxy"] for row in qubit_rows),
        "qubits": qubit_rows,
        "couplers": couplers,
        "schedule_types": schedule.tolist(),
        "moment_durations_ns": durations,
    }


def mean_interval(values: Sequence[float], confidence: float = CONFIDENCE) -> dict:
    """Return a Student-t interval for a finite sample mean, with explicit small-N limits.

    mean ± t.ppf((1+confidence)/2,n-1)*s/sqrt(n), using sample SD with n-1.
    For independent approximately normal replicates this is a confidence
    interval; reciprocal scores can be heavy-tailed, so interpretation is
    approximate. A singleton supplies a mean but no interval; empty data supplies
    neither. Nonfinite inputs or invalid confidence raise ValueError.
    Reference: scipy.stats.t, https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html
    """
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or not np.all(np.isfinite(array)) or not 0 < confidence < 1:
        raise ValueError("interval requires a finite one-dimensional sample and 0<confidence<1")
    count = len(array)
    average = float(array.mean()) if count else None
    se = float(array.std(ddof=1) / np.sqrt(count)) if count > 1 else None
    half = float(t.ppf((1 + confidence) / 2, count - 1) * se) if count > 1 else None
    return {
        "count": count,
        "mean": average,
        "standard_error": se,
        "confidence": confidence,
        "lower": average - half if half is not None else None,
        "upper": average + half if half is not None else None,
    }
