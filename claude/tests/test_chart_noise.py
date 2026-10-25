"""Validate the chart evaluator's calibration extraction and noisy sampling."""

import cirq
import cirq_google
import numpy as np
import pytest

from claude.scripts.evaluate_candidates import ROOT
from claude.scripts.evaluate_chart_noise import calibration, noisy_circuit, notebook_api


def test_notebook_calibration_matches_existing_recipe(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "ryon"))
    import judge

    monkeypatch.setattr(cirq_google, "Willow105", judge.get_device(), raising=False)
    assert calibration(notebook_api(), 117) == judge.fake_calibration(117)


def test_qsim_gate_noise_matches_exact_density_matrix():
    qsimcirq = pytest.importorskip("qsimcirq")
    a, b = cirq.GridQubit.rect(1, 2)
    circuit = cirq.Circuit(cirq.H(a), cirq.CZ(a, b), cirq.X(b))
    sq = {a: (0.01, 0), b: (0.03, 0)}
    cal = ({(a, b): (0.1, 0)}, sq, sq, sq)
    noisy = noisy_circuit(circuit, cal, "X")
    exact = cirq.DensityMatrixSimulator(dtype=np.complex128).simulate(noisy[:-1])
    expected = np.real(np.diag(exact.final_density_matrix))
    samples = qsimcirq.QSimSimulator(seed=117).run(noisy, repetitions=5000).measurements["m"]
    observed = np.bincount(samples @ np.array([2, 1]), minlength=4) / len(samples)
    np.testing.assert_allclose(observed, expected, atol=0.035, rtol=0)
