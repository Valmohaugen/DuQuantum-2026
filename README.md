# DuQuantum 2026 — Dicke-state preparation

Prepare exact weight-n Dicke states on calibrated Willow qubits using CZ and
`cirq.PhasedXZGate`. Hardware judging compares Z distributions and X correlators.
The bonus rewards depth and permits the current non-adaptive construction.
The organizer confirmed bonus grading for **2 ≤ N ≤ 15** and corrected the original
validator to use `range(len(qubits))`. Hidden grading cases and correlator sizes remain
undisclosed. The original challenge notebook stays unchanged and supplies the official scorer.

## Environment and local checks

Use the project environment with Python **3.12.15**. The dependency lock targets the tested
macOS environment and pins the Cirq 1.8 development build required for Willow105.
From the repository root, create an environment when needed, then install the lock:

```bash
conda create --name duquantum --channel conda-forge python=3.12.15 pip
conda activate duquantum
python -m pip install -r claude/requirements.txt
python -m pip check
```

For an existing environment, start at activation. The dependency files keep their existing
locations. To deliberately update dependencies, edit `claude/requirements.in`, regenerate
with `pip-compile --output-file claude/requirements.lock claude/requirements.in`, and rerun
all checks. No global package installation is needed.

```bash
python -m claude.scripts.check_quality lint
python -m claude.scripts.check_quality format
python -m claude.scripts.check_artifacts
python -m pytest claude/tests -v
pre-commit install
pre-commit run --all-files
```

The check helper supplies isolated Ruff settings: Python 3.12, a 100-character formatting
width, and `E4/E7/E9/F/I`. Reference implementations, generated artifacts and notebooks are
excluded. The artifact checker verifies the original challenge's SHA-256 and compiles
maintained Python sources. Tests remain tracked under `claude/tests/` and do not require
working notebooks or private documentation. The local commit hook runs these checks.

## Run the solution

```bash
python -u solution.py
```

The default full run shows six phases:

1. **Checks** — lint, formatting, Python syntax/original-file protection, and pytest.
2. **Validation** — selected constructors checked against exact states and device rules.
3. **Submission** — build the configured standalone local `submission.py` export.
4. **Bonus validation** — load that export and validate both actual entry points.
5. **Benchmark** — run or resume DD/no-DD/ideal simulations and save analysis quietly.
6. **Diagnostics** — save the eight-view scientific report and figures.

The checks phase uses one updating progress bar. Each preliminary check and each completed
pytest item contributes one unit; the total becomes available after collection. Skipped
items and setup/teardown failures are counted once per item. The percentage measures work
items, not elapsed time. Redirected output uses concise status lines. Full diagnostics are
saved to the terminal log and replayed on failure; failures return a nonzero status.

Comparison is optional:

```bash
python -u solution.py --comparison
python -u solution.py --mode compare --cases 2,1 4,2 15,7 --seed 42
```

`--comparison` appends a seventh phase in all mode. `--mode compare` requests comparison
directly. `--skip-comparison` remains accepted and is mutually exclusive with `--comparison`.
The comparison includes maintained dense/sparse/off DD variants and teammate references;
`--no-upstream` omits reference variants, and `--baseline /absolute/path/to/module.py` adds
a frozen constructor. Optional reference failures retain their traceback and receive no
score; maintained-solver and shared scoring failures stop the run.

The default **full** preset benchmarks all **28 nontrivial cases N=2–8**, with five seeds,
10,000 shots per basis, two detuning realizations, and all applicable X-correlator orders.
DD/no-DD/ideal produce 420 records. Both exported functions are also checked exactly for
**N=2–15, n=0–N**: 133 cases and **266 circuits**, including product boundaries. These
bonus checks test exact state fidelity and device rules, rather than a noisy sampled score.
Constructor-only resource probes extend through N=90 without density simulation.

Smaller and focused runs keep the existing flags:

```bash
python -u solution.py --preset quick
python -u solution.py --preset standard
python -u solution.py --cases 2,1 4,2 6,3 --seeds 1,2,3 --shots 2000 --dd-strategy sparse
python -u solution.py --no-check --no-bonus-check
python -u solution.py --mode validate --cases 15,7 --bonus-check
python -u solution.py --mode diagnose --results path/to/noisy_benchmark_results.json
python -u solution.py --plan
python -u solution.py --help
```

Quick uses two cases, one seed, 1,000 shots and one realization; standard uses six cases
and three seeds. Smaller presets, narrower modes and explicit case ranges skip broad
software/bonus suites by default. Add `--check` or `--bonus-check` to include them.
Explicit model/case options override presets. `--plan` and `--help` run no experiments
and create no output directories.

## Terminal tables and score interpretation

Each benchmark seed prints native resources and diagnostic values:

| Column | Meaning |
| --- | --- |
| N, n, var | Qubits, target excitation count and DD/no-DD/ideal variant |
| CZ, mom, build | Native CZ count, circuit moments and recorded construction time |
| rules, ideal | Device-rule status and exact noiseless Dicke-state fidelity |
| f | Probability of measuring the target excitation count in Z |
| Zfloor | Mean Z penalty from finite-shot sampling in the target sector |
| Zbias | Mean Z penalty from nonuniform probabilities within that sector |
| X | Mean X-correlator penalty, including finite-shot variance |
| E[s] | Reciprocal mean-penalty score proxy, defined below |
| sampled | Official score from the actual drawn Z/X measurement samples |

`E[s] = 1 / (Zfloor + Zbias + X)` assumes at least one Z shot has exactly n excitations.
It is a proxy: the reciprocal of a mean penalty differs from the mean of reciprocal
scores. For example, penalties 1 and 3 give a reciprocal mean penalty of 0.5, while the
mean sampled reciprocal is 2/3. X includes sampling variance even for an ideal circuit.
`--` means unavailable, `inf` infinite, and `undef` undefined.

Each seed table ends with a **SUM row per variant** for CZ, moments, build time, Zfloor,
Zbias, X, E[s], and sampled score. These are arithmetic sums of full-precision stored
values, including each row's score proxy; they are not a recomputed reciprocal of summed
penalties. IDs, fidelity, survival probability and rule labels are not summed. Build-time
totals include recorded cached times, rather than measuring the current seed's wall time.
Missing, undefined and infinite contributors remain explicit. `--no-ideal` omits ideal
rows and totals. Resuming a checkpoint prints the same summaries without resampling.

## Saved results and reproducibility

Every invocation creates `benchmark_outputs/solution_runs/<run-id>/` with a run index,
`run.json`, the complete `terminal-output.log`, stage reports/data, and the local export
when applicable. Analysis still saves its report and plot and is linked from the run index,
without printing a separate phase or its full report body. A failed analysis retains the
completed raw benchmark in the manifest. Failed stages keep partial results and tracebacks.
Checks also save `checks.json` and structured pytest progress in `check-progress.jsonl`.

Figures are saved under **`figs/solution_runs/<run-id>/`**. Diagnostics and optional
comparison save PNG/PDF; analysis saves PNG. Bonus validation saves Markdown, JSON and
CSV evidence for both entry points. Standalone tools retain their existing commands:

```bash
python -u -m claude.scripts.noisy_benchmark
python -u -m claude.scripts.analyze_benchmark_results path/to/noisy_benchmark_results.json
python -u -m claude.scripts.diagnose --results path/to/noisy_benchmark_results.json
python -u -m claude.scripts.compare_solutions --cases 4,2 6,3 --seeds 1,2,3
```

Reusable benchmark checkpoints live under `benchmark_outputs/runs/<fingerprint>/`.
The **benchmark fingerprint** identifies the effective noise/preparation settings,
calibration maps, participating sources, original scoring code and runtime versions.
The **calibration hash** identifies the generated qubit/coupler rates and uncertainties;
`--calibration-seed` controls their reproducible generation. Matching validated checkpoints
resume. Source or model changes produce a different fingerprint; `--fresh` creates a
separate repeat. Existing runs, figures and recorded outputs are preserved.

Shot seeds and physical-noise seeds are independent. Paired comparisons match replicate
seeds; aggregate uncertainty comes from paired seed means. Across-case spread describes
different cases, rather than uncertainty reduced by more shots. One seed cannot estimate
uncertainty. Undefined/infinite scores remain explicit and are excluded from finite paired
statistics. Historical data without complete provenance is labeled legacy. The original
historical report and PNG survive; the original 240 raw records are unavailable and have
not been reconstructed or relabeled as current data.

## Physics, diagnostics and export

For n=1, a low-error spanning tree distributes excitation using subtree-size Givens angles.
The known first split uses one CZ; later splits use two. For n≥2, nearest-neighbor
split-and-cyclic-shift preparation follows [Bärtschi and Eidenbenz](https://arxiv.org/abs/1904.07358).
The five-CZ flagged gate is valid on the reachable subspace. Complementary states use
bitwise X. The default optimized constructor combines a reachable first Givens/MUX pair
into four CZ gates and can use an exact five-CZ square for D(4,2). Closed-form angles,
derivations and limiting cases remain in the canonical module. Path/routing fallbacks
remain available. `--construction analytic` retains the previous constructor and older
recorded datasets retain their original preparation when reanalyzed.

Supported circuits obey the **1,750-moment inclusive limit**. Unsupported inputs raise
`NotImplementedError`; a heuristic search failure is not proof that no legal path exists.
The independent validator checks gates, connectivity, depth, exact amplitudes and relative
phases. Extra N=16–20 cases remain structural stress tests. Teammate implementations under
`ryon/` and `toby/` and the local reference-routing adapter remain available for comparison.

Density simulation is bounded to ten qubits because memory grows as 4^N. Comparison samples
noise only through N=6 and checks larger states structurally/exactly. Constructor-only
resource probes can be larger. The approximate noise model includes depolarizing errors,
T1/Tphi decay, readout and quasi-static detuning between native moments. Native single-qubit
gates can temporarily change excitation number, so detuning can affect final leakage.
Local correlator cutoffs and cases do not establish hidden grading choices or hardware-wide
DD performance. Sparse DD is optional and can add emitted moments; depth is checked afterward.

Diagnostics save exact-state, distribution/correlator, placement/cost, native schedule,
resource scaling, detuning sensitivity, paired-score and seed-convergence views. Six views
are available without raw score data; all eight require a completed dataset. The matched
score plot displays 0–2 with overflow markers while full values remain in tables/JSON.
Intervals are approximate and conditional on one synthetic calibration; calibration-rate
uncertainties are not propagated. Report generation is independent of private documentation.

```bash
python -m claude.scripts.build_submission submission_outputs/submission.py
```

The export includes both required entry points and imports outside the repository. Unified
runs embed the selected preparation settings; local noise/shot settings do not alter the
exported constructor. Review the original challenge and the current upload form for all
required supporting material and upload by hand. The workflow performs local CPU simulation;
it does not submit hardware jobs, commit, push, or publish automatically.

## Bonus score checkpoints

The bonus metric below is the corrected 56-case sum
`sum(N * k / emitted_native_moments)` for `2 <= N <= 15`,
`1 <= k <= N // 2`. Each listed candidate has passed full complex128 state,
relative-phase, native-gate, Willow-routing, and constructor-time checks.
The target remains **45**. These are local bonus scores, not hardware results.

| Date | Best verified bonus score | Cases | Candidate | Evidence |
| --- | ---: | ---: | --- | --- |
| 2026-10-25 | 43.2219421632 | 56 | [Frozen native portfolio](research/bonus_portfolio_20261025/portfolio_submission.py) | [Validation](research/bonus_portfolio_20261025/validation.json), [source selection](research/bonus_portfolio_20261025/merge_results.json) |

Reusable tasks and their acceptance criteria are recorded in
[the shared issue queue](ryon/ISSUES.md) and
[the bonus task board](research/bonus_portfolio_20261025/tasks.json).

## Best results so far (primary score)

Local metric: `cd ryon && python fast_eval.py --seeds 0 1 2` (expected notebook score, N = 2..8,
n <= N/2, three fake calibrations, density-matrix noise model with all X correlator sizes).
Larger N are spot checks with `benchmark_outputs/ex/sel.py`. Work queue: `ryon/ISSUES.md`.

| date (EDT) | commit | change | total N = 2..8 |
|---|---|---|---|
| 2026-10-24 | 0dc262c | baseline toby_sol | 16.615 |
| 2026-10-25 00:45 | a26041d | ladder + synthesised halves + start blocks | 17.199 |
| 2026-10-25 01:40 | ef0ec5d | whole-state pruned patches (7,3) (8,3) (8,4) (9,3) (9,4) | 17.435 |
| 2026-10-25 02:00 | f1f5bba | readout-bias-aware W trees | 17.458 |
| 2026-10-25 02:30 | (this) | pruned line circuits (7,3) (8,3) (9,3) (10,4), patches (10,3) (11,3) | 17.473 |

Per case, whole-state pruned circuits vs the previous toby_sol (CZ, expected score):
(8,4) 43 -> 22 CZ, 0.675 -> 0.845; (9,4) 63 -> 36 CZ, 0.607 -> 0.734; (10,5) 85 -> 43 CZ,
0.470 -> 0.685; (10,4) 77 -> 54 CZ, 0.546 -> 0.634; (10,3) 59 -> 39 CZ, 0.676 -> 0.785;
(11,3) 68 -> 44 CZ, 0.633 -> 0.763; (9,3) 44 -> 36 CZ, 0.724 -> 0.803; (7,3) 26 -> 20 CZ, 0.840 -> 0.903.
Bonus (moments, N <= 15) also rises with these tables: 38.30 -> 39.60.


## Bonus checkpoint — 2026-10-25 01:33 EDT

Best verified corrected 56-case bonus score: **46.1786336531**.
The standalone constructor passed complex128 state/relative-phase checks, native
gate and Willow connectivity checks for every case. Maximum construction time
was **0.002769 s**, maximum state L2 error
**6e-07**, and maximum emitted depth **126 moments**.
The 45-point milestone is passed; research continues beyond it.

[Standalone candidate](research/bonus_band_20261025/milestones/20261025T053345Z/submission.py),
[full validation](research/bonus_band_20261025/milestones/20261025T053345Z/validation.json), and
[checkpoint summary](research/bonus_band_20261025/milestones/20261025T053345Z/summary.json) are immutable copies.
The main entry point preserves a fresh shared-solver snapshot; a three-calibration
D(8,4) noise-model comparison was identical to that baseline, so this checkpoint
claims no additional primary-score gain.

Reusable W split decompositions are in
[w_broadcast.py](research/bonus_band_20261025/w_broadcast.py).
Follow-ups and ownership are in [the task board](research/bonus_portfolio_20261025/tasks.json)
and [the shared queue](ryon/ISSUES.md): calibrated W integration is assigned,
while terminal-decoder integration and adaptive oracle work remain available.
