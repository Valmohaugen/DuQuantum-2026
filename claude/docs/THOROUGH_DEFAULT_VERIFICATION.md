# Thorough default and score display verification — October 24, 2026

`python -u solution.py` now selects the full supported workflow without flags.
It benchmarks every nontrivial N=2–8 case, including complementary excitations,
with five seeds, 10,000 shots per basis, two detuning realizations and all applicable
X-correlator orders. Both actual exported entry points are validated exactly for
all 133 N=2–15, n=0–N cases, including product boundaries: 266 circuits.
Software checks and both notebook executions run before scientific stages.
Quick/standard presets, explicit cases/ranges and narrow modes remain available;
`--check`, `--no-check`, `--bonus-check` and `--no-bonus-check` override automatic suites.

## Evidence

| Check | Verified result |
| --- | --- |
| Actual no-flags invocation | Exit 0; all eight stages complete in 377.91 s, using the existing matching benchmark cache |
| Full scientific scope | 28 selected-state checks; 266 exported main/bonus checks; minimum export fidelity 0.9999999999999638 |
| Raw benchmark | All 420 records complete and finite; same SHA-256 before and after resume and plotting |
| Implementation comparison | 168 resource rows; 84 maintained rows valid; 445 sampled scores; one explicit optional reference error |
| Full-run saved figures | 11 PNG / 10 PDF under figs/solution_runs/20261025T002251Z-5cda7439/; all decode/header checks pass |
| Report integrity | 36 local links verified; recorded source hashes matched the execution sources before the later presentation-only update |
| Complete suite after presentation update | 461 passed in 98.33 s |
| Final hooks | Lint, format, output stripping and artifact contracts passed; pytest hook skipped because the full suite was run separately immediately before them |
| Targeted renderer/reference checks | 14 passed before the final full suite; singleton and nonfinite plotting paths remain supported |
| Working notebooks | solution: 6 code cells; tutorial: 19 code cells; executed in memory with temporary artifacts |
| Preservation | All 1,239 pre-existing saved artifacts/original notebook files byte-identical; all four ryon files match upstream d8f148d |

The independent review is in [THOROUGH_DEFAULT_REVIEW.md](THOROUGH_DEFAULT_REVIEW.md).
The first full attempt remains preserved at
benchmark_outputs/solution_runs/20261025T000413Z-7f900b5e/. It completed the benchmark
and diagnostics but exposed an optional reference routing failure in minimal_dicke.py
for D(5,4): its selected five-node star has no disjoint swap-edge pair for Cirq's
paired-swap strategy. The reference remains verbatim. Its failure is now recorded with
a full traceback and receives no score; unexpected maintained-constructor/validation
or shared noise/scoring failures remain fatal. Explicit unsupported requests retain
their distinct status. The constructor-only D(90,45) probe reports a bounded-search
failure rather than claiming that no physical layout exists.

## Presentation follow-up

The matched DD/no-DD panel displays 0–2. Boundary triangles indicate clipped means
or standard-deviation endpoints; overflowing means retain numeric labels. The first
DD and no-DD means are both 9.106756569643276 and display as 9.11. The plot's underlying
bar heights remain uncapped, the report retains full statistics, and the difference
panel keeps its own scale. The official reciprocal score is not bounded by 2.

Comparison reports now contain the implementation/DD glossary. Full resource figures
use vertical labels to keep all 28 cases legible. The corrected presentation was
rendered from the completed run's immutable data without new circuits or samples.
Its presentation.json records both input hashes and current renderer source hashes;
renderer snapshots are saved alongside it. Original figures and reports remain intact.

## Saved results

- [Complete no-flags run and all stage links](../../benchmark_outputs/solution_runs/20261025T002251Z-5cda7439/report.md).
- [Full-run artifact verification](../../benchmark_outputs/solution_runs/20261025T002251Z-5cda7439/verification.json).
- [Corrected score view, readable resource figure and variant guide](../../benchmark_outputs/plot_updates/20261025T003757Z-score-view/report.md).
- [Presentation input hashes and renderer snapshots](../../benchmark_outputs/plot_updates/20261025T003757Z-score-view/presentation.json).
- [Run and flag guide](RUN_GUIDE.md).

All scientific images remain under figs/. Original challenge SHA-256 remains
ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1.
The missing historical 240 records were not reconstructed. No hardware calls, staging,
commits, remote writes or attribution metadata changes were performed.
