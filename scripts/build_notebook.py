"""Inject dicke_prep.py into the submission notebook (keeps notebook == tested module).

Cell 2  (create_dicke_state stub)          <- dicke_prep.py up to the bonus function
Cell 14 (create_dicke_state_adaptive stub) <- the bonus function
Adds a verification cell after the fake-error-rate cell and an AI-usage cell at the end.
Re-running is idempotent: cells it added are tagged and replaced.

Usage: python scripts/build_notebook.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_PATH = ROOT / "DuQuantum_Google_Standard.ipynb"
SRC = (ROOT / "dicke_prep.py").read_text()
TAG = "added-by-build_notebook"
BONUS_MARKER = "\n\ndef create_dicke_state_adaptive("

CHECK_FN = '''def check_exact(circuit, num_excitations, qubits):
    """Like test_circuit above (which calls range() on a set and always raises)."""
    psi = cirq.final_state_vector(circuit, qubit_order=sorted(qubits), dtype=np.complex128)
    ideal = create_dicke_statevector(len(qubits), num_excitations)
    assert np.isclose(abs(np.vdot(ideal, psi)) ** 2, 1.0, atol=1e-8)
'''

VERIFY_SRC = CHECK_FN + '''

# Verify: exact noiseless Dicke states with the fake calibration above
import time

for n_q in range(2, 11):
    for n_exc in range(0, n_q + 1):
        t0 = time.monotonic()
        circuit, qubits = create_dicke_state(
            n_q, n_exc, cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors
        )
        assert time.monotonic() - t0 < 60
        assert len(circuit) <= 1750
        cirq_google.Willow105.validate_circuit(circuit)
        for op in circuit.all_operations():
            assert op.gate == cirq.CZ or isinstance(op.gate, cirq.PhasedXZGate), op
        check_exact(circuit, n_exc, qubits)
print("[done] all (N, n) with N <= 10 produce exact Dicke states")'''

BONUS_VERIFY_SRC = '''# Verify bonus circuits classically and report the depth score for 2 <= N <= 15
bonus = 0.0
for n_q in range(2, 16):
    for n_exc in range(1, n_q // 2 + 1):
        circuit, qubits = create_dicke_state_adaptive(n_q, n_exc)
        cirq_google.Willow105.validate_circuit(circuit)
        if n_q <= 12:
            check_exact(circuit, n_exc, qubits)
        bonus += n_q * n_exc / len(circuit)
print(f"[done] bonus depth score (2 <= N <= 15): {bonus:.2f}")'''

AI_MD = """## AI usage

This solution was developed with Claude (Claude Code, model Opus 5.5) as an AI assistant.
Prompts given to the AI:

1. "what is the goal of this challenge"
2. "try to do it"
"""


def code_cell(src: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {"tags": [TAG]},
        "outputs": [],
        "source": src.splitlines(keepends=True),
    }


def md_cell(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {"tags": [TAG]}, "source": src.splitlines(keepends=True)}


def main() -> None:
    nb = json.loads(NB_PATH.read_text())
    cells = [c for c in nb["cells"] if TAG not in c.get("metadata", {}).get("tags", [])]
    main_src, bonus_src = SRC.split(BONUS_MARKER)
    bonus_src = BONUS_MARKER.lstrip("\n") + bonus_src

    def find(prefix: str) -> int:
        hits = [i for i, c in enumerate(cells) if "".join(c["source"]).lstrip().startswith(prefix)]
        if len(hits) != 1:
            raise RuntimeError(f"expected one cell starting with {prefix!r}, found {len(hits)}")
        return hits[0]

    i_main = find('"""Hardware-aware') if any(
        "".join(c["source"]).lstrip().startswith('"""Hardware-aware') for c in cells
    ) else find("def create_dicke_state(")
    cells[i_main]["source"] = main_src.splitlines(keepends=True)
    cells[i_main]["outputs"] = []
    i_bonus = find("def create_dicke_state_adaptive(")
    cells[i_bonus]["source"] = bonus_src.splitlines(keepends=True)
    cells[i_bonus]["outputs"] = []

    i_rates = find("single_qubit_dropouts = pick_single_qubit_dropouts")
    cells.insert(i_rates + 1, code_cell(VERIFY_SRC))
    i_score = find("def score_solution()")
    cells.insert(i_score + 1, code_cell(BONUS_VERIFY_SRC))
    cells.append(md_cell(AI_MD))

    for c in cells:  # nbstripout-equivalent
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
    nb["cells"] = cells
    NB_PATH.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n")
    print(f"[done] wrote {NB_PATH.name} ({len(cells)} cells)")


if __name__ == "__main__":
    main()
