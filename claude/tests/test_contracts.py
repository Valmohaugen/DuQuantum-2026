"""Challenge and packaging contracts that the original tests did not cover."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import cirq
import cirq_google
import pytest

from claude import dicke_prep as dp

REPO = Path(__file__).resolve().parents[2]
PATH_COORDINATES: tuple[tuple[int, int], ...] = (
    (6, 0),
    (6, 1),
    (5, 1),
    (5, 2),
    (4, 2),
    (4, 3),
    (3, 3),
    (3, 4),
    (2, 4),
    (2, 5),
    (1, 5),
    (1, 6),
    (0, 6),
    (0, 7),
    (0, 8),
    (1, 8),
    (1, 7),
    (2, 7),
    (2, 6),
    (3, 6),
    (3, 5),
    (4, 5),
    (4, 4),
    (5, 4),
    (5, 3),
    (6, 3),
    (6, 2),
    (7, 2),
    (8, 2),
    (8, 3),
    (7, 3),
    (7, 4),
    (6, 4),
    (6, 5),
    (5, 5),
    (5, 6),
    (4, 6),
    (4, 7),
    (3, 7),
    (3, 8),
    (2, 8),
    (2, 9),
    (2, 10),
    (3, 10),
    (3, 9),
    (4, 9),
    (4, 8),
    (5, 8),
    (5, 7),
    (6, 7),
    (6, 6),
    (7, 6),
    (7, 5),
    (8, 5),
    (8, 4),
    (9, 4),
    (10, 4),
    (10, 5),
    (9, 5),
    (9, 6),
    (8, 6),
    (8, 7),
    (7, 7),
    (7, 8),
    (6, 8),
    (6, 9),
    (5, 9),
    (5, 10),
    (4, 10),
    (4, 11),
    (4, 12),
    (5, 12),
    (5, 11),
    (6, 11),
    (6, 10),
    (7, 10),
    (7, 9),
    (8, 9),
    (8, 8),
    (9, 8),
    (9, 7),
    (10, 7),
    (10, 6),
    (11, 6),
    (12, 6),
    (12, 7),
    (12, 8),
    (11, 8),
    (10, 8),
    (10, 9),
)


def path_calibration() -> tuple[dict, dict, dict, dict]:
    """Reconstruct the valid full-topology moment-limit review fixture."""
    path = [cirq.GridQubit(*pair) for pair in PATH_COORDINATES]
    edges = {frozenset(pair) for pair in zip(path, path[1:])}
    metadata = cirq_google.Willow105.metadata
    one = {q: (0.001, 0.0) for q in metadata.qubit_set}
    two = {tuple(p): (0.001 if p in edges else 0.05, 0.0) for p in metadata.qubit_pairs}
    return two, one, one, one


@pytest.mark.parametrize("dd", [False, True])
def test_never_return_an_over_depth_circuit(dd: bool) -> None:
    try:
        circuit, _ = dp.create_dicke_state(
            90,
            45,
            *path_calibration(),
            config=dp.PrepConfig(use_dynamical_decoupling=dd),
        )
    except NotImplementedError:
        return
    assert len(circuit) <= 1750


@pytest.mark.parametrize("n,k", [(3.5, 1), (3, 1.5), (True, 0)])
def test_noninteger_requests_are_not_silently_truncated(n: object, k: object) -> None:
    with pytest.raises((NotImplementedError, ValueError, TypeError)):
        dp.create_dicke_state(n, k, *path_calibration())


def test_importing_solution_is_inert(tmp_path: Path) -> None:
    """Trip real construction and benchmark calls before any expensive import side effect."""
    script = f"""
import sys
sys.path.insert(0, {str(REPO)!r})
import cirq_google
def trip(*args, **kwargs):
    raise RuntimeError('simulation or benchmark called while importing')
cirq_google.Willow105.validate_circuit = trip
from claude.scripts import noisy_benchmark, analyze_benchmark_results
noisy_benchmark.main = trip
analyze_benchmark_results.main = trip
import solution
assert callable(solution.create_dicke_state)
print('import is inert')
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "import is inert"


def test_physics_module_does_not_execute_notebook_cells() -> None:
    source = (REPO / "claude/dicke_prep.py").read_text()
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "exec"
        for node in ast.walk(tree)
    )


def test_challenge_notebook_is_protected() -> None:
    import hashlib

    assert hashlib.sha256(
        (REPO / "Google Quantum AI Challenge.ipynb").read_bytes()
    ).hexdigest() == ("ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1")
    json.loads((REPO / "Google Quantum AI Challenge.ipynb").read_text())


@pytest.mark.parametrize(
    "rate,uncertainty", [(float("nan"), 0.0), (-0.1, 0.0), (1.1, 0.0), (0.1, -0.1)]
)
def test_invalid_calibration_fails_before_layout(rate: float, uncertainty: float) -> None:
    q = cirq.GridQubit(5, 5)
    with pytest.raises(ValueError, match="calibration"):
        dp.create_dicke_state(1, 0, {}, {q: (rate, uncertainty)}, {}, {})


@pytest.mark.parametrize("n,k", [(0, 0), (4, -1), (4, 5)])
def test_public_line_builder_rejects_invalid_counts(n: int, k: int) -> None:
    with pytest.raises(ValueError):
        dp.line_gates(n, k)


@pytest.mark.parametrize("n,k", [(n, k) for n in range(2, 16) for k in range(n + 1)])
def test_bonus_confirmed_range_all_excitations(n: int, k: int) -> None:
    from claude.validation import validate_preparation

    circuit, qubits = dp.create_dicke_state_adaptive(n, k)
    validate_preparation(circuit, qubits, n, k, check_state=n <= 11)


@pytest.mark.parametrize("n,k", [(n, k) for n in range(16, 21) for k in range(1, n // 2 + 1)])
def test_bonus_extra_structural_stress_range(n: int, k: int) -> None:
    from claude.validation import validate_preparation

    circuit, qubits = dp.create_dicke_state_adaptive(n, k)
    validate_preparation(circuit, qubits, n, k, check_state=False)


@pytest.mark.parametrize("n,k", [(12, 6), (14, 2), (14, 7), (15, 8), (15, 14), (16, 8)])
def test_bonus_larger_exact_states(n: int, k: int) -> None:
    from claude.validation import validate_preparation

    circuit, qubits = dp.create_dicke_state_adaptive(n, k)
    validate_preparation(circuit, qubits, n, k)


def test_standalone_export_imports_outside_repository(tmp_path: Path) -> None:
    from claude.scripts.build_submission import build_submission

    path = build_submission(tmp_path / "submission.py")
    script = "import submission; import cirq_google; d=cirq_google.Willow105.metadata; q={q:(.001,0.) for q in d.qubit_set}; p={tuple(p):(.001,0.) for p in d.qubit_pairs}; c,s=submission.create_dicke_state(3,1,p,q,q,q); assert len(s)==3; cirq_google.Willow105.validate_circuit(c)"
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr
    assert path.read_text() == (REPO / "claude/dicke_prep.py").read_text()


def test_analyzer_import_preserves_notebook_plot_backend(tmp_path: Path) -> None:
    script = f"""
import sys
sys.path.insert(0,{str(REPO)!r})
import matplotlib
matplotlib.use('svg')
import matplotlib.pyplot as plt
before=matplotlib.get_backend()
import claude.scripts.analyze_benchmark_results
assert matplotlib.get_backend()==before, (before,matplotlib.get_backend())
"""
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, result.stderr


def test_solution_compiles_as_python() -> None:
    source = REPO / "solution.py"
    compile(source.read_text(), str(source), "exec")
