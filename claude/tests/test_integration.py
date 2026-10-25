"""Physics regressions for verified adaptations from the upstream implementation."""

from __future__ import annotations

import math

import cirq
import numpy as np
import pytest

from claude import dicke_prep as dp
from claude.scripts.challenge_calibration import make_challenge_calibration
from claude.validation import validate_preparation


@pytest.mark.parametrize("n", [2, 3, 6])
@pytest.mark.parametrize("complement", [False, True])
def test_first_known_split_saves_one_cz(n: int, complement: bool) -> None:
    k = n - 1 if complement else 1
    cal = make_challenge_calibration()
    circuit, qubits = dp.create_dicke_state(
        n, k, *cal, config=dp.PrepConfig(use_dynamical_decoupling=False)
    )
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 2 * n - 3
    validate_preparation(circuit, qubits, n, k, cal)


@pytest.mark.parametrize("theta", [0.0, math.pi / 4, math.pi / 2])
def test_known_input_split_has_correct_amplitudes(theta: float) -> None:
    a, b = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.X(b), dp._first_split_ops(a, b, theta))
    state = cirq.final_state_vector(circuit, qubit_order=[a, b], dtype=np.complex128)
    np.testing.assert_allclose(
        state, [0, math.cos(theta), math.sin(theta), 0], atol=1e-12, rtol=1e-10
    )
    assert sum(op.gate == cirq.CZ for op in circuit.all_operations()) == 1


@pytest.mark.parametrize("gap_length", [0, 1, 3, 4, 5, 12])
def test_sparse_echo_is_exactly_paired(gap_length: int) -> None:
    q = cirq.LineQubit(0)
    slots = [{} for _ in range(gap_length)]
    dp._fill_sparse_gap(slots, q, list(range(gap_length)), min_idle_slots=4)
    pulses = [slot[q] for slot in slots if q in slot]
    assert len(pulses) == (2 if gap_length >= 4 else 0)
    product = np.eye(2, dtype=complex)
    for pulse in pulses:
        product = pulse @ product
    np.testing.assert_allclose(product, np.eye(2), atol=1e-12, rtol=1e-10)


def test_sparse_schedule_preserves_full_unitary_and_reduces_pulses() -> None:
    q = cirq.LineQubit.range(4)
    ops = [
        cirq.H.on_each(*q),
        cirq.CZ(q[0], q[1]),
        *[cirq.CZ(q[1], q[2]), cirq.ry(0.2).on(q[1])] * 12,
        cirq.CZ(q[0], q[3]),
    ]
    ops = list(cirq.flatten_op_tree(ops))
    dense = dp.schedule(ops, True)
    sparse = dp.schedule(ops, True, dd_strategy="sparse")
    bare = dp.schedule(ops, False)
    for candidate in (dense, sparse):
        cirq.testing.assert_allclose_up_to_global_phase(
            candidate.unitary(qubit_order=q), bare.unitary(qubit_order=q), atol=1e-12
        )

    def count(c: cirq.Circuit) -> int:
        return sum(len(op.qubits) == 1 for op in c.all_operations())

    assert count(bare) < count(sparse) < count(dense)


@pytest.mark.parametrize(
    "settings",
    [{"dd_strategy": "unknown"}, {"sparse_min_idle_slots": 1}, {"sparse_min_idle_slots": True}],
)
def test_invalid_echo_config_fails_early(settings: dict) -> None:
    with pytest.raises(ValueError):
        dp.PrepConfig(**settings)


def test_connected_star_routes_when_no_full_path_exists() -> None:
    import cirq_google

    metadata = cirq_google.Willow105.metadata
    neighbors = {q: set() for q in metadata.qubit_set}
    for pair in metadata.qubit_pairs:
        a, b = tuple(pair)
        neighbors[a].add(b)
        neighbors[b].add(a)
    center = next(q for q in sorted(neighbors) if len(neighbors[q]) >= 3)
    leaves = sorted(neighbors[center])[:3]
    nodes = {q: (0.001, 0.0) for q in [center, *leaves]}
    pairs = {(center, q): (0.001, 0.0) for q in leaves}
    cal = (pairs, nodes, nodes, nodes)
    circuit, qubits = dp.create_dicke_state(4, 2, *cal)
    validate_preparation(circuit, qubits, 4, 2, cal)
    with pytest.raises(NotImplementedError):
        dp.create_dicke_state(4, 2, *cal, config=dp.PrepConfig(max_routing_qubits=0))
