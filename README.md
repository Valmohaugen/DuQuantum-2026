# DuQuantum-2026

we shall prosper

**Challenge:** Google Quantum AI, standard track. Prepare N-qubit, weight-n Dicke states on the
Willow 105-qubit device using only CZ and `PhasedXZGate`. Circuits are scored on hardware by how
uniform the Z-basis distribution is and how close the X-basis correlators are to ideal. The bonus
scores the circuit depth of adaptive circuits.

## Layout

| Path | What |
| --- | --- |
| `DuQuantum_Google_Standard.ipynb` | Submission notebook (solution injected by the build script) |
| `[standard_track] Google Quantum AI Challenge.ipynb` | Original challenge notebook, untouched |
| `dicke_prep.py` | The solution. Imports only cirq / cirq_google / numpy / stdlib, so it can be pasted into the notebook |
| `tests/test_dicke_prep.py` | Exactness, gate set, device validity and runtime tests |
| `scripts/build_notebook.py` | Writes `dicke_prep.py` into the notebook cells (idempotent) |
| `scripts/noisy_benchmark.py` | Density-matrix noise simulation scored with the notebook's own `overall_score` |

## Approach

* **n = 1 (W state):** a spanning tree of low-error qubits around a root. The root starts in
  |1⟩ and passes amplitude √(|subtree|/remaining) to each child with one Givens rotation
  (2 CZ). Total 2(N−1) CZ, depth about the tree height.
* **n ≥ 2:** a nearest-neighbour version of Bärtschi & Eidenbenz split-and-cyclic-shift
  ([arXiv:1904.07358](https://arxiv.org/abs/1904.07358)). The cyclic shift is a hole moving
  through a block of ones. Each pair gate uses its left neighbour as a flag ("hole already moving?"),
  so every gate acts on adjacent qubits. The flagged gate
  `Z_c · G(β) · CZ(c,a) · G(α)` with α, β = (θ ± π/2)/2 costs 5 CZ. It is exact on all inputs
  that can occur, and a numerical search found no 4-CZ version. Range bounds on the
  remaining-excitation count remove most flagged gates.
* **n > N/2:** prepare D(N, N−n), then apply X to every qubit.
* **Layout:** a beam search for the qubit path that minimises Σ (CZ count on edge × edge error) +
  readout error. Each edge is weighted by how many CZs the construction puts on it.
* **Schedule:** as late as possible, alternating single-qubit and CZ moments. Idle slots are
  filled with X/Y dynamical decoupling, and the net pulse product is folded into the next gate
  so the ideal state is unchanged.

## Usage

```bash
conda activate duquantum           # python 3.12, cirq / cirq-google 1.8 dev (Willow105 needs >= 1.8)
pip install -r requirements.txt
pytest tests/ -v                   # 99 tests
python scripts/build_notebook.py   # refresh the notebook after editing dicke_prep.py
python -u scripts/noisy_benchmark.py
```

**Note:** the notebook's provided `test_circuit` calls `range(qubits)` on a set and always raises.
The added verification cells use `check_exact` instead.
