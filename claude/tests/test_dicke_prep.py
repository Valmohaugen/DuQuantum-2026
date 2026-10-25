"""Correctness tests for dicke_prep: exact noiseless state, gate set, device rules."""

from __future__ import annotations

import itertools
import math
import time

import cirq
import cirq_google
import numpy as np
import pytest

from claude import dicke_prep as dp
from claude.scripts.challenge_calibration import make_challenge_calibration as fake_calibration

SEED = 1234
MAX_MOMENTS = 1750
TIME_LIMIT_S = 60.0


CAL = fake_calibration(SEED)


def matrix_product(oneq, q):
    product = np.eye(2, dtype=complex)
    for slot in oneq:
        if q in slot:
            product = slot[q] @ product
    return product


def dicke_vector(n: int, k: int) -> np.ndarray:
    psi = np.zeros(2**n)
    for ones in itertools.combinations(range(n), k):
        psi[sum(2**i for i in ones)] = 1
    return psi / np.linalg.norm(psi)


def check_circuit(circuit: cirq.Circuit, qubits: set, n: int, k: int) -> None:
    cz, sq, _, _ = CAL
    allowed_pairs = {frozenset(p) for p in cz}
    assert len(qubits) == n
    assert len(circuit) <= MAX_MOMENTS
    for op in circuit.all_operations():
        if len(op.qubits) == 2:
            assert op.gate == cirq.CZ, op
            assert frozenset(op.qubits) in allowed_pairs, op
        else:
            assert isinstance(op.gate, cirq.PhasedXZGate), op
            assert op.qubits[0] in sq, op
    assert circuit.all_qubits() <= qubits
    cirq_google.Willow105.validate_circuit(circuit)


def assert_exact_dicke(circuit: cirq.Circuit, qubits: set, n: int, k: int) -> None:
    order = sorted(qubits)
    psi = cirq.final_state_vector(circuit, qubit_order=order, dtype=np.complex128)
    overlap = abs(np.vdot(dicke_vector(n, k), psi))
    np.testing.assert_allclose(overlap, 1.0, atol=1e-8)


@pytest.mark.parametrize("theta", np.linspace(0.05, math.pi / 2, 6))
def test_mux_gate_on_reachable_inputs(theta):
    c, a, b = cirq.LineQubit.range(3)
    u = cirq.Circuit(dp.mux_ops(c, a, b, theta)).unitary(qubit_order=[c, a, b])
    co, si = math.cos(theta), math.sin(theta)
    e = np.eye(8)
    cases = {
        0b000: e[0b000],
        0b001: co * e[0b001] + si * e[0b010],
        0b011: e[0b011],
        0b111: e[0b111],
        0b101: e[0b110],
    }
    phase = u[0, 0]  # one global phase shared by all reachable inputs
    np.testing.assert_allclose(abs(phase), 1.0, atol=1e-10)
    for inp, out in cases.items():
        np.testing.assert_allclose(u[:, inp], phase * out, atol=1e-10)


@pytest.mark.parametrize("n", range(2, 11))
def test_line_gates_logically_exact(n):
    """The logical gate list is exact for every k (cirq.givens, no compilation)."""
    q = cirq.LineQubit.range(n)
    for k in range(0, n + 1):
        ops = [cirq.X(x) for x in q[n - k :]]
        for g in dp.line_gates(n, k):
            if g.kind == "givens":
                ops.append(cirq.givens(g.theta).on(q[g.p], q[g.p + 1]))
            else:
                ops += dp.mux_ops(q[g.p - 1], q[g.p], q[g.p + 1], g.theta)
        psi = cirq.final_state_vector(cirq.Circuit(ops), qubit_order=q, dtype=np.complex128)
        np.testing.assert_allclose(abs(np.vdot(dicke_vector(n, k), psi)), 1, atol=1e-10)


@pytest.mark.parametrize("n,k", [(n, k) for n in range(1, 12) for k in range(0, n + 1)])
def test_create_dicke_state_exact(n, k):
    circuit, qubits = dp.create_dicke_state(n, k, *CAL)
    check_circuit(circuit, qubits, n, k)
    assert_exact_dicke(circuit, qubits, n, k)


@pytest.mark.parametrize("dd", [False, True])
def test_dd_preserves_state(dd):
    cfg = dp.PrepConfig(use_dynamical_decoupling=dd)
    circuit, qubits = dp.create_dicke_state(9, 3, *CAL, config=cfg)
    assert_exact_dicke(circuit, qubits, 9, 3)


@pytest.mark.parametrize("gap_length", range(1, 11))
def test_fill_gap_trailing_product_is_identity(gap_length):
    q = cirq.LineQubit(0)
    oneq = [{} for _ in range(gap_length)]
    dp._fill_gap(oneq, q, list(range(gap_length)), fold_into=None)
    assert cirq.equal_up_to_global_phase(matrix_product(oneq, q), np.eye(2), atol=1e-10)


@pytest.mark.parametrize("gap_length", range(1, 11))
def test_fill_gap_folded_product_is_identity(gap_length):
    q = cirq.LineQubit(0)
    oneq = [{} for _ in range(gap_length + 1)]
    oneq[-1][q] = dp._Y
    dp._fill_gap(oneq, q, list(range(gap_length)), fold_into=gap_length)
    assert cirq.equal_up_to_global_phase(matrix_product(oneq, q), dp._Y, atol=1e-10)


@pytest.mark.parametrize("n,k", [(30, 1), (30, 15), (40, 20), (60, 30)])
def test_large_instances_fast_and_valid(n, k):
    t0 = time.monotonic()
    circuit, qubits = dp.create_dicke_state(n, k, *CAL)
    assert time.monotonic() - t0 < TIME_LIMIT_S
    check_circuit(circuit, qubits, n, k)


def test_too_many_qubits_raises():
    with pytest.raises(NotImplementedError):
        dp.create_dicke_state(200, 3, *CAL)


def test_empty_calibration_maps_raise_not_implemented():
    with pytest.raises(NotImplementedError, match="no usable qubits"):
        dp.create_dicke_state(1, 0, {}, {}, {}, {})
