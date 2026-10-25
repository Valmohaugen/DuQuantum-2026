# Thorough default workflow

User requests that python -u solution.py be the most thorough supported default,
with flags for focused experiments. Preserve the original challenge, recorded outputs,
user commit metadata and the optimized solver. No Git publication or attribution changes.

## Decisions

- Default preset becomes full: every nontrivial excitation count n=1–(N−1) for
  N=2–8, five seeds, 10,000 shots per basis and two detuning realizations. This is
  28 cases and 420 DD/no-DD/ideal records. Product boundaries are validated separately.
- Full preset scores all X-correlator orders through each case's N by default;
  an explicit --max-correlator-size still overrides this. Quick/standard retain cutoff 4.
- Unfocused full all-mode runs software checks and both notebooks by default, then
  selected validation, configured export, complete bonus-range export validation,
  noisy benchmark, analysis, diagnostics and implementation comparison.
- Bonus validation checks BOTH exported entry points for all 133 cases N=2–15,
  n=0–N: 266 independent exact/rule checks. Main uses chosen calibration; bonus uses
  its allowed full-device construction. Save JSON, CSV and Markdown coverage evidence.
- --preset quick/standard, --mode and explicit --cases/--nmax make focused runs;
  full software/bonus suites are opt-in there. --check/--no-check and
  --bonus-check/--no-bonus-check override automatic suite selection.
- Focused case runs use their selected sizes as default resource probes. Explicit
  --resource-sizes overrides this. Choose a balanced diagnostic case when available.
- Noise remains bounded to the existing default full N≤8 envelope (explicit cases
  can reach the existing N≤10 safety cap). Bonus checks use state vectors, not large
  density matrices. Matching source/model checkpoints resume; all new evidence is unique.

## Work and verification

- [x] Add failing parser, stage-plan, scoped suite and real configured-export coverage tests.
- [x] Resolve defaults/overrides, include notebook checks, implement partial
  bonus evidence and run it against the actual exported file.
- [x] Update README, run guide and working notebook mirror without changing the original.
- [x] Independent review, full no-flags execution, quality/artifact/figure/preservation checks.
- [x] Record measured default scope/runtime and completed status/continuity. No stage/commit/push.

First no-flags execution: benchmark_outputs/solution_runs/20261025T000413Z-7f900b5e/.
It passed 459 tests, both notebook checks, 28 selected-state checks, all 266 exported
main/bonus checks, the complete 420-record noisy benchmark, analysis and eight-view
diagnostics. The final comparison failed in optional minimal_dicke.py D(5,4): Cirq's
paired-swap router had no disjoint edge pair on the selected five-node star.
The original reference remains unchanged. The comparison now records optional reference
construction/validation errors and their full tracebacks, omits their scores and continues;
unexpected maintained-solver errors and shared noise/scoring failures remain fatal.
Two regression tests cover reference isolation and maintained-solver failure propagation.
The saved benchmark was reused without resampling. The second true no-flags execution
completed all eight stages with exit status 0 in 377.91 s:
benchmark_outputs/solution_runs/20261025T002251Z-5cda7439/.
It retained 168 comparison resource rows, 445 sampled comparison scores and the one
explicit optional reference error. All 266 exported circuits passed; 11 PNG and 10 PDF
figures, all report links and source hashes were verified before the presentation update.

The user's follow-up changes the matched DD/no-DD figure to a 0–2 view with explicit
overflow markers and numeric labels, adds a variant glossary and makes full resource
labels vertical. These changes were rendered from the immutable saved data without
rebuilding circuits or resampling. Current renderer snapshots and input hashes are in
benchmark_outputs/plot_updates/20261025T003757Z-score-view/presentation.json.
The full suite passed again after this update: 461 tests in 98.33 s; both notebooks execute.
Independent review is clear. See THOROUGH_DEFAULT_REVIEW.md and THOROUGH_DEFAULT_VERIFICATION.md.
