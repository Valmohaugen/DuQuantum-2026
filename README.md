# DuQuantum 2026 — Dicke-state preparation

Prepare exact weight-n Dicke states on calibrated Willow qubits using CZ and
`cirq.PhasedXZGate`. Hardware judging compares Z distributions and X correlators.
The bonus rewards depth and permits the current non-adaptive construction.
The organizer confirmed bonus grading for **2 ≤ N ≤ 15** and corrected the original
validator to use `range(len(qubits))`. Hidden grading cases and correlator sizes remain
undisclosed. The original challenge notebook stays unchanged and supplies the official scorer.

## Harmonic objective and paired evaluations — 2026-10-25

The reported new primary objective, `1 / mean(1 / score)`, is the **harmonic
mean**. Since each notebook score is `1 / (Z_penalty + X_penalty)`, pooling
individual scores this way is exactly equivalent to minimizing their mean
total penalty. Weak cases matter more than under the previous arithmetic
score sum: the marginal benefit of improving score s scales as `1 / s²`.
The depth bonus remains a separate objective; its historical totals below
have not been reinterpreted as primary harmonic scores.

The offline ranking is now recovered from `~/dat.txt`: see the
[archived chart](research/chart_comparison_20261025/chart.txt). Its early
`solution` entry places 4/5. Its displayed primary totals match the **sum**
of three per-case means (for example, Tanish: 0.3900 + 0.4328 + 0.5088 =
1.3316), not the harmonic mean. A revised harmonic rule therefore still needs
independent confirmation. This chart does not establish the rank of the
current exports. The averaging order also needs
confirmation: pooling individual observations differs from first averaging
scores within a case. The evaluator records **both** interpretations.

[evaluate_candidates.py](claude/scripts/evaluate_candidates.py) compares
constructors on matching synthetic calibration seeds, shots, cases and seeded
detuning draws. It checks native gates, Willow connectivity and exact noiseless
state fidelity before simulation. Finite-shot Z-sector counts and X Hamming-weight
counts reproduce the notebook penalties, including X sampling variance; tests
compare these compressed statistics directly with the notebook helper copy.
The older `fast_eval` reciprocal-mean-penalty proxy is reported separately.
Undefined draws fail explicitly rather than disappearing from the aggregate.

The full paired run covers **16 cases** (`2 <= N <= 8`, `1 <= n <= N//2`),
calibration seeds 0–2, four detuning realizations at 7.5 kHz, and 256 independent
finite-shot repeats of 10,000 shots per basis for each frozen distribution.
All **288 evaluated circuits** pass state/native/device checks; minimum
complex128 fidelity is 0.9999999999999978.

| Candidate | Pooled harmonic score | Harmonic of case mean scores | Mean moments | Maximum moments | Mean CZ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current peer (`ryon/toby_sol.py`) | **1.053658** | **1.426576** | 14.08 | 25 | 12.75 |
| Latest native standalone export | 1.045147 | 1.412098 | 15.21 | 29 | 12.60 |
| Simple: maintained optimized constructor, DD off | 0.976381 | 1.286525 | 27.92 | 81 | 19.06 |
| Simple plus EARLIEST packing | 0.966408 | 1.281143 | 27.77 | 81 | 19.06 |
| Maintained constructor, sparse DD | 0.956589 | 1.257639 | 27.92 | 81 | 19.06 |
| Maintained constructor, default dense DD | 0.946067 | 1.243806 | 27.92 | 81 | 19.06 |

[Full results and settings](research/harmonic_eval_20261025/full/results.json)
and [compact table](research/harmonic_eval_20261025/full/summary.md) retain
per-case/per-seed scores, source hashes, circuits and noisy distributions.
The sampled harmonic objective ranks the peer **11.37%** above the maintained
dense-DD constructor; turning off dense DD gains **3.20%** in this run.
These comparisons have the same direction at each calibration seed. Three
calibrations are a small sample, not a hardware-wide confidence claim.

The separate [four-case screen](research/harmonic_eval_20261025/screen/summary.md)
also compares the older analytic construction and the roughly 40-line
`ryon/minimal_dicke.py` reference. Their pooled harmonic scores are 0.902035
and 0.313181, respectively, versus 0.934793 for the optimized simple variant.
That screen uses two detuning realizations, so compare scores **within** a run.
The minimal reference reaches 558–601 moments at D(8,4), whereas the current
peer uses 21 moments and the maintained constructor uses 81. Small source
code alone does not imply a shallow native circuit. The peer's fitted weights
and synthesis tables have substantial measured value and should be retained.

The newer candidate has already resolved much of the early depth problem:
D(6,3) is 15 moments versus 43 in the maintained constructor; D(8,4) is 21
versus 81. Generic extra packing saved little depth and reduced the full-run
score, so it is not promoted. Disabling DD globally is also not established:
on held-out calibration 5, DD improves the peer's D(4,2) layout. Separate
[DD-off](research/harmonic_eval_20261025/peer_no_dd.py) and
[packing](research/harmonic_eval_20261025/peer_packed.py) ablations preserve
the peer's weights and stay outside the maintained solver.

Held-out seeds **3–5**, on D(4,2), D(6,3) and D(8,4), confirm that the newer
peer remains preferable under the tested stronger-detuning assumption:

| Candidate | Harmonic, 7.5 kHz | Harmonic, assumed 30 kHz stress |
| --- | ---: | ---: |
| Current peer | **0.958260** | **0.961275** |
| Peer, DD off | 0.955567 | 0.956838 |
| Peer, depth-oriented packing | 0.956498 | 0.954529 |
| Simple maintained constructor, DD off | 0.809445 | 0.775959 |
| Maintained dense-DD constructor | 0.762427 | 0.759515 |

[Nominal confirmation](research/harmonic_eval_20261025/heldout_nominal/results.json)
and [detuning stress results](research/harmonic_eval_20261025/heldout_detuning30/results.json)
record another **90** passing state/native/device evaluations. The small
differences among peer variants do not establish a reliable improvement;
even their near-tie ordering changes when averaging scores within cases first.
The slight increase in the peer's stressed aggregate is finite sampling/model
variation, not evidence that extra detuning helps. Across the screen, full
comparison and confirmations, **462 circuits** were evaluated. No selector,
packing tweak or global DD removal is promoted into the maintained constructors
or current exports on this evidence. Retain the newer shallow circuits and
use the harmonic evaluator to gate further changes.

Run a focused comparison with the project environment:

```bash
python -m claude.scripts.evaluate_candidates \
  --cases 2,1 4,2 6,3 8,4 --seeds 0 1 2 \
  --variants simple analytic current sparse packed \
  --candidate peer=ryon/toby_sol.py \
  --candidate standalone=research/bonus_band_20261025/native_submission.py \
  --candidate minimal=ryon/minimal_dicke.py \
  --output research/my_harmonic_comparison
```

Candidate paths can point to frozen or tweaked implementations exposing
`create_dicke_state`. Use a fresh output directory; completed results are
never overwritten. This session used isolated Python 3.11.5/Cirq 1.6.1 with
the explicit `--willow-fallback` device alias because the documented project
environment was unavailable. [Runtime versions](research/harmonic_eval_20261025/runtime.txt)
are recorded; these are local modeled comparisons, not a locked-runtime
certification or hardware leaderboard reproduction. The existing model omits
leakage, coherent errors, ZZ crosstalk and drift, and these runs do not cover
N=9–15 or undisclosed hardware grading cases.

## Recovered chart cases and current depths — 2026-10-25

The actual chart cases are **(10,3), (10,5), (15,4)**. Its final pair is
therefore D(15,4), rather than D(8,4) or D(15,7). A fresh constructor-only
comparison using `judge.fake_calibration(0)` gives:

| Constructor | D(10,3) moments | D(10,5) moments | D(15,4) moments | Mean moments |
| --- | ---: | ---: | ---: | ---: |
| Old `solution`, chart | 106 | 134 | 215 | 151.67 |
| Newest peer (`ryon/toby_sol.py`) | **37** | **33** | **118** | **62.67** |
| Current native standalone, main entry point | 55 | 73 | 118 | 82.00 |
| Simple maintained constructor, DD off | 91 | 123 | 193 | 135.67 |

The reported old depth of **152** is the rounded mean, `(106+134+215)/3`,
not the depth of a single case. Compare that mean with 62.67 for the newest
peer or 82.00 for the current standalone, under the synthetic calibration used here.

All newly constructed circuits pass native/device checks and complex128
noiseless state checks. These are primary-constructor depths, not bonus-cache
depths. The newest peer reduces the final pair's depth by **45.1%** relative
to the chart, with **147 CZ gates**. The frozen standalone's main path trails
the newest peer on the two N=10 cases, despite its up-to-date bonus cache.
The calibration is synthetic: these measurements do not establish the exact
depth selected under the chart's unavailable calibration.

The supplied old source is cut off mid-angle-table and literally ends with
`... (32 KB left)`. The initial
[partial recovery](research/chart_comparison_20261025/old_solution_partial.py)
preserves complete required tables through N=11 and rejects larger requests.
It reproduces **106 and 134 moments** on the two N=10 cases.
The [complete old source](research/chart_comparison_20261025/old_solution_recovered.py)
was subsequently recovered from commit `6b0b1a6`: its complete supplied prefix
matches byte for byte, including all 24 functions and the visible angle tables.
It reproduces **215 moments and 166 CZ gates** for D(15,4), with exact noiseless
state fidelity. [Full recovery evidence](research/chart_comparison_20261025/full_recovery.json),
[initial recovery provenance](research/chart_comparison_20261025/provenance.json)
and [resource results](research/chart_comparison_20261025/resources.json) retain
the original file hash and the measured evidence.

The chart and code contain no fixed calibration maps or judging noise
configuration. The original notebook does provide a synthetic calibration
recipe and specifies 10,000 shots in each basis and a sum of case scores.
The previous small-case evaluations already used that recipe through
`judge.fake_calibration`; the chart-specific simulations below extract its
functions directly. Exact chart reproduction still requires its particular
calibration realization, noise model and X-correlator cutoff. No synthetic
noisy score is presented as an exact reproduction of the chart.

## Notebook-based noisy simulation of the chart cases

[evaluate_chart_noise.py](claude/scripts/evaluate_chart_noise.py) directly loads
the unchanged original notebook's calibration functions (cells 11–12). Its
error-rate medians are 0.0004 for single-qubit gates, 0.0025 for CZ gates,
0.005 for 0→1 readout and 0.01 for 1→0 readout; lognormal spread is 0.5,
with 1% qubit and coupler dropout. Each seed saves its generated maps,
including the notebook's uncertainty fields. These uncertainty fields are
measurement uncertainties, not extra per-shot error probabilities.

The simulation applies a stochastic Pauli channel with the calibrated error
probability after each gate, including the X measurement basis rotation,
then applies the asymmetric readout errors. The notebook does not specify
idle decay, detuning, leakage or coherent noise channels, so this minimal
model adds none. Thus depth reductions alone do not imply proportional
score gains in this model. The gate/readout model differs from the earlier
timed T1/T2/detuning model; their absolute scores should not be compared.

The CPU qsim trajectory simulator generates **10,000 actual noisy shots per
basis**, including N=15, without constructing an exponentially larger density
matrix. This avoids plugging a small trajectory average into a nonlinear
score. The exact notebook score is calculated from sufficient count statistics
for X cutoffs 2, 4 and N; the notebook leaves that argument unspecified.
Tests verify the calibration recipe, compare the score with the notebook
helper copy at multiple cutoffs and compare qsim with an exact density result
on a small noisy circuit. qsim is only an evaluation dependency and is not
imported by submitted constructors.

Example for a fresh seed/run directory (qsim is additionally required):

```bash
python -m claude.scripts.evaluate_chart_noise --seed 0 \
  --output research/my_chart_noise_seed0
```

Pass `--variants peer standalone simple old` and `--cases 10,3 10,5 15,4`
to select constructors/cases. The default uses all of them. Each process uses
one CPU thread by default. Archived calibration seeds 0–2, sampled measurements,
circuits and runtime versions are in [the chart-noise evidence](research/chart_noise_20261025/).

Results using **all X-correlator orders**, with mean ± SE across the three
calibration/shot seeds:

| Constructor | D(10,3) score | D(10,5) score | D(15,4) score | Sum |
| --- | ---: | ---: | ---: | ---: |
| Recovered old submission | 0.8237 ± 0.1074 | 0.5897 ± 0.0119 | 0.5243 ± 0.0055 | 1.9377 ± 0.1133 |
| Simple maintained constructor, DD off | 1.0271 ± 0.0440 | 0.5891 ± 0.0185 | 0.5812 ± 0.0039 | **2.1974 ± 0.0639** |
| Frozen standalone | 0.7297 ± 0.0231 | 0.6741 ± 0.0271 | 0.5525 ± 0.0163 | 1.9563 ± 0.0228 |
| Newest peer | 0.8497 ± 0.0820 | 0.7488 ± 0.0074 | 0.5525 ± 0.0163 | **2.1509 ± 0.0851** |

There are 36 case/seed/constructor evaluations, with three identical N=15
peer/standalone circuits reusing their measurements: **33 distinct sampled
contexts and 660,000 noisy shots**. Every circuit passes exact noiseless and
native/device checks. Full [statistics](research/chart_noise_20261025/summary.json),
[table](research/chart_noise_20261025/summary.md) and
[reproduction script](research/chart_noise_20261025/summarize.py) are saved.
The simple constructor has the highest arithmetic total in this small run;
the peer has the highest pooled harmonic score (**0.6896**, versus **0.6820**
for simple, 0.6418 for standalone and 0.6171 for old). This is not sufficient
evidence for a constructor promotion. The peer-minus-old paired sum change is
**+0.2132 ± 0.1936 SE**; one of the three calibration seeds regresses.
These SEs include calibration and finite-shot variation across three seeds,
not uncertainty in the hardware noise model or calibration uncertainty fields.

The unspecified X cutoff materially changes the arithmetic totals:

| Constructor | Cutoff 2 | Cutoff 4 | All orders |
| --- | ---: | ---: | ---: |
| Recovered old | 2.2947 | 2.2008 | 1.9377 |
| Simple | 2.5313 | 2.4396 | 2.1974 |
| Standalone | 2.3077 | 2.2219 | 1.9563 |
| Newest peer | 2.3789 | 2.3194 | 2.1509 |

The old submission's simulated total **1.9377** differs substantially from
the chart's **1.1190**. For the final pair, old simulation gives **0.5243**
versus chart **0.3919**. Consequently, **2.1509 is a conditional local model
estimate, not a prediction of the official score**. The notebook's recipe
allows simulation, but its random rates and a Pauli/readout model cannot
recover an unknown calibration realization or unmodeled judging noise.

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
| 2026-10-25 09:45 | 51.4051 | 56 | [toby/bonus_squeeze_sol.py](toby/bonus_squeeze_sol.py): native_submission.py (51.3337) plus a z-ejection / realignment pass; (13,3) 55 -> 54, (14,3) 57 -> 55, (15,3) 67 -> 64 moments | all 56 pass Willow105.validate_circuit and judge.test_circuit, max build 2.6 s |

Reusable tasks and their acceptance criteria are recorded in
[the shared issue queue](ryon/ISSUES.md) and
[the bonus task board](research/bonus_portfolio_20261025/tasks.json).

## Best results so far (primary score)

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

Source note: the start blocks in the a26041d row were ported from `toby/halves_start_sol.py` (0d47ab3).

## Revised judging metric: 1 / mean(Z + X)

Judging now takes the harmonic mean of the per-case scores, 1 / mean over cases of (Z + X),
instead of the sum of 1 / (Z + X). Every case's penalty counts equally, so the worst cases
(large N, n near N/2) matter most and the small-N lottery no longer helps. `ryon/fast_eval.py`
now prints this metric under its total. Scripts, raw rows and the summary are in
[research/new_metric_20261025](research/new_metric_20261025/summary.txt). The noise model is
fast_eval's, with all X correlator sizes and three fake calibrations (seed 0 only for N = 11, 12).

| date (EDT) | commit | solution | 1/mean(Z+X) N = 2..8 | N = 2..10 | N = 2..12 (seed 0) | mean moments N = 2..8 |
|---|---|---|---|---|---|---|
| 2026-10-25 09:10 | de2d0d0 | ryon/toby_sol.py (main entry point) | 1.050 | 0.959 | 0.805 | 14.1 |
| 2026-10-25 09:10 | 105326Z | bonus milestone 51.04, `create_dicke_state_adaptive` (bonus_sub_105326Z.py) | 0.951 | 0.872 | 0.715 | 12.0 |

The bonus build is about 15 % shallower, but its penalty is 5 to 25 % higher than main's in all
36 cases (N = 2..12). It places circuits without calibration data, and the packed 1q gates
raise Z bias (zb 0.05 to 0.13 against 0.01 to 0.02). Depth does cost score: zeroing the
selector's idle term (`idle_err = 0`) gives 15.9 moments and 1.045 instead of 14.1 and 1.050.
The extra main-entry moments are 25 ns single-qubit layers. The current depth weighting is
already at the optimum: `idle_err` 1e-3 and 3e-3, `idle_penalty` 3e-3, `prefer_synth = False` and no DD
all land within 0.001 of main. Packing 1q gates into CZ moments (`pack=True`) scores lower (1.036).
Bonus metric (sum N n / moments, N = 2..15) is unchanged: milestone 105326Z 51.04, toby_sol
`create_dicke_state_adaptive` 44.00.

Larger N (trajectories, seed 0, Z floor + X; [summary_largeN.txt](research/new_metric_20261025/summary_largeN.txt)):
main / bonus build 0.581 / 0.526 for N = 2..15, 0.520 / 0.456 for N = 2..16, 0.420 / 0.360 for N = 2..18.
Penalties of 4 to 6 at N >= 14, n near N/2 dominate the mean. A 300-trajectory, 2-seed head-to-head over
10 cases at N = 14..16 ([rows_traj300.jsonl](research/new_metric_20261025/rows_traj300.jsonl)) has main ahead or tied in every case.
The bonus build's apparent N = 15 wins at 80 trajectories were noise.

Part 2 (bonus): the same searches gave 15 circuits shallower than the bonus portfolio (+2.2 points vs milestone
101047Z); most are now merged (milestone 105326Z, 51.04). Remaining 4 are in research/primary_depth_20261025 (ISSUES 14).

Readout-only ceiling for the same placements (gate and idle noise switched off): 18.474 for N = 2..8,
so roughly 1.0 is still recoverable at small N; the theoretical maximum (no noise at all) is 19.18.

Per case, whole-state pruned circuits vs the previous toby_sol (CZ, expected score):
(8,4) 43 -> 22 CZ, 0.675 -> 0.845; (9,4) 63 -> 37 CZ, 0.607 -> 0.784; (10,5) 85 -> 43 CZ,
0.470 -> 0.728; (10,4) 77 -> 45 CZ, 0.546 -> 0.724; (10,3) 59 -> 39 CZ, 0.676 -> 0.785;
(11,3) 68 -> 44 CZ, 0.633 -> 0.763; (9,3) 44 -> 36 CZ, 0.724 -> 0.803; (7,3) 26 -> 20 CZ, 0.840 -> 0.903.
Bonus (moments, N <= 15) also rises with these tables: 38.30 -> 39.60.
N >= 11: (11,5) 104 -> 59 CZ (89 -> 53 moments, fast_eval 1 seed 0.417 -> 0.596), (12,3) 77 -> 51 CZ (0.611 -> 0.724, 1 seed),
(12,4) 105 -> 96, (13,4) 119 -> 112, (15,3) 91 -> 68. Robust under coherent CZ errors and ZZ crosstalk
(toby's trajectory check, ISSUES #10).


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
