# Qubillionaires — DuQuantum 2026 Google Quantum AI Challenge

Our solution to the Google Quantum AI challenge at DuQuantum 2026: prepare the N-qubit,
weight-n Dicke state on Google's Willow processor using only CZ gates between calibrated
neighbours and `cirq.PhasedXZGate` single-qubit gates. The task and the official scorer are in
[`Google Quantum AI Challenge.ipynb`](Google%20Quantum%20AI%20Challenge.ipynb).

**Submission: [`qubillionaires_solution.py`](qubillionaires_solution.py)**. It is a single
self-contained file that imports only `cirq`, `cirq_google`, their dependencies (`numpy`,
`scipy`) and the standard library, as the rules require. It defines both entry points:

| Entry point | Judged on | Our result |
| --- | --- | --- |
| `create_dicke_state(N, n, cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors)` | `overall_score` on real hardware (Z and X basis, 10,000 shots each) | Local noise model, N = 2..8: summed score **17.658**, 1/mean(Z+X) **1.058** |
| `create_dicke_state_adaptive(N, n)` (bonus) | depth: sum of N·n / moments over 2 ≤ N ≤ 15, 1 ≤ n ≤ N/2 (56 cases) | **52.482** |

## Bonus: moments per case

Every one of the 56 circuits passes `cirq_google.Willow105.validate_circuit` and the notebook's
exact-state test (`test_circuit`), and each is returned in under 0.01 s.

| N | n = 1 | 2 | 3 | 4 | 5 | 6 | 7 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2 | 3 | | | | | | |
| 3 | 6 | | | | | | |
| 4 | 7 | 7 | | | | | |
| 5 | 8 | 11 | | | | | |
| 6 | 9 | 13 | 11 | | | | |
| 7 | 9 | 15 | 17 | | | | |
| 8 | 10 | 17 | 19 | 21 | | | |
| 9 | 10 | 19 | 29 | 29 | | | |
| 10 | 11 | 21 | 29 | 37 | 29 | | |
| 11 | 12 | 23 | 32 | 60 | 47 | | |
| 12 | 12 | 25 | 38 | 54 | 78 | 82 | |
| 13 | 12 | 27 | 50 | 70 | 86 | 97 | |
| 14 | 12 | 29 | 50 | 82 | 96 | 106 | 108 |
| 15 | 13 | 29 | 51 | 90 | 101 | 110 | 119 |

## How it works

### Main entry: `create_dicke_state`

The main circuit is chosen per call from the calibration data passed in.

- **Qubit choice.** Each qubit and coupler is weighted by its CZ, single-qubit and readout error
  rates. A readout-bias term penalises placements whose uneven 0/1 readout errors would make the
  measured Z distribution non-uniform.
- **n > N/2.** Prepare D(N, N − n) and flip every qubit at the end.
- **n = 1 (W states).** The excitation spreads down a low-error spanning tree of the chip, one
  Givens rotation per edge (2N − 3 CZ). Children are ordered so that the tree finishes in as few
  rounds as possible.
- **n ≥ 2.** Several constructions compete, and the one with the lowest estimated error on this
  calibration wins:
  - Bärtschi–Eidenbenz split-and-cyclic-shift on a path of qubits, using synthesised short blocks.
  - A "ladder": two halves prepared in parallel and then joined.
  - Whole-state circuits for specific (N, n), found offline as pruned CZ + Ry circuits on small
    grid patches or lines (`archive/synth.py`).
- **Small cases.** For a few small (N, n), a fitted error model ranks every placement of a
  synthesised circuit on the chip. The top two placements are simulated under a noise model and
  replace the default circuit only if they score higher.
- **Compilation.** Everything compiles to CZ + `PhasedXZGate` with dynamical decoupling on long
  idle stretches. Each circuit is checked against the calibrated couplers, the 1,750-moment limit
  and an internal 35 s build guard, well inside the 1-minute limit.

### Bonus entry: `create_dicke_state_adaptive`

The bonus is scored on depth alone and gets no calibration data, so no search runs at call time.
The function returns a frozen table holding the shallowest verified circuit we found for each of
the 56 graded cases. Those circuits came from offline depth searches:

- the constructions above, packed for depth;
- a moment squeeze (z-ejection and realignment);
- learned angles with exact scheduling;
- depth-weighted pruning.

Cases outside 2 ≤ N ≤ 15, 1 ≤ n ≤ N/2 raise `NotImplementedError`.

## Running it

`cirq_google.Willow105` only exists in the Cirq 1.8 pre-releases:

```bash
pip install --pre cirq-google
```

```python
import cirq_google
from qubillionaires_solution import create_dicke_state_adaptive

circuit, qubits = create_dicke_state_adaptive(8, 4)
cirq_google.Willow105.validate_circuit(circuit)
print(len(circuit), "moments")
```

`create_dicke_state` needs calibration maps. The challenge notebook's last cells generate fake
ones, or use `archive/judge.py`:

```python
import sys; sys.path.insert(0, "archive")
import judge
from qubillionaires_solution import create_dicke_state

circuit, qubits = create_dicke_state(10, 3, *judge.fake_calibration(seed=0))
judge.test_circuit(circuit, 3, qubits)  # exact-state check (the notebook's, with its range bug fixed)
```

Local noisy score: a density-matrix model with gate, readout, T1/T2 and detuning noise, three fake
calibrations, N = 2..8.

```bash
cd archive
PYTHONPATH=.. python fast_eval.py --solution qubillionaires_solution --seeds 0 1 2
```

## Repository layout

| Path | Contents |
| --- | --- |
| `qubillionaires_solution.py` | Our submission (both entry points) |
| `Google Quantum AI Challenge.ipynb` | The original challenge notebook, unchanged |
| [`archive/`](archive/README.md) | Earlier solutions, their scores, and the evaluation and synthesis tools |

The solution was developed as `ryon/slim_sol.py`; `git log --follow qubillionaires_solution.py`
shows its full history. The old `claude/` workflow and `research/` notes were removed. They are
still in git history at commit
[`180e9f4`](https://github.com/Valmohaugen/DuQuantum-2026/tree/180e9f4).
