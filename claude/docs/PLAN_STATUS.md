> Current integration: development continues on `main`, combining upstream main `4225b90`
> with the reviewed solution workflow. Teammate sources under `ryon/` and `toby/` are
> preserved, the public credit document is omitted, and the original challenge is unchanged.
> All 168 updated-reference circuits validate; both notebooks and static checks pass.
> The installed commit hook gates the complete software suite. Remote publication remains
> user-managed. See [MAIN_INTEGRATION.md](MAIN_INTEGRATION.md) for this checkpoint.

> Previous follow-up: the actual minimal-reference D(5,4) routing failure is repaired.
> A local, recorded Cirq guard allows the router's existing fallback when swap candidates
> are empty; reference source, global Cirq state and maintained physics remain unchanged.
> Verification: 466 tests pass in 105.09 s; all 168 small-case circuits validate with zero
> reference errors; repaired D(5,4) produces 30 scores across six variants and five seeds.
> Both notebooks and quality checks pass; independent review is clear. See
> [REFERENCE_ROUTING_FIX.md](REFERENCE_ROUTING_FIX.md) and
> [REFERENCE_ROUTING_REVIEW.md](REFERENCE_ROUTING_REVIEW.md).
> Saved report: benchmark_outputs/reference_routing/20261025T010027Z-reference-routing/report.md.

> Previous milestone: thorough default workflow completed; actual no-flags invocation exited 0 in 377.91 s.
> `python -u solution.py` selects 28 full cases, all X orders, software/notebook checks,
> and 133 bonus-range cases checked in both exported functions (266 circuits). Flags narrow scope.
> Full run: benchmark_outputs/solution_runs/20261025T002251Z-5cda7439/.
> All 266 exported circuits pass; 420 benchmark records, 168 comparison resource rows,
> 445 comparison scores and 21 saved figures verified. One optional minimal-reference error
> retains its traceback and receives no score. D(90,45) remains an explicit unsupported probe.
> Follow-up: matched-score display uses 0–2 with overflow markers; variant labels are explained.
> Updated presentation: benchmark_outputs/plot_updates/20261025T003757Z-score-view/.
> Final suite after presentation changes: 461 tests pass in 98.33 s; both notebooks execute.
> All 1,239 pre-existing saved artifacts and original challenge remain byte-identical;
> all four upstream reference files match d8f148d. No stage/commit/push or hardware execution.
> See [THOROUGH_DEFAULT_PLAN.md](THOROUGH_DEFAULT_PLAN.md),
> [THOROUGH_DEFAULT_REVIEW.md](THOROUGH_DEFAULT_REVIEW.md),
> [THOROUGH_DEFAULT_VERIFICATION.md](THOROUGH_DEFAULT_VERIFICATION.md) and [RUN_GUIDE.md](RUN_GUIDE.md).

Previous optimized-synthesis milestone: test_sol.py optimizations integrated using exact closed-form angles.
> Default construction is optimized; `--construction analytic` retains the previous solver.
> Current calibration CZ counts: D(4,2)12→5, D(6,2)26→17, D(6,3)35→29,
> D(8,4)70→61, D(15,7)279→258. Square selection retains calibrated path/routing fallbacks.
> Final gate:450 tests pass in102.19s; all five pre-commit hooks pass; both notebooks execute.
> Independent physics audit and integration review are clear. All709 pre-existing saved
> result/figure/reference/original files remain byte-identical. No hardware or Git writes.
> Latest full report: benchmark_outputs/solution_runs/20261024T233528Z-bc30a1d0/report.md.
> Matched comparisons: benchmark_outputs/optimized_integration/final/20261024T233654Z/.
> See [OPTIMIZED_SYNTHESIS.md](OPTIMIZED_SYNTHESIS.md),
> [OPTIMIZED_SYNTHESIS_VERIFICATION.md](OPTIMIZED_SYNTHESIS_VERIFICATION.md),
> [OPTIMIZED_SYNTHESIS_PLAN.md](OPTIMIZED_SYNTHESIS_PLAN.md) and [RUN_GUIDE.md](RUN_GUIDE.md).

Previous unified CLI milestone: one-command solution workflow completed. `python -u solution.py` now runs
> validation, benchmark, analysis, eight-view diagnostics, shared-model comparison and
> configured standalone export, with saved logs/index/manifest and all figures under figs/.
> `--preset quick`, experiment flags, narrower modes, `--plan` and optional `--check` are supported.
> Final gate:418 tests pass in101.47s; all five pre-commit hooks pass; both notebooks execute.
> Independent CLI review is clear after the recorded-model provenance fix. See
> [SOLUTION_CLI_VERIFICATION.md](SOLUTION_CLI_VERIFICATION.md),
> [SOLUTION_CLI_REVIEW.md](SOLUTION_CLI_REVIEW.md) and [RUN_GUIDE.md](RUN_GUIDE.md).
> Latest quick index: benchmark_outputs/solution_runs/20261024T230048Z-0fa4fc8f/report.md.
> Quick run:6.60s, 11 PNG and10 PDF files; all stage paths, links and source hashes verified.

Previous terminal-table milestone: requested terminal tables implemented in benchmark and comparison commands.
> All14columns are printed per seed, with saved diagnostics and corrected finite-shot penalties.
> Final gate:406tests pass in91.97s; all five pre-commit hooks pass. See
> [TERMINAL_TABLE.md](TERMINAL_TABLE.md) and [TERMINAL_TABLE_REVIEW.md](TERMINAL_TABLE_REVIEW.md).
> Latest table demo: benchmark_outputs/comparisons/20261024T223822Z-f011e5150b68-31af56/terminal-output.txt.
> Latest standard report: benchmark_outputs/diagnostics/D6_3-ac4a52542b98/report.md.

# Current status — upstream integration completed

The repair branch includes upstream main d8f148d plus the local verified integration. The
upstream additions were fast-forwarded without replacing existing files or creating a commit.
All work remains local and unstaged on codex/repair-diagnostics. No push, publication, or hardware
job occurred. The original challenge notebook and all four upstream reference files are unchanged.

| Follow-up phase | Done | Pending |
| --- | --- | --- |
| Preservation | Verified 163-file external pre-integration snapshot, Git bundle, patch and hashes; all 115 older saved artifacts remain byte-identical | None |
| Code comparison | 42 resource rows, 84 sampled scores, 28 paired summaries, 15 source snapshots and 41 native circuits saved | None |
| Selective integration | One-CZ known first split, optional sparse DD, bounded connected-patch routing fallback; efficient native core retained | None |
| Figure persistence | Eight report views, two comparison views, seven actually exported tutorial views, all in PNG/PDF under figs/; missing/corrupt view recovery tested | None |
| Final quality | 399 tests pass in 90.27 s; all five pre-commit hooks pass; lint/format and both notebooks clean; independent review clear | None |
| Git checkpoint | Incoming additions included locally; external backup protects uncommitted and ignored files | User may review and make a local commit using RUN_GUIDE.md |

Read [RUN_GUIDE.md](RUN_GUIDE.md) for exact commands and preservation instructions,
[INTEGRATION_REVIEW_2026-10-24.md](INTEGRATION_REVIEW_2026-10-24.md) for independent review,
and [INTEGRATION_VERIFICATION_2026-10-24.md](INTEGRATION_VERIFICATION_2026-10-24.md) for evidence.
The older completed repair record below is the pre-integration baseline, not the latest artifacts.

Current comparison: [report](../../benchmark_outputs/comparisons/20261024T221541Z-b98ebfe737a7-11ac8b/report.md).
Current standard diagnostics: [report](../../benchmark_outputs/diagnostics/D6_3-42ba04fe7b0c/report.md).
Current raw run: benchmark_outputs/runs/ed0da3e25389d176/noisy_benchmark_results.json.
Sparse DD remains optional; the short noisy comparison does not establish a universal preference.

---

# DuQuantum 2026 — completed repair and diagnostic status

Plan: [REPAIR_PLAN.md](REPAIR_PLAN.md). Finding resolution: [FIX_STATUS.md](FIX_STATUS.md).
Original findings: [REVIEW_2026-10-24.md](REVIEW_2026-10-24.md). Independent final review:
[FINAL_REVIEW_2026-10-24.md](FINAL_REVIEW_2026-10-24.md). Verification:
[VERIFICATION_2026-10-24.md](VERIFICATION_2026-10-24.md).

| Phase | Done | Pending |
| --- | --- | --- |
| Canonical physics / challenge contract | Tested Python module, 1,750-moment cap, input/calibration validation, inert imports and standalone export | None |
| Benchmark validity | Effective configuration/source/runtime fingerprints, distinct RNG streams, strict JSON/statuses/checkpoint validation, paired statistics | None |
| Tutorial / analyzer | Correct detuning ensemble, reachable controls, singleton/undefined-score support and backend preservation | None |
| Packaging / quality | Locked project environment, local pre-commit installed, lint/format, artifact checks and local CI definition | Remote CI deliberately not triggered |
| Additional diagnostics | Both notebooks; saved Markdown/JSON/CSV; eight PNG/PDF views; all figures under figs/ | None |
| Final verification / review | 373 tests pass; all five pre-commit hooks pass; both notebooks execute; independent final review clear | None |

All original F01–F10 code corrections passed the repair gate before diagnostic feature code
was added. Final complete suite: **373 passed in 90.42 seconds**. Ruff lint and format pass
for all 23 Python files. All five local pre-commit hooks pass. Both working notebooks execute
in memory with temporary figure/report destinations: solution has six code cells; tutorial
has 19. Saved notebooks remain valid, synchronized and output-free. Dependency consistency,
standalone export/import, whitespace, strict JSON, CSV, figure/link and preservation checks pass.
Headless execution verifies Python behavior, not a particular frontend's widget rendering.
The independent review found no unresolved correctness or scientific-validity issue.

The original challenge notebook is byte-identical, SHA-256
`ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1`.
The source of truth is `claude/dicke_prep.py`; notebooks are consumers. The organizer email
confirms **2 ≤ N ≤ 15** for bonus grading and corrects `range(len(qubits))`; see
[CHALLENGE_CORRECTIONS.md](CHALLENGE_CORRECTIONS.md). All excitation counts through N=15
are structurally tested, all through N=11 exactly, selected larger states through N=16.
Extra N=16–20 cases are stress tests. Hidden cases and correlator sizes are not inferred
from local benchmark settings. The adaptive function remains the allowed non-adaptive fallback.

## Current diagnostic artifacts

- Report: [D(6,3) diagnostic report](../../benchmark_outputs/diagnostics/D6_3-d8ef4d3e3b0b/report.md).
- Figures: `figs/diagnostics/D6_3-d8ef4d3e3b0b/` — eight views in PNG and vector PDF.
- Numeric metrics and three CSV tables: beside the report under `benchmark_outputs/diagnostics/`.
- Current raw run: `benchmark_outputs/runs/9adfed8ea7db4a95/noisy_benchmark_results.json`.
- Separate analyzer plot: `figs/benchmarks/ea620c603403e499/noisy_benchmark_insights.png`.
- Export: `submission_outputs/submission.py`; byte-equal to the canonical physics module.

The new run contains 90 records: six cases through N=6, five seeds, DD/no-DD/ideal modes,
10,000 shots per basis. Paired aggregate DD minus no-DD is −0.0226567, SE 0.0142398,
approximate 95% t interval [−0.0621927, 0.0168794]. These are small-sample, model-conditional
results; they do not establish a hardware-wide DD preference. Exact D(6,3) fidelity is one
within floating-point precision; maximum aligned phase residual is 1.18×10⁻¹⁵ rad.

## Historical-data disposition and local state

Historical raw JSON was lost in the documented regression-test incident. The user chose to
keep the surviving original report and PNG only. Both retain their recorded hashes; the PNG
was moved byte-identically to `figs/historical/noisy_benchmark_insights.png` at the user's
request that all figures go under `figs/`. No historical run was reconstructed or rerun.
All 65 relocated figures have individual preservation hashes in the relocation ledger.
The separate new run is not presented as recovery of the historical observations.

Changes remain local and unstaged on `codex/repair-diagnostics`. No commits, hardware jobs,
pushes, GitHub writes or submission were performed. The local CI definition has not run remotely.
Follow [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) and the original challenge's
instructions when preparing all required material for the manual upload.
