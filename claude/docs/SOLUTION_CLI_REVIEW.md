# Unified solution CLI review

Scope: `solution.py`, `claude/scripts/run_solution.py`, `claude/tests/test_solution_cli.py`, effective benchmark overrides/signature, recorded diagnostic settings, shared-model comparison arguments, and configured standalone export. Requirements read from `claude/docs/SOLUTION_CLI_PLAN.md`. Review is limited to the new CLI integration, not earlier repository repairs.

**Final status: no open actionable findings.** The one P2 issue below was fixed by the parent and independently verified with the original temporary dataset. The final plan is read-only, resolves the recorded model/cases/seeds, and the completed master manifest exactly matches the actual diagnostic settings.

## Finding

**[P2] Existing-data diagnostics save and print a configuration different from the one executed.**

At review time, `run_solution.py:293–314` returned preset/default noise, calibration, and preparation values when `--results` was supplied. `main()` serialized that configuration into `run.json` and `--plan` (`454–458`) and printed those settings (`497–501`), while the diagnostic stage deliberately passed no overrides for existing data (`519–540`), allowing `diagnose.build_report()` to use the recorded configuration instead. Rejecting explicit model overrides prevents silently ignored flags but does not fix this mismatch for defaults.

An actual N=2 benchmark followed by `--mode diagnose --results` produced:

| Setting | Master plan/manifest/log | Actual diagnostics |
| --- | --- | --- |
| Calibration seed | 1234 | 8 |
| Shots | 10000 | 37 |
| T1 in microseconds | 68 | 15 |
| Detuning in kHz | 20 | 0 |
| Realizations | 2 | 1 |
| DD policy | dense | sparse |

Resolve the recorded settings before printing the plan or saving the master manifest, or explicitly save separate requested and effective configurations with the actual effective settings clearly identified. Default cases/seeds should also reflect the selected dataset where appropriate; an explicit illustrative diagnostic seed can remain distinct.

Evidence: `/private/tmp/duq-cli-review/recorded-provenance/evidence.json`. Raw data, master manifest, diagnostic JSON, figures, and logs are retained under that same probe directory. Parent accepted this finding and is implementing the parser resolution fix; this document records the pre-fix evidence.

## Verification and remaining scope

- Focused CLI tests: **11 passed, 1 deselected** in 21.37 seconds. The parent owns the end-to-end test and broad gate; that one test was intentionally deselected here. Command used the project Python, `PYTHONDONTWRITEBYTECODE=1`, a temporary Matplotlib cache, `--basetemp=/private/tmp/duq-cli-review/pytest`, and `-p no:cacheprovider`.
- Tiny real N=2 benchmark: two paired records at 37 shots and zero detuning; no long benchmark was run. Existing-data diagnostics completed and produced **8 PNG + 8 PDF** views under the temporary figure root.
- Eighteen configurations yielded eighteen distinct benchmark fingerprints: baseline, cases, replicate seed, T1, Tphi, both gate durations, detuning, shots, realizations, correlator cutoff, calibration seed, beam width, search budget, DD strategy, idle-slot threshold, routing bound, and ideal-baseline toggle. Evidence: `/private/tmp/duq-cli-review/plumbing/evidence.json`.
- All scoped benchmark globals and `DUQUANTUM_FIGURES_DIR` were restored after successful contexts and a deliberate exception. The existing failed-run regression also passed, including saved traceback, failed manifest, and run index.
- Configured standalone export embeds all selected preparation settings and binds `create_dicke_state(..., config=...)` and `Hardware(..., config=...)` to the exported `CONFIG`. No-configuration export remains byte-identical to the canonical source.
- Protected original notebook SHA-256 is `ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1`, matching the required value. `git diff --name-only -- ryon 'Google Quantum AI Challenge.ipynb'` produced no paths.
- No repository edits, Git mutations, hardware calls, full suite, or long benchmark were performed by this reviewer. Probe outputs remain under `/private/tmp/duq-cli-review`.

## Independent fix verification

The parent introduced shared `diagnose.resolve_report_settings()` resolution, used by both CLI parsing and diagnostic generation. Reusing the original temporary N=2 raw dataset:

- Default cases, seeds, and illustrative case came from the dataset: `((2, 1),)`, `(31,)`, `(2, 1)`.
- `--plan` reported calibration seed 8, 37 shots, T1 15 microseconds, zero detuning, one realization, and sparse DD; the planned output directory did not exist afterward.
- Explicit `--seed 91` remained supported for the illustrative ensemble.
- A real diagnostic-only run completed. Its master manifest's calibration seed, every noise field, and every preparation field matched `diagnostics.json` exactly. Eight PNG and eight PDF files existed.
- Final evidence: `/private/tmp/duq-cli-review/recorded-provenance-fixed/evidence.json`.

No additional actionable CLI correctness/configuration/error-handling findings were identified in the remaining reviewed paths. The one finding is closed following this independent recheck.
