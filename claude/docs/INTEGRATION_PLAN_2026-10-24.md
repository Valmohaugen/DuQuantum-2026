# Upstream comparison and preservation plan

User request: protect the repaired work, compare newly pushed code, combine verified improvements,
and ensure reports/figures are saved during future local diagnosis runs.

## Fixed constraints and design decisions

- Original challenge notebook remains byte-identical; no hardware, commits, pushes or GitHub writes.
- Current repair branch and all local changes stay in place. Incorporate only a verified additive
  upstream fast-forward; do not pull/rebase/reset or replace repaired files wholesale.
- Verified external safety snapshot: /Users/valentine/.Codex/backups/DuQuantum-2026/2026-10-24T215713Z/.
  Includes all 163 working files, ignored figures/results, per-file hashes, patch and Git bundle.
- Remote main verified live as d8f148d271aeef552c450af668be169c192bc058; its only changes from
  d40c6c1 are four additions under ryon/. Keep these source references intact.
- Canonical tested physics remains claude/dicke_prep.py; use one shared calibration/noise/scoring
  pipeline for comparisons. Different harness assumptions cannot rank the implementations fairly.
- Candidate improvements: one-CZ first W-tree split and optional sparse paired echo pulses.
  Retain the current nearest-neighbor general Dicke construction unless evidence favors routing.
- Correctness and challenge validity precede gate/depth/cost comparisons. A small modeled score
  comparison does not establish a universal hardware/DD preference.
- Save comparison JSON/CSV/Markdown under benchmark_outputs/comparisons/ and all PNG/PDF under figs/.
  Preserve previous artifacts and raw data; new source/config identities get separate directories.
- Explain manual Git integration steps and the difference between local files, commits and backups.

## Tasks and verification

- [x] Inspect branch/remote state without pulling; verify remote SHA with ls-remote.
- [x] Make and hash-verify external backup of every current source and saved result/figure.
- [x] Fast-forward only the four additive upstream files; verify every pre-existing file hash.
- [x] Compare both algorithms with independent exact states, rules, resources and a common noise model.
- [x] Write failing regressions, implement proven improvements, confirm state/phase preservation.
- [x] Add reusable comparison/report output and verify every figure path is saved under figs/.
- [x] Document reproducible user commands, backup restoration and safe future integration.
- [x] Independent review; full quality gate, notebook execution, export and protected/survivor checks.
- [x] Update plan/status and external continuity notes; hand off local unstaged changes.

## Review focus

Sparse pulses must never cross an operation on their qubit; first-split optimization is valid only
from the known all-zero input; unsupported inputs stay explicit; comparisons must use identical
calibration/noise/seeds/correlator settings; saved outputs must identify their actual source and
must not overwrite prior runs. Notebook-only plots and CLI plots must both be persisted.

## Final evidence

399 tests pass in90.27s; all five pre-commit hooks pass, both notebooks execute and all28
maintained Python files pass lint/format. Independent review has no unresolved findings.
Common-model comparison and standard report links are in PLAN_STATUS.md. Seven tutorial
views were actually exported to figs/notebooks/. All115pre-existing saved artifacts remain
byte-identical. Current source/data are local and unstaged; no new commit or remote write.
