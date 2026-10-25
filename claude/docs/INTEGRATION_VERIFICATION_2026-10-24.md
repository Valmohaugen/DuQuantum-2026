# Integration verification — October 24, 2026

User requested protected local work, a comparison with incoming teammate code, selective
combination, and reliable saving of report/exploration figures. These checks ran after the
original repair task was complete.

- Remote main was verified live as d8f148d271aeef552c450af668be169c192bc058 before and after work.
- Verified external pre-integration backup: /Users/valentine/.Codex/backups/DuQuantum-2026/2026-10-24T215713Z/.
  All 163 archived files and the archive's hashes were checked. It includes untracked files,
  ignored figures/results, patch, status and Git-history bundle.
- The local fast-forward only added four ryon/ files. Every pre-existing file hash was checked
  unchanged at that point. All four additions remain byte-identical to upstream.
- Every one of the 115 saved artifacts present before integration still matches its baseline
  hash. Existing reports, raw data and figures were not replaced by the new runs.
- First-split, sparse-pulse, native-rule, routing-fallback and persistence regressions passed.
- Final full suite: **399 passed in 90.27 seconds**. All five pre-commit hooks passed on a frozen
  checkout. An earlier run had 399 passing tests but detected concurrent README editing;
  the final clean gate supersedes that run.
- Ruff lint/format passes for all 28 maintained Python files. Upstream reference files are
  deliberately retained verbatim outside that formatting scope, with issues documented.
- Both working notebooks execute in memory with temporary destinations, with saved outputs
  cleared and mirror/generator consistency intact. Original notebook SHA-256 remains
  ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1.
- Locked package versions are unchanged; NetworkX 3.7 is now an explicit dependency. pip check
  passes. Standalone export is refreshed and its isolated import is tested.
- Independent review verified 195 exact line cases, 18 routed cases, 120 arbitrary-input
  scheduling/DD unitary checks, star boundaries, CLI product cases, saved-view recovery and
  the complete current comparison artifacts. No actionable code issue remains.

## Saved evidence

- Common-model comparison: /Users/valentine/github/hackathons/DuQuantum-2026/benchmark_outputs/comparisons/20261024T221541Z-b98ebfe737a7-11ac8b/report.md
- Standard eight-view report: /Users/valentine/github/hackathons/DuQuantum-2026/benchmark_outputs/diagnostics/D6_3-42ba04fe7b0c/report.md
- New complete 90-record dataset: /Users/valentine/github/hackathons/DuQuantum-2026/benchmark_outputs/runs/ed0da3e25389d176/noisy_benchmark_results.json
- Actual tutorial export: /Users/valentine/github/hackathons/DuQuantum-2026/figs/notebooks/tutorial/20261024T222009Z-0a1474e7 (7 PNG/PDF views).

The comparison stores 42 resource rows (41 valid, one explicitly unsupported), 84 score
observations, 28 paired summaries, 15 source snapshots, and 41 circuit JSON files with output
qubit coordinates. All source snapshot hashes and figure links were verified. Its individual
runs get distinct output directories. Figures are under figs/comparisons/, with source/data
under benchmark_outputs/comparisons/.

The standard report uses a separately identified new run: six cases, five seeds, three modes,
10,000 shots/basis. DD minus no-DD is −0.00601916 with paired SE 0.009491 and approximate 95% t
interval [−0.0323704,0.0203321]. These small model-dependent data do not choose a hardware-wide DD
policy. The earlier lost 240-record dataset remains unavailable; no reconstruction was attempted.

Native resource examples in the shared-calibration comparison:

| State | Previous repaired CZ/moments | Hybrid CZ/moments | Upstream sparse CZ/moments |
| --- | ---: | ---: | ---: |
| D(2,1) | 2/5 | 1/3 | 1/3 |
| D(4,2) | 13/23 | 12/21 | 14/25 |
| D(6,3) | 36/53 | 35/51 | 45/76 |
| D(15,7) | 280/237 | 279/235 | 464/531 |

Heuristic candidate selection and timing are run-dependent; consult the saved actual circuits
and rows, rather than treating this table as an invariant. Dense and sparse choices remain
separate experiments. Sparse may add emitted moments by filling virtual slots; the cap is
rechecked. The routed fallback is bounded to 15 qubits by default and can be disabled.

No new commit, staging, push, remote write, or hardware run was performed. RUN_GUIDE.md contains
the manual local checkpoint and separate artifact-backup commands. Figures/results are local
and Git-ignored. Notebook exploratory additions should call save_and_show explicitly.
