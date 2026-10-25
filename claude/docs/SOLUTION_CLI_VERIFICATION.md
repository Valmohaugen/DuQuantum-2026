# Unified solution CLI — final verification, October 24, 2026

The user requested a single command through solution.py, with flags for experiments.
The complete workflow is implemented in claude/scripts/run_solution.py; solution.py and
the synchronized working notebook remain thin consumers of tested Python modules.

## Behavior verified

- Default mode runs validation, paired DD/no-DD/ideal benchmark, analysis, eight-view
  diagnostics, shared-model solution comparison and a configured standalone export.
- Quick/standard/full presets and explicit case, seed, noise, sampling, preparation and
  resource controls resolve before output directories are created. Invalid settings fail
  through argparse. Help and plan do not start experiments or create output directories.
- Every actual invocation saves a unique report/index/log/manifest. Source/model-matched
  raw checkpoints can resume; fresh repeats and changed settings preserve prior runs.
- All figures use figs/solution_runs/<run-id>/; numeric data and reports use the selected
  output root. Reports contain valid links to saved files. Missing score data is explicit.
- Noise, calibration and preparation settings reach every applicable stage. Existing-data
  diagnostics resolve the recorded model into the plan, manifest and terminal setup as
  well as into the actual diagnostic code. Explicit model overrides of existing data are
  rejected. An explicit illustrative seed is supported without altering saved observations.
- Export embeds selected preparation defaults before constructor definitions bind their
  default arguments. Noise/shot settings remain local test settings. The standalone
  exporter without an explicit configuration remains byte-identical to canonical source.
- Failed stages retain a failed manifest, partial output paths and full traceback/log.
  Temporary benchmark settings and figure environment are restored after success/failure.
- The original challenge notebook remains byte-identical with SHA-256
  ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1.
  The four ryon reference files remain unchanged. No Git write or hardware call occurred.

## Commands and results

All commands used the project environment, private temporary Matplotlib/cache directories
and one OpenBLAS thread. Verification outputs went to isolated temporary directories,
except the explicitly recorded new demonstration runs below.

| Check | Result |
| --- | --- |
| Initial CLI regressions before implementation | 9 expected failures because the runner did not exist |
| Configured-export regression | Failed on dense default before export was updated; then passed |
| Existing-data provenance regression | Failed with calibration 1234 instead of 8; shared resolver fixed it |
| Focused CLI/diagnostic suite | 30 passed in 16.51 s |
| python -u solution.py --preset quick --check | Completed; Ruff, artifact checks, 418 tests, all scientific stages |
| Final pre-commit run --all-files -v | All five hooks passed; 418 tests in 101.47 s |
| Final check_notebooks | solution: six code cells; tutorial: 19 code cells executed in memory |
| Final standalone quick command | Completed in 6.60 s; all six stages and output paths exist |
| Final figure/link/source checks | 11 PNG + 10 PDF, every image >1,000 bytes; all report links and current source hashes match |
| Independent review | One P2 resolved; no open actionable findings |

Final quick command: `python -u solution.py --preset quick`.

- Run index: benchmark_outputs/solution_runs/20261024T230048Z-0fa4fc8f/report.md
- Manifest/log: run.json and terminal-output.log beside the index.
- Figures: figs/solution_runs/20261024T230048Z-0fa4fc8f/
- Raw data: benchmark_outputs/runs/dcc50eaf70041a8f/noisy_benchmark_results.json
- Benchmark: six records from two cases, one seed and three modes.
- Comparison: twelve resource rows and twelve finite sampled scores across six variants.

The quick run is a workflow smoke check, not evidence of a statistically preferred DD
strategy. One replicate does not estimate uncertainty. The printed E[s] remains an
inverse conditional mean-penalty proxy, not the expected reciprocal sampled score.

Gate logs: /private/tmp/duq-review/solution-cli-final-gate.log,
solution-cli-final-run.log and solution-cli-notebooks.log. Independent review and extra
configuration/failure probes are copied to SOLUTION_CLI_REVIEW.md; original detailed
evidence remains under /private/tmp/duq-cli-review/.

All changes remain local and unstaged on codex/repair-diagnostics. Existing historical
data disposition and external safety snapshots remain documented in RUN_GUIDE.md.
