# Optimized Dicke synthesis implementation plan

User request: improve the maintained solver using /Users/valentine/Downloads/test_sol.py.
Prior discussion identified a five-CZ D(4,2) square circuit and cheaper split/shift blocks.
The existing original challenge, user runs, upstream references, CLI and diagnostic outputs
must be preserved. Keep the previous analytical constructor available for comparison.

## Design and derivation

The downloaded block tables are approximate fits. Their first-three-qubit kernel admits
an exact two-angle identity, so the general implementation does not need those 81 tables.
For R(t)=[[cos(t/2),-sin(t/2)],[sin(t/2),cos(t/2)]] and C_ab=diag(1,1,1,-1)
on the indicated pair, use these operations in chronological order:

1. R_a(-alpha), R_c(-pi/2), C_ab.
2. R_a(alpha), R_b(pi/2), C_bc.
3. R_b(pi/2+beta), R_c(beta), C_ab.
4. R_b(-pi/2), C_bc, R_b(-pi/2), R_c(pi/2).

Multiplication on the ordered columns |000>,|001>,|011> gives the 8x3 matrix
[[1,0,0], [0,cos(beta),0], [0,sin(beta),0], [0,0,cos(alpha)],
 [0,0,0], [0,0,0], [0,0,sin(alpha)], [0,0,0]]. All columns have the SAME
positive phase. Substitute alpha=acos(sqrt(r/m)), beta=acos(sqrt((r-1)/m))
to combine the original first Givens (2 CZ) and adjacent flagged shift (5 CZ)
into four CZ, saving three. Limits alpha=beta=0 preserve both inputs; alpha=beta=pi/2
moves |001> to |010> and |011> to |110>; alpha=beta=pi/4 makes positive equal splits.

The sorted-prefix invariant ensures these three local inputs at the beginning of a
stage with m>k. Preserve the remaining pruned gates and do not replace stages m<=k,
which may contain |111>. If the second gate is an unflagged shift, preserve it and
the existing one-CZ first-known-input optimization. This partial replacement improves
more stages than copying the reference's full-window lookup block.

For D(4,2), preserve the reference five-CZ square topology. Offline polishing exposed
simple closed forms a=atan2(2,1), b=2asin(1/sqrt(6)), and pi multiples; these were
independently proven against (|0011>+|0101>+|0110>+|1001>+|1010>+|1100>)/sqrt(6).
Only the closed forms are shipped. No numerical fits or optimizer run in production.
Choose a fully calibrated square only when its estimated calibration cost improves on
the available analytical-path candidate. A missing or costly square keeps the general
optimized path; bounded connected-patch routing remains available.

The split/shift target and sorted-input invariant follow Bärtschi & Eidenbenz,
arXiv:1904.07358, Section 2. The four-CZ identity and square adaptation are derived
and independently checked here from the user-provided file, not attributed to that paper.

## Files and tasks

- [x] Preserve a verified complete external workspace/reference snapshot and old solver copy.
- [x] Add failing regressions: four-CZ positive amplitudes and limits, lower actual CZ counts,
  square selection/fallback/calibration, line cost accounting and old construction option.
- [x] Add analytic stage planning/kernel and a certified five-CZ square to claude/dicke_prep.py.
  Keep line_gates as the original analytical logical sequence and the standalone module inert.
- [x] Add PrepConfig.construction optimized/analytic (optimized default) and CLI --construction;
  signatures/export inherit effective settings. Old datasets missing this field resolve analytic.
- [x] Run exact small/boundary/complement states, bonus range through15, sparse/dense/off DD,
  and standalone-export checks. Preserve old moment/time limits and no-path routing fallback.
- [x] Save matched calibration/noise/correlator/seeds comparison against the preserved old
  solver and downloaded candidate; all figures under figs/, raw evidence in unique folders.
- [x] Update README/run guide/notebook prose and current status; full tests, pre-commit,
  both notebooks, independent review, saved figure/link/preservation checks.
- [x] Update external plan/project continuity and hand off local changes, without commit/push.

## Review focus

Common relative phases across superposed inputs; excluded |111> at m<=k; correct per-edge
CZ cost after merging; all eight square orientations; fallback when a square is missing
or excessively noisy; no loaded historical dataset silently enabling a new constructor;
no runtime dependency on Downloads, optimizers, numeric block tables or repository files.

Backup: /Users/valentine/.Codex/backups/DuQuantum-2026/2026-10-24T231953Z-pre-optimized-blocks/
Receipt: 1,383 files, verified archive SHA-256
a6bfd65396ef7d848248949b92ab592f6129dedf4cec128de63817fbb43c158b.
Reference SHA-256: 5a9bc743c89a4f5af1e561c8162ba3af2aeb8d795a45d9dc00fd1fbb23c3f245.

Completed:450 tests pass in 102.19 s, all five pre-commit hooks pass, both notebooks execute.
Independent mathematical audit and integration review are clear. The two review findings
(legacy missing-setting defaults and configured bonus export) were reproduced, fixed and
independently rechecked. All 709 older result/figure/reference/original files match the backup.

Current artifacts: benchmark_outputs/solution_runs/20261024T233528Z-bc30a1d0/report.md;
benchmark_outputs/optimized_integration/final/20261024T233654Z/matched_runs.json.
Matched runs include64 resource rows, 240 individual sampled score records and source snapshots.
Full current benchmark:90 records. All 25 current image files and report links verified; figures
remain under figs/. See OPTIMIZED_SYNTHESIS_VERIFICATION.md for evidence and statistical limits.
