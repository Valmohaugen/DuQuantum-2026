"""Independent, bounded exact-state and challenge-contract validation."""

from __future__ import annotations

import itertools
import math

import cirq
import cirq_google
import numpy as np

from .dicke_prep import MAX_MOMENTS

MAX_EXACT_QUBITS = 16
ATOL = 1e-12
RTOL = 1e-10


def dicke_vector(n: int, k: int) -> np.ndarray:
    """Return the normalized real weight-k state in the 2**n dimensional basis.

    Parameters
    ----------
    n, k : int
        Qubit and excitation counts, with 1 <= n <= 16 and 0 <= k <= n.

    Returns
    -------
    numpy.ndarray
        Shape (2**n,), in big-endian computational basis order. Permutation
        symmetry makes the selected qubit order immaterial to this target.

    Raises
    ------
    ValueError
        If the request is invalid or exceeds the exact simulation safety bound.
    """
    if not 1 <= n <= MAX_EXACT_QUBITS or not 0 <= k <= n:
        raise ValueError(f"exact target requires 1 <= N <= {MAX_EXACT_QUBITS}, 0 <= n <= N")
    vector = np.zeros(2**n)
    for positions in itertools.combinations(range(n), k):
        vector[sum(2**position for position in positions)] = 1 / math.sqrt(math.comb(n, k))
    return vector


def validate_preparation(
    circuit: cirq.Circuit,
    qubits: set[cirq.GridQubit],
    n: int,
    k: int,
    calibration: tuple[dict, dict, dict, dict] | None = None,
    *,
    check_state: bool = True,
) -> float | None:
    """Validate gates, routing, depth and optionally exact state fidelity.

    Parameters
    ----------
    circuit, qubits
        Preparation circuit and its N output qubits; no hidden ancillas allowed.
    n, k : int
        Requested qubit and excitation counts.
    calibration : tuple or None
        Four challenge maps, used to check calibrated gates when supplied.
    check_state : bool
        If True, simulate up to 16 qubits and require Dicke fidelity one.

    Returns
    -------
    float or None
        Exact fidelity if checked, otherwise None. Violations raise ValueError
        with diagnostic values. This is independent of the original notebook's
        defective test_circuit helper.
    """
    if len(qubits) != n or not circuit.all_qubits() <= qubits:
        raise ValueError(f"qubit contract failed: requested {n}, returned {len(qubits)}")
    if len(circuit) > MAX_MOMENTS:
        raise ValueError(f"depth {len(circuit)} exceeds {MAX_MOMENTS} moments")
    allowed_pairs = {frozenset(p) for p in calibration[0]} if calibration else None
    for op in circuit.all_operations():
        if op.gate == cirq.CZ:
            if allowed_pairs is not None and frozenset(op.qubits) not in allowed_pairs:
                raise ValueError(f"uncalibrated CZ: {op}")
        elif isinstance(op.gate, cirq.PhasedXZGate):
            if calibration and op.qubits[0] not in calibration[1]:
                raise ValueError(f"uncalibrated single-qubit gate: {op}")
        else:
            raise ValueError(f"unsupported gate: {op}")
    cirq_google.Willow105.validate_circuit(circuit)
    if not check_state:
        return None
    target = dicke_vector(n, k)
    state = cirq.final_state_vector(circuit, qubit_order=sorted(qubits), dtype=np.complex128)
    fidelity = float(abs(np.vdot(target, state)) ** 2)
    if not np.isfinite(fidelity) or not np.isclose(fidelity, 1.0, atol=ATOL, rtol=RTOL):
        raise ValueError(f"Dicke fidelity {fidelity:.16g} differs from one for ({n},{k})")
    return fidelity
