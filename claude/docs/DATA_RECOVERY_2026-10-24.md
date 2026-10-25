# Historical benchmark data incident — October 24, 2026

During the repairs, a failing regression test called the original benchmark after changing
`OUTPUT_DIR`. That version had already bound `CHECKPOINT_PATH` and `RESULTS_PATH` to the real
repository output directory. Consequently, the test replaced both original 240-record JSON
files with a three-record, 37-shot configuration record. This was an implementation error in
the review/repair session, not a user action.

The independent repair reviewer identified it. Searches of scratch files, available VS Code
history/backups, and retained review evidence found no complete raw-data backup. The original
Markdown report and PNG figure survived. The user explicitly chose **keep the surviving report
and figure only**, rather than rerunning or reconstructing the original experiment.

The surviving files remain at:

- `benchmark_outputs/noisy_benchmark_report.md`
- `figs/historical/noisy_benchmark_insights.png` (moved without changing its bytes when the user
  requested all figures under `figs/`; originally `benchmark_outputs/noisy_benchmark_insights.png`)

The erroneous three-record files were moved to
`benchmark_outputs/recovery/overwritten-test-artifacts/`, with incident metadata under
`benchmark_outputs/recovery/INCIDENT.json`. They are test artifacts, not historical observations.
No reconstructed dataset will be presented as the original run. Those raw records are unavailable;
new diagnostics must use a clearly identified new run or display the surviving summaries as such.

The current benchmark resolves output paths when a run starts, under its configured output root.
Its tests use temporary roots, and an integration regression checks that a pre-existing legacy
sentinel is unchanged. Before any test executes a benchmark, its effective destination must be
verified. Existing reports and figures have independent preservation hashes.
