# Plan status: Google Quantum AI Dicke-state challenge (DuQuantum 2026)

| Phase | Status |
| --- | --- |
| Derivation (NN split-and-cyclic-shift, 5-CZ flagged gate, W tree) | done (docstring of `dicke_prep.py`) |
| `create_dicke_state`: layout search, synthesis, ALAP schedule, DD | done, 123 tests pass; DD identity and empty-calibration regressions added (2026-10-24) |
| Working pair `solution.ipynb` + jupytext mirror `solution.py`; original notebook read-only | done (2026-10-24) |
| Noisy benchmark (`claude/scripts/noisy_benchmark.py`) | done for configurable multi-seed cases; checkpointed comparison currently favors no-DD slightly in aggregate |
| Bonus: real adaptive (measurement + feed-forward) construction | optional future optimization; current exact non-adaptive fallback is legal under the challenge rules |
| Lower CZ count for n >= 2 (tree / divide-and-conquer Dicke) | pending idea |
| Submit via Google form (by hand) | pending |
| Interactive tutorial (`claude/tutorial/Dicke_Tutorial.ipynb`) | done (2026-10-24): runs clean from repo root and `claude/tutorial/`, every slider swept headless |

## Facts worth knowing

* `Willow105` exists only in cirq-google >= 1.8 (dev builds). Conda env: `duquantum`.
* `Google Quantum AI Challenge.ipynb` is the untouched original (chmod 444, user request, 2026-10-24). Never edit it.
  The solution lives in `solution.ipynb`, mirrored by `solution.py` (`jupytext --sync solution.ipynb`).
* `from __future__ import annotations` was dropped from the solution: in the mirror script it would sit mid-file
  and be a SyntaxError.
* The notebook's `test_circuit` is buggy (`range(qubits)` on a set). Use `check_exact`.
* `two_qubit_matrix_to_cz_operations` is exact only up to global phase. That is harmless, because
  every gate's phase is a scalar.
* At 4000 shots the score's shot-noise spread (std about 0.3–0.9 at N = 6) is as large as the DD on/off gap;
  compare circuits by averaging seeds, or by exact leakage.
* No exact 4-CZ version of the flagged gate was found (numerical search), so 5 CZ is used.
* Simulation is the default development and benchmark mode. Set the explicit `HARDWARE` switch to `True`
  only for a deliberate hardware submission workflow.
* Benchmark scores are checkpointed atomically after each seed/mode result under the ignored
  `benchmark_outputs/` directory, so interrupted runs can resume without losing completed work.
