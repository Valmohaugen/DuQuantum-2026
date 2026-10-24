# DuQuantum-2026

we shall prosper

**Challenge:** Google Quantum AI, standard track. Prepare N-qubit, weight-n Dicke states on the
Willow 105-qubit device using only CZ and `PhasedXZGate`. Circuits are scored on hardware by how
uniform the Z-basis distribution is and how close the X-basis correlators are to ideal. The bonus
scores the circuit depth of adaptive circuits.

## Layout

| Path | What |
| --- | --- |
| `Google Quantum AI Challenge.ipynb` | The original challenge notebook, unmodified and read-only. Reference only |
| `solution.ipynb` | **Working notebook**: the solution code in short sections, plus `check`-tagged test cells |
| `solution.py` | **Working script**: a jupytext mirror of `solution.ipynb` (same cells, `# %%` format) |
| `claude/dicke_prep.py` | Loads the solution cells of `solution.ipynb` as the module `dicke_prep` for the tests and tools |
| `claude/tests/` | Exactness, gate set, device validity and runtime tests, plus a mirror-sync check |
| `claude/scripts/noisy_benchmark.py` | Density-matrix noise simulation scored with the challenge's own `overall_score` |
| `claude/tutorial/Dicke_Tutorial.ipynb` | Interactive tutorial that walks through the whole construction, with sliders and exercises |
| `claude/scripts/build_tutorial.py` | Regenerates the tutorial notebook |
| `claude/docs/PLAN_STATUS.md` | Phase status and known quirks |

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
* **Execution:** simulation is the default. The working solution exposes `HARDWARE = False`; hardware
  execution is deliberately opt-in and is never reached by tests or benchmarks in the default mode.

## Usage

```bash
conda activate duquantum                  # python 3.12, cirq / cirq-google 1.8 dev (Willow105 needs >= 1.8)
pip install -r claude/requirements.txt
jupytext --sync solution.ipynb            # after editing either solution file (Jupyter Lab does it on save)
pytest claude/tests -v                    # correctness, DD, simulation, and mirror checks
python -u solution.py                     # exact checks plus resumable multi-seed simulation benchmark
python -u claude/scripts/noisy_benchmark.py
python -u claude/scripts/analyze_benchmark_results.py  # display insights from the saved results
jupyter lab claude/tutorial/Dicke_Tutorial.ipynb   # or open it in VS Code with the duquantum kernel
```

The noisy benchmark compares DD and no-DD across multiple seeds. Edit the configuration block at
the top of `claude/scripts/noisy_benchmark.py` to change the seeds, cases, shot count, or detuning.
It saves an atomic checkpoint after every score under `benchmark_outputs/` and resumes automatically
after interruption. Change `RESUME_FROM_CHECKPOINT` to `False` to force a fresh run.

**Note:** the notebook's provided `test_circuit` calls `range(qubits)` on a set and always raises.
`solution.ipynb` and the tests use `check_exact` instead.

The adaptive entry point is tested through the official `N <= 20` scoring range. The challenge allows
a non-adaptive circuit for this bonus, so the current implementation keeps the exact standard
construction as a legal fallback while adaptive measurement/feed-forward remains an optional future
optimization.
