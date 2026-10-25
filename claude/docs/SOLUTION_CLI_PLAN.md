# Unified solution.py command

User asks for one command to do the scientific workflow and flags for experiments.
Default: validation, paired benchmark, analysis, diagnostic figures/report, shared-model
comparison, standalone export, saved terminal log and an index/manifest. Full software
quality checks are opt-in via --check. Keep import silent, original challenge unchanged,
working notebook synchronized, artifacts local and all saved figures under figs/.

Presets: quick (two small cases, one seed, 1,000 shots, one noise realization), standard
(six cases through N=6, three seeds, 10,000 shots, two realizations), full (all 16 cases
through N=8, five seeds, 10,000 shots). Explicit flags override preset defaults.

Modes: all, benchmark, compare, diagnose, validate. Common flags cover cases/ranges,
seeds, shots, calibration seed, correlator cutoff, detuning/T1/Tphi/durations, DD strategy,
resource sizes, output/figure roots, fresh/resume, optional comparison and upstream references.
Existing raw input is supported for diagnose mode. Each invocation saves a unique run index/log;
benchmark checkpoints retain source/configuration-addressed resume behavior. No hardware or Git writes.

- [x] Failing parser/workflow/config-fingerprint tests, without executing the old script guard.
- [x] Effective noise/preparation plumbing into benchmark signatures and reports.
- [x] Thin solution.py CLI delegate and reusable orchestrator; stage outputs/log/manifest.
- [x] Sync working notebook; document the one-line commands.
- [x] End-to-end quick run, invalid/plan/help tests, full gate and independent review.
- [x] Update status/continuity and hand off local changes.

Verification: 418 tests pass in 101.47 s; all five pre-commit hooks pass. Both notebooks
execute in memory. The final default quick command completed in 6.60 s, saved all six
stage outputs and 21 figure files, and passed link/source-hash checks. Source defaults,
existing-data effective configuration, error logs, configuration restoration, checkpoint
separation and configured standalone export are covered. Independent review's one P2
provenance finding was fixed and independently rechecked; no findings remain.

Final quick index: benchmark_outputs/solution_runs/20261024T230048Z-0fa4fc8f/report.md.
See SOLUTION_CLI_VERIFICATION.md, SOLUTION_CLI_REVIEW.md and RUN_GUIDE.md. No Git writes,
hardware calls, original challenge edits or upstream reference changes occurred.
