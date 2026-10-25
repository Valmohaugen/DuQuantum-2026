# Archive

Earlier solutions and the tools we used to build and score them. The final submission is
[`../qubillionaires_solution.py`](../qubillionaires_solution.py). It grew out of
`bonus_portfolio_squeeze_sol.py` below and was developed as `ryon/slim_sol.py`.

Until the cleanup, these files lived in `ryon/` and `toby/`. They are now all in this one folder,
so the evaluation tools still import each other by module name. Run them from here:

```bash
cd archive
python fast_eval.py --solution toby_sol --seeds 0 1 2                                 # any solution in this folder
PYTHONPATH=.. python fast_eval.py --solution qubillionaires_solution --seeds 0 1 2    # the final one
```

## Solutions

The "recorded result" column is copied from each file's header or commit. The early files use
different metrics, so compare numbers only within the same metric:

- **e(x)**: expected main score summed over 44 cases, averaged over 10 fake calibrations.
- **fast_eval**: `fast_eval.py` summed score proxy, N = 2..8, three calibrations.
- **bonus**: sum of N·n / moments over 2 ≤ N ≤ 15 (the later files score the corrected
  56-case set, 1 ≤ n ≤ N/2).

| File | Author | Added (EDT) | Recorded result | What it adds |
| --- | --- | --- | --- | --- |
| [`minimal_dicke.py`](minimal_dicke.py) | Ryon | 10-24 16:01 | reference only | About 40 lines: the "card-dealing" algorithm with no qubit selection or gate savings. It is exact but uses many gates. |
| [`dicke_solution.py`](dicke_solution.py) | Ryon | 10-24 16:01 | first full solution | Calibrated qubit patch; W state on a spanning tree (2N − 3 CZ); Bärtschi–Eidenbenz for n ≥ 2, routed with `cirq.RouteCQC`; echo pulses. |
| [`test_sol.py`](test_sol.py) | Toby | 10-24 19:24 | | Swap-free Dicke state prep; became `toby_sol.py`. |
| [`toby_sol.py`](toby_sol.py) | Toby, then Ryon | 10-24 19:34 → 10-25 07:14 | fast_eval 16.615 → 17.528; 1/mean(Z+X) 1.050; bonus 44.00 | The main solution line: grid patches, synthesised blocks, ladder halves, whole-state pruned circuits, readout-bias-aware W trees. |
| [`ladder_sol.py`](ladder_sol.py) | Toby | 10-24 22:57 | e(x) 36.19; bonus 37.53 | Ladder split: prepare two halves in parallel and join them. |
| [`ladder_split_sol.py`](ladder_split_sol.py) | Toby | 10-24 23:33 | e(x) 36.48; bonus 37.53 | Picks the ladder split point by estimated error. |
| [`combined_sol.py`](combined_sol.py) | Toby | 10-24 23:45 | e(x) 36.50; bonus 37.81 | Patches plus a multi-split ladder search. |
| [`halves_start_sol.py`](halves_start_sol.py) | Toby | 10-25 00:09 | fast_eval 17.19; bonus 38.30 | Synthesised halves plus start blocks (later ported into `toby_sol.py`). |
| [`guarded_sol.py`](guarded_sol.py) | Toby | 10-25 00:48 | e(x) 36.54; bonus 38.30 | `toby_sol.py` at a26041d with a global 35 s build guard. |
| [`bonus_squeeze_sol.py`](bonus_squeeze_sol.py) | Toby | 10-25 09:37 | bonus 51.4051 | Z-ejection and realignment pass on the native bonus export. |
| [`bonus_portfolio_squeeze_sol.py`](bonus_portfolio_squeeze_sol.py) | Toby | 10-25 09:55 | bonus 51.8367; fast_eval 17.658; 1/mean(Z+X) 1.058 | Depth-search portfolio plus the moment squeeze; the base of the final solution. |

Two bonus checkpoints by Ryon lived in the removed `research/` folder and are still in git
history:

- [`bonus_priority_20261025/submission.py`](https://github.com/Valmohaugen/DuQuantum-2026/blob/180e9f4/research/bonus_priority_20261025/submission.py)
  (bonus 51.3337, 5764eb4)
- [`bonus_optimize_20261025/submission.py`](https://github.com/Valmohaugen/DuQuantum-2026/blob/180e9f4/research/bonus_optimize_20261025/submission.py)
  (bonus 52.1616, 4e6be5b)

## Tools

| File | Purpose |
| --- | --- |
| [`judge.py`](judge.py) | Copies of the challenge notebook's helpers: `test_circuit` with its `range(len(qubits))` fix, the scorer, and `fake_calibration(seed)`. |
| [`test_dicke.py`](test_dicke.py) | Test harness with a Cirq density-matrix noise model (gate, readout, T1/T2, detuning). |
| [`fast_eval.py`](fast_eval.py) | The same noise model in plain numpy. Prints the summed score proxy and 1/mean(Z+X). |
| [`traj_eval.py`](traj_eval.py) | Trajectory version of `fast_eval.py` for N up to about 20. |
| [`synth.py`](synth.py), [`synth_kernel.c`](synth_kernel.c) | Offline synthesis of short CZ + Ry circuits. The optional C kernel compiles on first use. |
| [`ISSUES.md`](ISSUES.md) | The shared work queue from the optimisation sessions. |

## Score history

The three tables below are copied unchanged from the old top-level README at
[`180e9f4`](https://github.com/Valmohaugen/DuQuantum-2026/blob/180e9f4/README.md), which also has
the longer write-ups they refer to. Only the link targets have changed. `ryon/` and `toby/` files
now live in this folder, `ryon/slim_sol.py` is `../qubillionaires_solution.py`, and `research/`
links point to commit 180e9f4. The files behind the 43.22 row were never committed.

### Bonus score checkpoints

The bonus metric below is the corrected 56-case sum
`sum(N * k / emitted_native_moments)` for `2 <= N <= 15`,
`1 <= k <= N // 2`. Each listed candidate has passed full complex128 state,
relative-phase, native-gate, Willow-routing, and constructor-time checks.
The target remains **45**. These are local bonus scores, not hardware results.

| Date | Best verified bonus score | Cases | Candidate | Evidence |
| --- | ---: | ---: | --- | --- |
| 2026-10-25 | 43.2219421632 | 56 | Frozen native portfolio | Validation, source selection |
| 2026-10-25 09:45 | 51.4051 | 56 | [toby/bonus_squeeze_sol.py](bonus_squeeze_sol.py): native_submission.py (51.3337) plus a z-ejection / realignment pass; (13,3) 55 -> 54, (14,3) 57 -> 55, (15,3) 67 -> 64 moments | all 56 pass Willow105.validate_circuit and judge.test_circuit, max build 2.6 s |
| 2026-10-25 10:05 | 51.8367 | 56 | [toby/bonus_portfolio_squeeze_sol.py](bonus_portfolio_squeeze_sol.py): exp/depth-search portfolio_sol.py (51.5954) plus the same pass | all 56 pass Willow105.validate_circuit and judge.test_circuit, max build 2.7 s |
| 2026-10-25 10:15 | 52.2802 | 56 | [ryon/slim_sol.py](../qubillionaires_solution.py): frozen best-per-case bonus table (52.162 checkpoint + (12,4) 65 -> 56) on the slimmed squeeze portfolio | all 56 pass Willow105.validate_circuit and judge.test_circuit at N <= 15, build 2 s |
| 2026-10-25 10:50 | 52.3618 | 56 | [ryon/slim_sol.py](../qubillionaires_solution.py): + depth-weighted pruning (ALPHA = 20) from the incumbents: (12,4) 65 -> 54, (13,4) 75 -> 70 moments | all 56 pass Willow105.validate_circuit and judge.test_circuit at N <= 15 |
| 2026-10-25 11:00 | 52.4821 | 56 | [ryon/slim_sol.py](../qubillionaires_solution.py): + (8,3) 21 -> 19 moments (27-cz pruned circuit packs tighter) | all 56 pass Willow105.validate_circuit and judge.test_circuit at N <= 15 |

### Best results so far (primary score)

Historical local metric: `cd ryon && python fast_eval.py --seeds 0 1 2` (summed score proxy, N = 2..8,
n <= N/2, three fake calibrations, density-matrix noise model with all X correlator sizes).
These arithmetic totals do not measure the revised harmonic objective; see the paired
evaluation above. The proxy omits X finite-shot variance and is not E[1/penalty].
Larger N are spot checks with `benchmark_outputs/ex/sel.py`. Work queue: `ryon/ISSUES.md`.

| date (EDT) | commit | change | total N = 2..8 |
|---|---|---|---|
| 2026-10-24 | 0dc262c | baseline toby_sol | 16.615 |
| 2026-10-25 00:45 | a26041d | ladder + synthesised halves + start blocks | 17.199 |
| 2026-10-25 01:40 | ef0ec5d | whole-state pruned patches (7,3) (8,3) (8,4) (9,3) (9,4) | 17.435 |
| 2026-10-25 02:00 | f1f5bba | readout-bias-aware W trees | 17.458 |
| 2026-10-25 02:30 | 8993717 | pruned line circuits (7,3) (8,3) (9,3) (10,4), patches (10,3) (11,3) | 17.473 |
| 2026-10-25 02:50 | 761433b | (10,4) 48-cz line, (9,4) 35-cz patch, (8,4) brickwork line, (9,3) 33-cz line | 17.480 |
| 2026-10-25 03:45 | 5a0a94f | N >= 11: (11,4) (11,5) (12,3) (12,4) (13,4) (15,3) | 17.480 (N <= 8 unchanged) |
| 2026-10-25 04:05 | c2e760e | brickwork-start lines (8,3) (9,3); (9,4) 33 cz; (10,5) 42 cz | 17.495 |
| 2026-10-25 04:10 | 0dc1b2c | (10,4) 45-cz line; (11,5) 59 cz (in bec93b1) | 17.495 (N <= 8 unchanged) |
| 2026-10-25 05:40 | 5fbdb31 | depth-weighted pruning (cost = cz + 3 x cz layers): (5,2) (6,2) (6,3) (7,2) | 17.528 |
| 2026-10-25 06:15 | 484dc11 | (10,5) 40-cz depth-weighted line, 0.708 -> 0.728 | 17.528 (N <= 8 unchanged) |
| 2026-10-25 07:10 | a453a9c | (9,4) 37-cz shallow line, 0.778 -> 0.784 | 17.528 (N <= 8 unchanged) |
| 2026-10-25 10:15 | 9a76864 | toby/bonus_portfolio_squeeze_sol.py (main entry = exp/depth-search portfolio_sol.py) | 17.658 |
| 2026-10-25 10:45 | 180e9f4 | qubillionaires_solution.py (final submission, = ryon/slim_sol.py; same main circuits as the row above) | 17.658 |

Source note: the start blocks in the a26041d row were ported from `toby/halves_start_sol.py` (0d47ab3).

### Revised judging metric: 1 / mean(Z + X)

Judging now takes the harmonic mean of the per-case scores, 1 / mean over cases of (Z + X),
instead of the sum of 1 / (Z + X). Every case's penalty counts equally, so the worst cases
(large N, n near N/2) matter most and the small-N lottery no longer helps. `ryon/fast_eval.py`
now prints this metric under its total. Scripts, raw rows and the summary are in
[research/new_metric_20261025](https://github.com/Valmohaugen/DuQuantum-2026/blob/180e9f4/research/new_metric_20261025/summary.txt). The noise model is
fast_eval's, with all X correlator sizes and three fake calibrations (seed 0 only for N = 11, 12).

| date (EDT) | commit | solution | 1/mean(Z+X) N = 2..8 | N = 2..10 | N = 2..12 (seed 0) | mean moments N = 2..8 |
|---|---|---|---|---|---|---|
| 2026-10-25 09:10 | de2d0d0 | ryon/toby_sol.py (main entry point) | 1.050 | 0.959 | 0.805 | 14.1 |
| 2026-10-25 09:10 | 105326Z | bonus milestone 51.04, `create_dicke_state_adaptive` (bonus_sub_105326Z.py) | 0.951 | 0.872 | 0.715 | 12.0 |
| 2026-10-25 10:15 | 9a76864 | toby/bonus_portfolio_squeeze_sol.py (portfolio_sol.py main entry) | 1.058 | 0.959 | not run | |
| 2026-10-25 10:30 | 5764eb4 | bonus 51.33 `native_submission.py`, `create_dicke_state_adaptive` | 0.953 | 0.874 | not run | 11.9 |
| 2026-10-25 10:30 | 9a76864 | bonus 51.84 `toby/bonus_portfolio_squeeze_sol.py`, `create_dicke_state_adaptive` | 0.951 | 0.868 | not run | 11.8 |
| 2026-10-25 10:45 | 180e9f4 | qubillionaires_solution.py (final submission, main entry) | 1.058 | not run | not run | 13.8 |
