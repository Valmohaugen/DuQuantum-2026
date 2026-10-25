# Repair resolution — October 24, 2026

The original [review](REVIEW_2026-10-24.md) is a historical snapshot. All ten findings below
were corrected and independently reviewed before the additional diagnostic feature was started.
Final verification status is tracked in [PLAN_STATUS.md](PLAN_STATUS.md).

| Finding | Correction | Permanent evidence |
| --- | --- | --- |
| F01: over-limit circuits | Canonical constructor enforces the inclusive 1,750-moment cap; unsupported requests fail loudly | `test_never_return_an_over_depth_circuit`, both DD modes and the preserved 90-qubit fixture |
| F02: invalid benchmark reuse | Full effective configuration, preparation/scoring/source/calibration/runtime provenance; strict schema/record checks; new run directories | Signature, corrupt-checkpoint, metadata and atomic-write tests in `test_benchmark.py` |
| F03: import side effects | Inert canonical `.py` library, thin working notebooks, genuine script guard and standalone allowed-import export | Import-safety, module-independence, export-outside-repository and artifact-contract tests |
| F04: ignored runtime shots | Explicit shot count supplied to every experiment mode | Actual-sampling configuration regression with 37 shots, isolated in a temporary directory |
| F05: misleading tutorial detuning | Shared ensemble probabilities for scores/plots; corrected compiled-gate explanation; independent noise/shot RNGs | Detuning population regression, shot-seed invariance and domain separation tests |
| F06: unstable calibration ordering | Sort qubit endpoints and pairs canonically before seeded draws | Equivalent-topology/reversed-metadata calibration regression |
| F07: one-seed plotting failure | Shared finite-pair statistics; uncertainty unavailable at a singleton | Synthetic singleton analysis and diagnostic-report tests |
| F08: nonfinite official scores | Preserve scorer semantics using explicit finite/infinite/undefined statuses, strict JSON and exclusion counts | Nonfinite score/status tests, undefined-pair bundle regression, no invented uncertainty |
| F09: inaccessible final trace step | Trace control bound covers all allowed cases, including step 21 for D(7,6) | Exhaustive allowed-control-range trace regression |
| F10: inconsistent validation sliders | Validate/clamp excitation count before construction | Full allowed validation-control-range regression |

Additional repairs include independent exact-state/gate/routing/depth validation, dependency
locking and environment documentation, format/lint cleanup, consistent generator/mirror checks,
quiet imports, cached benchmark work, typed documented public physics APIs, analytical derivations,
readout/damping/bit-order tests, explicit unsupported cases and reproducible RNG streams.

The organizer's subsequent email is recorded in [CHALLENGE_CORRECTIONS.md](CHALLENGE_CORRECTIONS.md).
Tests cover every excitation count through the confirmed N≤15 bonus range structurally, all
such counts through N=11 exactly, selected larger/complement states through N=16, and extra
N=16–20 stress cases. Local cases and correlator cutoff are not claims about hidden grading.

Diagnostics are implemented separately from submission physics: exact-state errors, leakage and
Z/X residuals, physical layout/cost proxies, native schedules, resource scaling, detuning sensitivity,
paired scores and seed convergence. Saved PNG/PDF, strict JSON and numeric CSV accompany the
notebook display. Uncertainty uses finite matched seed replicates; interval assumptions and
small-sample limits are explicit. A tiny-leakage regression prevents cancellation at 10⁻²⁰.

The historical raw JSON loss was caused by an early regression test against the old bound output
paths. It is documented in [DATA_RECOVERY_2026-10-24.md](DATA_RECOVERY_2026-10-24.md); per the user's
choice, the original report and PNG alone are retained. Current benchmark tests guard output
destinations before execution. New raw data is separately identified, not a historical recovery.

## Final gate

373 tests passed in 90.42 seconds; all five pre-commit hooks pass. Both working notebooks
execute cleanly; all-source lint/format, dependency/export/artifact checks pass. The independent
final review and figs/ follow-up have no unresolved findings. All saved figures now go under
figs/, with reports and notebooks using the recorded figure_dir. See
[VERIFICATION_2026-10-24.md](VERIFICATION_2026-10-24.md) for commands and limits.
