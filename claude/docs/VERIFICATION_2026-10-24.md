# Final verification — October 24, 2026

Executed in the existing project environment with `/opt/anaconda3/envs/duquantum/bin/python`,
Python 3.12.15. Canonical physics, benchmark/data provenance and diagnostic output were reviewed
independently before the final gate. Diagnostics were added only after the original repair gate.

| Verification | Final result |
| --- | --- |
| Complete pytest suite via pre-commit | 373 passed in 90.42 s |
| All five pre-commit hooks | Pass: lint, format, working-output stripping, artifact contracts, complete tests |
| Explicit Ruff checks of solution.py and claude/ | Lint passes; all 23 Python files formatted |
| Dependency consistency | pip check: no broken requirements |
| Headless solution notebook | Six code cells execute cleanly, including report/figure display |
| Headless tutorial notebook | 19 code cells execute cleanly, including report/figure display |
| Notebook schema, syntax and source contracts | Valid; solution mirror and tutorial generator match; working outputs cleared |
| Protected original notebook | SHA-256 unchanged |
| Original historical report and PNG | Both SHA-256 unchanged; PNG relocated into figs/historical/ |
| Existing artifact relocation | All 65 PNG/PDF moves byte-identical; links and metadata updated |
| Current 90-record raw dataset | Complete; effective source/settings/calibration signature matches current benchmark |
| Final diagnostic bundle | Source/raw hashes match; strict JSON, three populated numeric CSV tables, eight valid PNG/PDF pairs |
| All saved figure paths | Under figs/; report links resolve; tests/checker use temporary roots |
| Submission exporter | Refreshed; export byte-equal to canonical module; isolated import contract tested |
| Git whitespace/index | diff --check clean; index empty; no binary artifacts staged |
| Independent final review | No unresolved findings, including the user's figs/ request |

The independent review checked all X-correlator orders through N=7 against dense Hadamard
probabilities (maximum residual 2.22×10⁻¹⁶), empty/full/complement states, zero-moment schedules,
10⁻²⁰ leakage, finite-pair exclusions and intervals, and figure routing/link integrity.
The final suite tests every excitation count through confirmed bonus N=15 structurally,
all counts through N=11 exactly, selected exact states through N=16, plus extra stress cases.
No test is presented as knowledge of the undisclosed grading cases or correlator cutoff.

## Reproduce local checks

From the repository root with `conda activate duquantum`:

```bash
python -m pip check
python -m ruff check solution.py claude
python -m ruff format --check solution.py claude
pre-commit run --all-files -v
python -m claude.scripts.check_notebooks
python -m claude.scripts.build_submission submission_outputs/submission.py
```

To regenerate the current report and figures from the existing new dataset, without rerunning
its benchmark:

```bash
python -m claude.scripts.diagnose --results benchmark_outputs/runs/9adfed8ea7db4a95/noisy_benchmark_results.json
```

Reports/JSON/CSV go under `benchmark_outputs/diagnostics/`; PNG/PDF go under `figs/diagnostics/`.
Source changes create a new diagnostic identity. The original historical raw dataset is
unavailable and is not a regeneration input. See `DATA_RECOVERY_2026-10-24.md`.

This is local CPU verification. No hardware job, commit, push, remote CI run or submission was
performed. Headless notebook execution does not certify a specific Jupyter widget frontend.
The adaptive entry point remains the legal non-adaptive fallback. No universal DD preference
or hardware fidelity is inferred from the approximate noise model and five replicate seeds.
