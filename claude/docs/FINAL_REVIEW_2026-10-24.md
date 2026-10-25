# Independent final code review — diagnostics and repository integration

Reviewed on October 24, 2026, against base `d40c6c1397e50f421ac56e68a94b1c22112a6d7e`.
Implementation is uncommitted on `codex/repair-diagnostics`. The review used
`final-review.diff` and the current sources, including the narrow legend and leakage-mask
corrections made during this review. This reviewer made no repository, index, HEAD, branch,
benchmark-data, or remote changes. All probe output is under `/private/tmp/duq-review/`.

## Strengths

- The completed repairs are separated cleanly from the diagnostic feature. The canonical
  physics lives in `claude/dicke_prep.py`; both working notebooks consume it and call the same
  report builder. The main challenge notebook remains byte-identical, verified independently
  with SHA-256 `ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1`.
- Exact-state diagnostics retain relative phase information and remove only a common global
  phase. Leakage is summed directly outside the target support, including a verified
  `1e-20` leakage case. The independent target vector and global-phase checks behave correctly.
- The X-correlator calculation agrees with the original challenge's average-over-subsets
  definition. Independent dense-Hadamard checks, including empty/full excitation boundaries,
  complements, and all orders through N=7, had maximum absolute residual `2.22e-16`.
- Distribution metrics distinguish probability outside the requested weight from conditional
  nonuniformity within that weight. Physical-noise ensemble probabilities and finite-shot
  score samples are labeled separately; the report does not call the reciprocal score fidelity.
- Paired statistics use finite matched observations and common seed cohorts across cases.
  Singleton/empty cohorts have unavailable uncertainty. Approximate Student-t intervals use
  the seed count and explicitly state the heavy-tail, small-sample, and fixed-calibration limits.
- Calibration, benchmark source, noise settings, runtime, and score-dataset identity are
  recorded separately. For the current dataset, calibration and all benchmark source hashes
  match the saved diagnostic provenance. The report says its provenance *structure* is checked,
  without claiming that an arbitrary supplied file was independently reproduced.
- PNG/PDF views use explicit rendering canvases. The current native-schedule and paired-score
  figures were inspected directly: physical-time widths, gate legends, sample counts, exclusions,
  log score scale, signed differences, and intervals are readable and consistent with the data.
- The historical raw-data loss is candidly recorded and the surviving report/PNG remain
  identified as historical evidence. The new 90-record dataset is explicitly separate.
  No historical reconstruction is claimed or requested.

## Issues

### Critical — none

No critical finding remains from this review.

### Important — none

No important correctness, scientific-validity, or integration finding remains from this review.

### Minor — one found and corrected during review

**R1 / P3: Preserve the score-plot legend when the first case has no finite pairs. Resolved.**

- Original location: `claude/diagnostic_plots.py:387` and its legend call (then line 426).
- Trigger: the first declared case has zero finite DD/no-DD pairs, while a later case has one
  or more finite pairs. Labels were assigned only when `i == 0`, so all drawn observations
  were unlabeled. The figure lost the DD/no-DD legend and Matplotlib emitted
  `No artists with labels found to put in legend`.
- Impact: viewers could not map the score colors to modes; warnings-as-errors also broke
  rendering for this valid mixed-data case. Numerical scores and intervals were unaffected.
- Correction reviewed: current `claude/diagnostic_plots.py:376–390` tracks `labeled_modes`
  and labels the first actual observations of each mode. The added regression in
  `claude/tests/test_diagnostics.py` covers an undefined first case followed by a singleton.
- Independent confirmation: rerendered the actual saved payload after clearing the first
  case's pairs, promoted `UserWarning` to an exception, inspected actual figure legend labels,
  and saved PNG/PDF successfully. Labels are exactly `dd`, `no-dd`; no warning occurred.
  Output: `final-diagnostic-probes/fixed-legend/07_paired_scores.{png,pdf}`.

## Verification performed by this reviewer

These were focused probes, not a duplicate full-suite execution.

1. Read the repair plan, historical review, repair resolution/status, organizer corrections,
   historical-data incident disposition, prior independent repair gate, and reviewer template.
2. Reviewed current diagnostic metrics, plotting, driver, tests, benchmark/statistics/analyzer,
   canonical preparation/independent validation, submission/artifact/notebook checks, working
   notebook integration/mirror, changed tutorial code, calibration, and quality configuration.
3. Recomputed the new experiment's aggregate directly from its raw records, independently of
   the reporting helper:

   | Quantity | Independent result |
   | --- | ---: |
   | Records / cases / paired seeds | 90 / 6 / 5 |
   | Mean DD | 8.626438952000584 |
   | Mean no-DD | 8.649095619812640 |
   | Mean paired difference | -0.022656667812054575 |
   | Paired standard error | 0.014239814368518535 |
   | Approximate 95% t interval | [-0.06219273071445307, 0.01687939509034392] |

   These agree with the saved report and do not establish a universal DD advantage.
4. Checked analytical X correlators and phase handling, as described above.
5. Built a separate no-score diagnostic bundle for N=1,k=0, with resource size 2 and one
   zero-detuning sensitivity point. It completed with six PNG/PDF figures, strict JSON, three
   CSVs, zero-moment schedules, and explicitly unavailable paired comparisons:
   `final-diagnostic-probes/boundary/D1_0-9af7648b4aee/report.md`.
6. Reproduced R1 before correction, then independently verified the correction. Rechecked
   the support-mask change using a `1e-20` leakage example: result
   `1.0000000000000005e-20`.
7. Reverified the protected challenge hash; inspected an empty staged diff. The reviewer did
   not stage files, commit, push, install dependencies, run hardware, or launch the benchmark.

The main agent reported that all five pre-commit hooks passed with 371 tests and both working
notebooks executed cleanly immediately before R1's final small edit. Those results are reported
context, not checks independently rerun by this reviewer. The main agent owns the fresh final
suite/source checks, notebook execution status, preservation hashes, and regenerated diagnostic
bundle after the plot/metrics source hashes changed.

## Recommendations

- Complete the already planned final gate on the final sources, including the new mixed-data
  regression, and record its exact outcome in the current status documents.
- Generate the final diagnostic bundle from the existing 90-record raw dataset because the
  diagnostic source hashes changed. A noisy benchmark rerun is unnecessary for these changes.
- Retain the explicit unavailable-data and small-sample language in later report revisions.

## Declined to judge

- Hardware performance or hardware-wide DD policy: the authorized work uses a small, approximate
  local CPU model and explicitly limits its conclusions.
- Recovery, reconstruction, or rerunning the historical 240 records: the user explicitly chose
  the surviving report and figure only; this remains an acknowledged loss of raw data.
- New adaptive algorithms, globally optimal layout search, and dense simulation of large
  structural cases: these are outside the repair/diagnostic plan, which preserves the existing
  exact construction and bounds dense simulation.
- Undisclosed grading (N,n) cases or correlator cutoff: the organizer has not provided them;
  the documented N≤15 bonus range and local experiment choices are distinguished correctly.
- Actual GitHub Actions execution, publication, submission, or remote-write behavior: none is
  authorized here; the local definitions were reviewed as source only.
- Live browser/widget rendering in a Jupyter frontend: this review inspected source integration,
  saved figures, and focused rendering behavior; the primary's in-memory execution is a separate
  Python-behavior check and does not certify a specific frontend installation.
- A repeated full pytest/lint/pre-commit/notebook gate: the review assignment explicitly leaves
  that gate to the main agent to avoid duplicated work.

## Assessment

**Ready for final handoff: Yes, subject to the main agent's final verification gate.**

No unresolved correctness or scientific-validity finding remains in this review. R1 was fixed
and independently reconfirmed. The diagnostics meet the requested notebook-and-saved-report
scope, preserve the protected original, identify current versus historical evidence, and use
statistical claims consistent with their finite paired-seed design. No commit, push, merge,
hardware execution, or historical-data rerun is recommended by this verdict.

## Addendum — user-requested `figs/` layout

The user subsequently requested that all figures go to a `figs` folder. A narrow read-only
follow-up review covered `claude/output_paths.py`, diagnostic/analyzer routing, report links,
both saved notebook consumers and their source/mirror, test isolation, headless notebook
configuration, ignore/documentation changes, and the existing artifact relocation.

**Follow-up verdict: approved; no new finding.** The original review verdict remains valid,
subject to the main agent's final full verification gate on these final sources.

Independent evidence:

- `figure_root()` defaults to the absolute repository `figs/` path and resolves the temporary
  `DUQUANTUM_FIGURES_DIR` override at call time. The diagnostic builder records the absolute
  `figure_dir`; its report and both notebook display cells use that field. Diagnostic source
  provenance includes `output_paths.py`.
- Diagnostic figures are routed to `figs/diagnostics/<bundle>/`; analyzer figures are routed to
  `figs/benchmarks/<dataset-hash>/`. Reports, raw data, JSON, and CSV remain separate. The
  autouse pytest fixture and headless notebook checker explicitly redirect figure outputs to
  temporary directories.
- Independently generated a small N=2,k=1 bundle and ran the analyzer against the existing raw
  dataset, using `/private/tmp/duq-review/figs-routing-probes/figs` as the override. All six
  diagnostic PNG/PDF pairs and the analyzer PNG were saved there. Every report link resolves;
  no PNG/PDF appeared alongside the reports. Probe reports and logs remain under
  `/private/tmp/duq-review/figs-routing-probes/`.
- Independently verified all 65 entries in `benchmark_outputs/recovery/FIGURE_RELOCATION.json`:
  every destination exists with the recorded SHA-256 and every old source path is absent.
- Every listed PNG/PDF in all five current saved diagnostic bundles exists under its recorded
  `figs/diagnostics/` directory and is linked by its report. This includes the final
  `D6_3-d8ef4d3e3b0b` bundle. No image/figure file remains outside `figs/` in the repository,
  and none remains stranded under `benchmark_outputs/`.
- Verified the incident-record hashes for the original surviving report and the relocated
  historical PNG. Both match; the historical PNG is now at
  `figs/historical/noisy_benchmark_insights.png`. The protected challenge hash still matches.
- Verified executable source equality for the saved solution notebook/Python mirror and full
  source equality for the tutorial/generator. Both notebooks consume recorded `figure_dir`
  and retain cleared saved outputs.

No physics, score, statistical policy, historical reconstruction, or benchmark rerun was added
by this layout request. The existing declined-to-judge list still applies; no new behavior was
set aside. The main agent owns the final 373-test/pre-commit gate and final notebook execution.
