# Plan status: Google Quantum AI Dicke-state challenge (DuQuantum 2026)

| Phase | Status |
| --- | --- |
| Derivation (NN split-and-cyclic-shift, 5-CZ flagged gate, W tree) | done (docstring of `dicke_prep.py`) |
| `create_dicke_state`: layout search, synthesis, ALAP schedule, DD | done, 99 tests pass |
| Notebook injection (`scripts/build_notebook.py`), clean-kernel run | done |
| Noisy benchmark (`scripts/noisy_benchmark.py`) | done for N <= 10, n <= 2 (2026-10-24): about 50–90% of the shot-noise ceiling; DD on vs off is within shot noise |
| Bonus: real adaptive (measurement + feed-forward) construction | pending (currently reuses non-adaptive, score 20.77) |
| Lower CZ count for n >= 2 (tree / divide-and-conquer Dicke) | pending idea |
| Submit via Google form (by hand) | pending |

## Facts worth knowing

* `Willow105` exists only in cirq-google >= 1.8 (dev builds). Conda env: `duquantum`.
* The notebook's `test_circuit` is buggy (`range(qubits)` on a set). Use `check_exact`.
* `two_qubit_matrix_to_cz_operations` is exact only up to global phase. That is harmless, because
  every gate's phase is a scalar.
* No exact 4-CZ version of the flagged gate was found (numerical search), so 5 CZ is used.
