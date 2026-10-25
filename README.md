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

## Best results so far (primary score)

Local metric: `cd ryon && python fast_eval.py --seeds 0 1 2` (expected notebook score, N = 2..8,
n <= N/2, three fake calibrations, density-matrix noise model with all X correlator sizes).
Larger N are spot checks with `benchmark_outputs/ex/sel.py`. Work queue: `ryon/ISSUES.md`.

| date (EDT) | commit | change | total N = 2..8 |
|---|---|---|---|
| 2026-10-24 | 0dc262c | baseline toby_sol | 16.615 |
| 2026-10-25 00:45 | a26041d | ladder + synthesised halves + start blocks | 17.199 |
| 2026-10-25 01:40 | ef0ec5d | whole-state pruned patches (7,3) (8,3) (8,4) (9,3) (9,4) | 17.435 |
| 2026-10-25 02:00 | (next) | readout-bias-aware W trees | 17.458 |

Per case, whole-state pruned circuits vs the previous toby_sol (CZ, expected score):
(8,4) 43 -> 22 CZ, 0.675 -> 0.845; (9,4) 63 -> 36 CZ, 0.607 -> 0.734; (10,5) 85 -> 43 CZ,
0.470 -> 0.665; (10,3) 59 -> 39 CZ, 0.676 -> 0.775; (9,3) 44 -> 33 CZ, 0.724 -> 0.779.


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


## Bonus checkpoint — 2026-10-25 01:53 EDT

Best verified corrected 56-case bonus score: **46.5862094107**, up from
46.1786336531 after independently checking five peer W-state improvements.
All exported native/device/state checks passed; maximum constructor time was
**0.002403 s** and maximum state L2 error **6e-07**.
[Immutable candidate](research/bonus_band_20261025/milestones/20261025T055319Z/submission.py),
[validation](research/bonus_band_20261025/milestones/20261025T055319Z/validation.json), and [summary](research/bonus_band_20261025/milestones/20261025T055319Z/summary.json).

The calibrated-W pilot at N=8,10 gave mixed results and an adverse N=10 case,
so the main constructor is unchanged. [Pilot evidence](research/bonus_band_20261025/w_hardware_summary.json)
records both correlator cutoffs and Monte Carlo uncertainty. PORT-004 continues
with calibration-aware selection; PORT-005/006 cover terminal integration and
adaptive oracle work. Existing ownership is preserved.


## Continued research checkpoint — 2026-10-25

Best fully verified bonus remains **46.5862094107** across all 56 corrected
cases ([immutable validation](research/bonus_band_20261025/milestones/20261025T055319Z/validation.json)).
Research continues beyond the 45-point milestone. Two further calibrated W
pilots tested N=8,10 over six calibration seeds, including three held-out seeds.
The fixed-tree state-aware cost retained the baseline in every case; tree
placement changed four of twelve choices with mixed results. Neither pilot
justifies a main-constructor replacement. See the
[fixed-tree summary](research/bonus_band_20261025/w_cost_summary.json),
[placement summary](research/bonus_band_20261025/w_tree_summary.json), and
[reproduction manifest](research/bonus_band_20261025/w_experiment_manifest.json).
Reported Monte Carlo uncertainty excludes calibration and detuning uncertainty.

PORT-004 continues with output-probability sensitivity; PORT-005 tracks fresh
peer decoder/circuit integration. The [task board](research/bonus_portfolio_20261025/tasks.json)
preserves ownership and acceptance checks.


## Verified bonus checkpoint — 2026-10-25 02:31 EDT

Best corrected 56-case bonus score: **47.4261661947**,
up **0.8399567840** from 46.5862094107. Eleven native-depth
improvements came from fresh peer circuits and certified five-site terminal
decoders. All 56 standalone cases passed state, native-gate and Willow-connectivity
checks. Maximum constructor time was **0.002808 s**;
maximum state L2 error was **2.12e-07**.

[Standalone candidate](research/bonus_band_20261025/milestones/20261025T063113Z/submission.py),
[full validation](research/bonus_band_20261025/milestones/20261025T063113Z/validation.json),
[checkpoint summary](research/bonus_band_20261025/milestones/20261025T063113Z/summary.json), and
[integration evidence](research/bonus_terminal_integration_20261025/integration_results.json).
The main entry point is unchanged. The bounded integration left part of the
N=15 and asymmetric-split search for follow-up; research continues.


The follow-up first-order Z-output model passed an independent scaled-noise
derivative check. Its N=8,10 placement pilot on fresh calibration seeds 6..11
produced mean sampled score changes of **+0.02198** and **+0.02106**, respectively
(all X orders, six seeds each). Nine cases improved, one declined, and two kept
the baseline. This is promising simulation evidence; the main constructor
remains unchanged pending baseline-seed and robustness checks.
[Full pilot summary](research/bonus_band_20261025/w_z_summary.json),
[reproduction manifest](research/bonus_band_20261025/w_z_manifest.json).
PORT-009 is available to finish the bounded bonus integration's remaining
N=15/asymmetric coverage; PORT-008 is assigned to the resource-audit worker.


Original-seed confirmation (seeds 0..5) of the same Z-output selector also
improved mean sampled scores: **+0.01033 at N8** and **+0.01108 at N10**.
Across both studies (24 case/seed comparisons), 20 improved, one declined,
and three retained baseline. Main integration and coherent-noise robustness
remain follow-ups. [Confirmation evidence](research/bonus_band_20261025/w_z_baseline_summary.json).
The [symmetrization resource audit](research/bonus_symmetrization_audit_20261025/resource_audit.json)
found an optimistic 116-qubit lower bound for its direct N15 register layout,
before scratch space. This limits that implementation, not all Dicke circuits;
no native-depth improvement is claimed.


## Verified bonus checkpoint — 2026-10-25

Best corrected 56-case bonus score: **47.8780317427**, up **0.4518655480**
from the previous published 47.4261661947 checkpoint. Two completed integration
passes improved nine cases. All 31 valid groups in the defined balanced/adjacent
split worklist are covered; broader circuit searches remain open.
All standalone state/native/device checks pass. Maximum construction time:
**0.002442 s**; maximum state L2 error: **2.12e-07**.

[Standalone candidate](research/bonus_band_20261025/milestones/20261025T070208Z/submission.py),
[full validation](research/bonus_band_20261025/milestones/20261025T070208Z/validation.json),
[checkpoint summary](research/bonus_band_20261025/milestones/20261025T070208Z/summary.json).
The main entry point remains unchanged. The nominal W-selector gains were
sensitive to an explicitly assumed 100 kHz ZZ stress model; a coupling-aware
selector is being tested before any main-path promotion. This stress rate is
not a measured Willow calibration value.


## Verified bonus checkpoint — 2026-10-25

Best corrected 56-case bonus score: **48.0185710188**. Precision
certification of an existing fixed 26-CZ decoder improved five more k=4 cases,
adding **0.1405392761** points. Its supported coherent counts r=0..4
share one phase to 1.53e-15; no new gate topology was synthesized.
All 56 standalone native/device/state checks pass. Maximum construction time
is **0.002501 s**, and maximum state L2 error is **1.19e-07**.
[Standalone candidate](research/bonus_band_20261025/milestones/20261025T071120Z/submission.py),
[full validation](research/bonus_band_20261025/milestones/20261025T071120Z/validation.json),
[checkpoint summary](research/bonus_band_20261025/milestones/20261025T071120Z/summary.json),
[precision evidence](research/bonus_half_precision_20261025/precision_results.json).
The main entry point remains unchanged; hardware robustness research continues.


## Standalone hardware candidate — 2026-10-25

Bonus best remains **48.0185710188**. A separate
[combined candidate](research/bonus_band_20261025/hardware_submission.py)
preserves maintained main tables from commit761433b, all56 verified
bonus circuits, and adds a guarded W-tree selector for N8/N10 with defaultDD
and pack=False. It exactly matches the evaluated selector on18 calibration
cases; maximum measured construction time was **1.241 s**.
[Export verification](research/bonus_band_20261025/hardware_submission_verified.json)
includes native/state checks, fallback comparisons and exact bonus equality.

The selector had positive mean sampled score changes under nominal, coherent
and assumed uniform100kHz ZZ models in both cohorts. These are simulated
results, not hardware measurements; see the
[confirmation](research/bonus_band_20261025/w_zz_confirmation_summary.json).
The maintained solver is unchanged. A held-out coupler-dependent signed-ZZ study found mean changes of
**+0.02409** (N8) and **-0.01438** (N10), including a substantial N10
regression. This selector is **not promoted**; the standalone export is
research evidence, not a recommended hardware replacement.
[Signed-ZZ results](research/bonus_band_20261025/w_heterogeneous_summary.json)
include both conditional Monte Carlo and calibration uncertainty. A further399 bonus comparisons found no improvement;
[coverage](research/bonus_half_completion_20261025/handoff_summary.json)
records unfinished groups so other agents can continue without repeating work.


## Verified bonus checkpoint — 2026-10-25

Best corrected 56-case bonus score: **48.4141358975**. A freshly
verified peer D(11,5) circuit reduces native depth from **71 to 47 moments**
(56 CZ), adding **0.3955648786** points. All 56 standalone state,
native-gate and device checks pass; maximum constructor time is
**0.002553 s**, maximum state L2 error **1.49e-07**.
[Standalone candidate](research/bonus_band_20261025/milestones/20261025T074513Z/submission.py),
[full validation](research/bonus_band_20261025/milestones/20261025T074513Z/validation.json), and
[checkpoint summary](research/bonus_band_20261025/milestones/20261025T074513Z/summary.json) are frozen copies.
The native main entry point is unchanged; the separate experimental W selector
is still unpromoted after its signed-coupling regression. Research continues.


## Verified bonus checkpoint — 2026-10-25

Best corrected 56-case bonus score: **48.5197258860**. Native depths
improved for D(13,3), **62 → 59**; D(14,3), **65 → 59**; and D(15,3),
**76 → 75**, adding **0.1055899886** points. The first uses a newly
precision-certified six-site decoder; the other two reuse an existing certified
seven-site decoder in newly checked combinations. All 56 state/native/device
checks pass. Maximum constructor time: **0.002485 s**;
maximum state L2 error: **1.49e-07**.
[Standalone bonus candidate](research/bonus_band_20261025/milestones/20261025T082016Z/submission.py),
[validation](research/bonus_band_20261025/milestones/20261025T082016Z/validation.json), and
[summary](research/bonus_band_20261025/milestones/20261025T082016Z/summary.json) are frozen copies.
The native main prefix is unchanged. Research continues beyond this checkpoint.


## Verified bonus checkpoint — 2026-10-25

Best corrected 56-case bonus score: **48.9368744609**, up
**0.5227385635** from the previous published best.
This combines four fresh peer circuits with a faithful seven-site decoder;
D(13,3) now uses **57 moments**, and D(15,3) uses **71**. All 56 standalone
state/native/device checks pass. Maximum construction time: **0.002592 s**;
maximum state L2 error: **1.49e-07**.
[Standalone bonus candidate](research/bonus_band_20261025/milestones/20261025T082924Z/submission.py),
[validation](research/bonus_band_20261025/milestones/20261025T082924Z/validation.json), and
[summary](research/bonus_band_20261025/milestones/20261025T082924Z/summary.json) are immutable copies.

A separate [combined research candidate](research/bonus_band_20261025/edge_hardware_submission.py)
uses maintained main tables from commit0dc1b2c, this bonus cache, and the
fixed-pattern W selector for N8/N10. Its24 calibrated outputs match the evaluated
selector; maximum measured main construction time was **1.440 s**.
[Export verification](research/bonus_band_20261025/edge_hardware_verified.json)
records exact bonus equality and unchanged-main checks across the cache refresh.
Across12 calibration seeds per size, pooled score changes are positive under
all four assumed models. However, N10 uniform-ZZ was negative in the confirmation
cohort alone, and individual regressions remain. These are **simulated results**,
not measured hardware gains; the maintained solver is unchanged.
[Full results and uncertainty](research/bonus_band_20261025/w_edge_confirmation_summary.json).

The [compiler audit](research/bonus_matched_half_precision_20261025/faithful_native_results.json)
keeps the accurate53-moment decoder; the inaccurate52-moment conversion is excluded.
The [symmetry audit](research/bonus_spinflip_audit_20261025/audit_results.json)
rules out one restricted decoder family and records the limits of its proposed extension.
Research and ticket handoffs continue.


## Research checkpoint — density ranking and decoder screening

Best verified corrected bonus remains **48.9368744609**; the immutable
[56-case checkpoint](research/bonus_band_20261025/milestones/20261025T082924Z/summary.json)
is unchanged. A new direct density-matrix W reranker completed eight fresh
calibration cases (seeds 33–36, N8/N10), four assumed evaluation models, and
both X-score cutoffs. Maximum constructor time was **35.14 s**; all tested
outputs passed exact-state, native-gate and device checks.

The reranker is **not promoted**: its N10 outputs equal the prior selector,
and its only changed N8 choice loses under all four evaluation models.
[Results and uncertainty](research/bonus_band_20261025/w_density_summary.json)
include comparisons with both the maintained baseline and prior selector.
These are simulated results, not measured hardware gains.

A [finite-size counter screen](research/bonus_band_20261025/counter_literal_screen.json)
finds that a literal implementation of a recent low-workspace counter is too
costly for the current small instances; this is not a lower bound on other
implementations. Decoder research continues with fixed Clifford blocks and
a transformation specialized to unary inputs. Tickets PORT024 and PORT025
track the remaining reachability, phase, routing and interface checks.

The new [unary-input transformation](research/bonus_band_20261025/folded_unary_native_verified.json)
uses **24 CZ gates and 19 native moments** on a checked Willow footprint. All
eight supported input columns share one phase, with error below6.1e-16. This
is a reusable component, **not a complete Dicke decoder**: its upstream
layout and a symmetric decoder core remain open. The
[agent handoff](research/bonus_clifford_screen_20261025/handoff_summary.json)
also records the fixed-Clifford algebra and adaptive-branch checks.


## Research checkpoint — smaller folded input and paired-core objective

Best verified corrected bonus remains **48.9368744609**; the
[56-case checkpoint](research/bonus_band_20261025/milestones/20261025T082924Z/summary.json)
is unchanged. A direct folded input for D(14,7) now has two verified options:
**37 CZ / 31 moments** and **42 CZ / 26 moments**, reduced from68CZ/96moments.
The bounded affine search checked745 encoders using known-zero inputs. Both
selected circuits pass full14-qubit state, native-gate and Willow checks.
[Independent checks](research/bonus_band_20261025/affine_encoder_independent_check.json)
and [handoff](research/bonus_affine_encoder_20261025/handoff_summary.json).

These circuits prepare the **folded input, not a Dicke state**; two decoder
cores remain necessary. Small symmetry-constrained core fits produced an exact
three-qubit example but no useful five-qubit result. Forty bounded core/sign
fits are recorded, including failures, in the
[core study](research/bonus_symmetric_core_20261025/handoff_summary.json).

The next [paired-core objective](research/bonus_symmetric_core_20261025/paired_core_checks.json)
evaluates the actual balanced-state overlap using two smaller simulations.
It agrees with direct full-state calculations at6,10,14qubits and passes
derivative checks; no fit or score gain is claimed yet. PORT029 is assigned.
The readout audit also corrects the adaptive sketch: the local checker requires
complete **device** diagonals, not just used-qubit groups. All published
unitary components are unaffected.


## Bonus checkpoint — 2026-10-25 06:10 EDT

Best independently verified corrected bonus: **49.1115192815**,
up **0.1746448206** from the previous published checkpoint. All 56 cases
pass state, native-gate, Willow connectivity and constructor-time checks.
Maximum build time is **0.002296s**, maximum state L2 error
**1.49e-07**, and maximum depth **119 moments**.

| Case | Previous moments | New moments |
| --- | ---: | ---: |
| D(5,2) |14|13|
| D(7,2) |17|16|
| D(13,3) |57|55|
| D(14,3) |59|57|
| D(15,3) |71|69|

[Standalone candidate](research/bonus_band_20261025/milestones/20261025T101047Z/submission.py),
[validation](research/bonus_band_20261025/milestones/20261025T101047Z/validation.json), and
[immutable summary](research/bonus_band_20261025/milestones/20261025T101047Z/summary.json).
SHA-256: `5b91bb1bf7ad046aed8ff63399e233e36d12aee45de5e683013ca3b6884ef576`.
The main constructor is unchanged. The separate experimental hardware candidate
also carries the new bonus cache; its main path is unchanged and this checkpoint
claims no new measured or modeled hardware gain.

The repaired seven-site decoder retains51 moments / 30 CZ and passes all four
supported columns with one phase to 1.17e-15.
[Peer refresh](research/bonus_peer_refresh_20261025/handoff_summary.json) and
[precision/integration handoff](research/bonus_peer7_precision_20261025/handoff_summary.json)
include source hashes and complete bounded-search coverage.

The [paired-core pilot](research/bonus_paired_core_20261025/handoff_summary.json)
verified an exact logical 10-qubit starting point; none of ten bounded gate
deletions passed. No routed-circuit or bonus gain is claimed from that pilot.
[Further literature screening](research/bonus_band_20261025/literature_followup_best10.json)
and the [task board](research/bonus_portfolio_20261025/tasks.json) track continued work.
