"""Verbatim copies of the challenge notebook's helpers, plus two fixes.

Fixes (marked FIX below):
  * test_circuit: `range(qubits)` -> `range(len(qubits))` (the original raises TypeError).
  * get_device(): `cirq_google.Willow105` only exists in Cirq >= 1.8 pre-releases; fall back
    to the identical 'willow_pink' device that ships with stable Cirq 1.6/1.7.
"""
import itertools
import math

import cirq
import cirq_google
import numpy as np


def get_device():
    # FIX: Willow105 is missing from stable Cirq 1.7.0.
    dev = getattr(cirq_google, "Willow105", None)
    if dev is None:
        dev = cirq_google.engine.create_device_from_processor_id("willow_pink")
    return dev


# ----------------------------------------------------------------------------- state check
def create_dicke_statevector(num_qubits: int, num_excitations: int) -> np.ndarray:
    psi = np.zeros(2**num_qubits)
    normalization = 1 / np.sqrt(math.comb(num_qubits, num_excitations))
    qubits = range(num_qubits)
    for excited_qubits in itertools.combinations(qubits, num_excitations):
        idx = sum(2**qubit_number for qubit_number in excited_qubits)
        psi[idx] = normalization
    return psi


def test_circuit(circuit, num_excitations, qubits, sampler=cirq.Simulator()):
    all_qubits = circuit.all_qubits()
    ancilla_qubits = all_qubits.difference(qubits)
    ordered_qubits = sorted(qubits) + sorted(ancilla_qubits)
    keep_indices = range(len(qubits))  # FIX: was range(qubits)
    num_qubits = len(qubits)
    psi_circuit_full = sampler.simulate(circuit, qubit_order=ordered_qubits).final_state_vector
    psi_circuit = cirq.sub_state_vector(
        state_vector=psi_circuit_full, keep_indices=keep_indices
    ) if len(all_qubits) > len(qubits) else psi_circuit_full
    overlap = np.abs(psi_circuit @ create_dicke_statevector(num_qubits, num_excitations)) ** 2
    assert np.isclose(overlap, 1.0, atol=1e-5), f"overlap {overlap}"
    return float(overlap)


# ----------------------------------------------------------------------------- scoring
def check_z_bitstring_distribution(bitstrings: np.ndarray, num_excitations: int) -> float:
    n_shots, n_qubits = bitstrings.shape
    measured_excitations = np.sum(bitstrings, axis=1)
    fraction_in_subspace = np.mean(measured_excitations == num_excitations)
    chi2 = 0
    ideal_prob = 1 / math.comb(n_qubits, num_excitations)
    for indices in itertools.combinations(range(n_qubits), num_excitations):
        ideal_state = np.zeros(n_qubits)
        ideal_state[np.array(indices)] = 1
        match_count = np.sum(np.all(bitstrings == ideal_state, axis=1))
        expected_count = n_shots * fraction_in_subspace * ideal_prob
        chi2 += (match_count - expected_count) ** 2 / expected_count
    return ideal_prob * chi2 / fraction_in_subspace


def get_correlator_average(bitstrings: np.ndarray, correlator_size: int) -> float:
    correlator_sum = 0.0
    n_shots, n_qubits = bitstrings.shape
    for indices in itertools.combinations(range(n_qubits), correlator_size):
        correlator_sum += 1 - 2 * np.mean(np.sum(bitstrings[:, indices], axis=1) % 2)
    return correlator_sum / math.comb(n_qubits, correlator_size)


def check_x_bitstring_distribution(bitstrings, num_excitations, max_correlator_size) -> float:
    comb = lambda n, k: math.comb(n, k) if (k >= 0 and n >= k) else 0
    n_shots, n_qubits = bitstrings.shape
    score = 0.0
    for correlator_size in range(1, max_correlator_size + 1):
        expected_correlator = (
            comb(correlator_size, correlator_size // 2)
            * comb(n_qubits - correlator_size, num_excitations - correlator_size // 2)
            / comb(n_qubits, num_excitations)
            if correlator_size % 2 == 0
            else 0.0
        )
        measured_correlator = get_correlator_average(bitstrings, correlator_size)
        score += (
            (expected_correlator - measured_correlator) ** 2 / expected_correlator**2
            if expected_correlator != 0
            else (expected_correlator - measured_correlator) ** 2
        )
    return score


def overall_score(z_bitstrings, x_bitstrings, num_excitations, max_correlator_size) -> float:
    return 1 / (
        check_z_bitstring_distribution(z_bitstrings, num_excitations)
        + check_x_bitstring_distribution(x_bitstrings, num_excitations, max_correlator_size)
    )


# ----------------------------------------------------------------------------- fake errors
def pick_single_qubit_dropouts(dropout_rate, rng):
    all_qubits = np.array(list(get_device().metadata.qubit_set))
    is_dropout = rng.random(len(all_qubits)) < dropout_rate
    return set(all_qubits[is_dropout])


def generate_qubit_error_rates(median, spread, dropouts, uncertainty, rng):
    all_qubits = np.array(list(get_device().metadata.qubit_set))
    is_working = np.array([q not in dropouts for q in all_qubits])
    working_qubits = all_qubits[is_working]
    error_rate = rng.lognormal(np.log(median), spread, len(working_qubits))
    return dict(zip(working_qubits, zip(error_rate, uncertainty * np.ones(len(working_qubits)))))


def generate_two_qubit_pauli_error_rates(
    median=2.5e-3, spread=0.5, dropout_rate=0.01, uncertainty=5e-4, rng=None,
    single_qubit_dropouts=None,
):
    rng = rng or np.random.default_rng()
    single_qubit_dropouts = single_qubit_dropouts or set()
    all_pairs = np.array(list(get_device().metadata.qubit_pairs))
    no_qubit_dropouts = np.array(
        [np.all([q not in single_qubit_dropouts for q in pair]) for pair in all_pairs]
    )
    is_working = (rng.random(len(all_pairs)) > dropout_rate) * no_qubit_dropouts
    working_pairs = [tuple(pair) for pair in all_pairs[is_working]]
    error_rate = rng.lognormal(np.log(median), spread, len(working_pairs))
    return dict(zip(working_pairs, zip(error_rate, uncertainty * np.ones(len(working_pairs)))))


def fake_calibration(seed: int = 0):
    """Same recipe as the notebook's last code cell, with a fixed seed."""
    rng = np.random.default_rng(seed)
    drop = pick_single_qubit_dropouts(0.01, rng)
    sq = generate_qubit_error_rates(4e-4, 0.5, drop, 2e-4, rng)
    cz = generate_two_qubit_pauli_error_rates(rng=rng, single_qubit_dropouts=drop)
    zero = generate_qubit_error_rates(5e-3, 0.5, drop, 2e-4, rng)
    one = generate_qubit_error_rates(1e-2, 0.5, drop, 3e-4, rng)
    return cz, sq, zero, one