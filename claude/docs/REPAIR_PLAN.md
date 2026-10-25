# Repository repairs and diagnostics implementation plan

> For agentic workers: execute the tasks in order, with failing regression tests before fixes.

**Goal:** resolve every actionable review finding and quality gap, then add useful diagnostics.
**Spec:** `REVIEW_2026-10-24.md` and the user's instruction to do all fixes before diagnostics.
**Architecture:** a normal Python physics module is canonical; notebooks are thin consumers.
Benchmark simulation, provenance, statistics, and plotting remain separate from submission code.
**Stack:** Python 3.12, the installed Cirq 1.8 development build, NumPy, Matplotlib, pytest.

## Constraints and decisions

- Never modify `Google Quantum AI Challenge.ipynb`; verify its recorded SHA-256 at the end.
- Preserve existing benchmark outputs. A regression-test incident violated this constraint for
  the two historical raw JSON files; the user chose to retain the original report and PNG only.
  No historical reconstruction or rerun is authorized. New runs use separate provenance directories.
- Work locally on `codex/repair-diagnostics`; no staging, commits, pushes, or remote writes.
- No hardware jobs. Keep development and diagnostic simulations bounded.
- Enforce the 1,750-moment inclusive limit and the challenge's supported gates/connectivity.
- Preserve exact state preparation; no new physics algorithm is needed for these repairs.
- Undefined scores are explicit records, not silently clamped finite numbers.
- Complete the fix gate before writing diagnostic feature code or producing diagnostic figures.
- Diagnostics destination: both notebook summaries and saved reports/figures, as the user chose.
- Organizer email confirms bonus grading for 2 ≤ N ≤ 15, fixes `range(len(qubits))`, and leaves
  grading cases/correlator sizes undisclosed; see `CHALLENGE_CORRECTIONS.md`.
- User requested all saved figures under repository-level `figs/`, with reports/data remaining
  under `benchmark_outputs/`. Notebook/report links and test isolation must follow that layout.

## Task 1: canonical physics, contract limits, inert imports, submission export

- [x] Add regressions for the 90-qubit depth violation, import side effects, invalid integer inputs,
  canonical module independence from notebooks, and the full bonus scoring range.
- [x] Observe expected failures, then move the existing proven physics into `claude/dicke_prep.py`.
- [x] Add derivations, explicit reachable-subspace assumptions, types, validation, and final limits.
- [x] Make `solution.py` / `solution.ipynb` thin synchronized consumers; script-only work guarded.
- [x] Add a deterministic standalone export containing only allowed imports and both entry points.
- [x] Run focused regressions and the complete suite. Update README with the actual architecture.

## Task 2: trustworthy benchmark configuration, provenance, results, and efficiency

- [x] Add regressions for runtime shot overrides, source/noise/calibration signature changes,
  canonical pair ordering, preserved legacy outputs, singleton seeds, and nonfinite scoring.
- [x] Separate shot/noise RNG seeds; expose shared ensemble probabilities for tutorial consistency.
- [x] Fingerprint effective noise/preparation/scoring/source/calibration/runtime inputs.
- [x] Validate checkpoint schema and record sets; write strict JSON atomically in new run folders.
- [x] Cache case circuits and ideal probabilities across seeds; use local X-basis transforms.
- [x] Report paired seed statistics; do not label across-case spread as estimation uncertainty.
- [x] Validate analytical damping/readout, bit order, probability mass, and malformed inputs.

## Task 3: tutorial, analysis, and control correctness

- [x] Add failing regressions for singleton plotting, final trace reachability, invalid controls,
  detuning-enabled leakage, and shot-only seed experiments.
- [x] Fix plotting/statistics and score-status handling without adding new diagnostic features yet.
- [x] Use production calibration helpers; correct detuning explanations and plot ensembles.
- [x] Fix slider bounds, remove the misleading unused hardware switch, regenerate the tutorial.
- [x] Execute both working notebooks headlessly; compare generator and mirror sources.

## Task 4: quality and packaging fix gate

- [x] Resolve all Ruff findings, document public interfaces, and add local quality configuration.
- [x] Record the Python environment and dependency lock; make the documented notebook command valid.
- [x] Add pre-commit/CI checks, a submission checklist, and reproducible verification records.
- [x] Full pytest, lint/format, syntax/schema, allowed-import export, dependency checks pass.
- [x] Mark F01–F10 resolved with evidence. Only then start Task 5.

## Task 5: diagnostic outputs and figures (after the fix gate)

- [x] Add tested scientific summaries for exact/noisy states, circuit costs, and data provenance.
- [x] Produce amplitude/phase, Hamming-weight/leakage, X-correlator, layout, circuit-cost,
  paired-score and convergence figures, with sample counts and uncertainty definitions.
- [x] Add a bounded CLI and notebook cells that save PNG/PDF plus machine-readable metrics.
- [x] Preserve historical report/figure as historical evidence; explicitly document unavailable raw data.
- [x] Separate physical-noise, shot-noise, and exact-state evidence in labels and recommendations.
- [x] Inspect representative rendered figures and execute the final notebooks/CLI.

## Task 6: final review and handoff

- [x] Run the full suite and required checks once on the final implementation.
- [x] Have a fresh reviewer inspect the final diff; resolve actionable findings.
- [x] Verify protected notebook and surviving historical report/PNG hashes, clean diffs, no staged binaries.
- [x] Update this plan, project continuity notes, and `PLAN_STATUS.md` with results and commands.

## Progress ledger

- Setup: user authorized all reviewed fixes, followed by diagnostics. Baseline review: 123 tests pass.
- Setup: existing review documents preserved; no source changes existed before implementation.
- Execution decision: implement inline because the module, notebook, and benchmark interfaces are
  coupled; use an independent final reviewer. No further design approval is needed for the fixes
  explicitly requested from the completed review. New diagnostics use the stated defaults.

## Review focus

Import-only callers; sparse/disconnected calibration; maximum-depth requests; one/zero valid score
pairs; resumed or legacy data with different provenance. Tests must cover each owning task.

- Repair evidence: 260 tests passed after the main fixes. Additional repair-review regressions
  then passed with all five pre-commit hooks and clean headless notebook execution.

- FIX GATE PASSED: all five pre-commit hooks passed; independent repair review has no open correctness findings. New diagnostics start after this entry.
- User-directed incident disposition: preserve original report and PNG only; do not recompute lost historical raw data. See DATA_RECOVERY_2026-10-24.md.
- Diagnostics implemented only after the fix gate: eight PNG/PDF views, JSON and three CSV tables,
  notebook display and saved reports. New bounded experiment: six cases, five seeds, three modes,
  10,000 shots per basis, 90 records. Source identity is separate from the historical experiment.
- Numerical diagnostic regressions cover analytical correlators, phases, missing/undefined pairs,
  singleton intervals and tiny leakage. Final full gate and fresh diagnostics review passed.

- Final evidence: 373 tests pass in 90.42 seconds; all five pre-commit hooks, explicit all-source
  Ruff checks, dependency consistency, clean notebook execution and artifact preservation checks pass.
- Independent final review and narrow figs/ follow-up have no unresolved findings. One missing-legend
  edge case was reproduced, regression-tested, corrected and independently reconfirmed.
- Final report: benchmark_outputs/diagnostics/D6_3-d8ef4d3e3b0b/report.md. All figures are under
  figs/; numeric reports/tables remain under benchmark_outputs/. No commits or remote writes.
