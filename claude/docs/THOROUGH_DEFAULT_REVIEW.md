# Independent review: thorough default workflow

Reviewed the current uncommitted changes against `claude/docs/THOROUGH_DEFAULT_PLAN.md` on base HEAD 7695923. No remaining actionable correctness findings after the two fixes below were independently rechecked.

## Findings resolved during review

1. **Focused single-qubit validation regressed (P2).** Inferred resource sizes filtered out N=1 and unconditional `min(sizes)` then raised `min() iterable argument is empty` for `--mode validate --cases 1,0` and `1,1`. Confirmed with an isolated parser probe. The revised inference falls back to `(2,)`; both new regression cases pass.
2. **Interrupted bonus validation omitted CSV evidence (P2).** Before the fix, a KeyboardInterrupt on the second validation left one completed JSON row and no CSV, because CSV was written only at the end or inside `except Exception`. Confirmed with an isolated actual-export probe. The revised code saves CSV after each completed row; the new interrupt regression now independently passes, retaining the completed JSON and CSV row.

## Scope and scientific evidence checked

- Default parsing selects all 28 nontrivial N=2–8 cases, five seeds, 10,000 shots, two realizations, and cutoff 8. The scorer clamps the cutoff to each case's N, so every applicable X order is included.
- Default bonus scope contains exactly 133 N=2–15, n=0–N cases and invokes both actual configured standalone export functions for 266 independent exact-state and native-device checks.
- Stage order places software/notebook checks first, then selected validation, configured export, bonus validation, noisy benchmark, analysis, diagnostics, and comparison.
- Explicit cases/ranges, smaller presets, and narrow modes skip broad suites unless requested; explicit boolean overrides remain effective. Focused resource sizes and the default balanced D(8,4) diagnostic case resolve correctly.
- Configured export coverage uses the analytic constructor in its test and checks its distinct CZ count, which provides meaningful evidence that the tested functions come from the configured exported file rather than merely the in-repository default.
- Exact validation independently checks qubit count/no hidden ancillas, allowed gates, calibration membership for main, Willow device rules, depth, finite fidelity, and target amplitudes/phases. Bonus uses the permitted full-device construction and does not infer noisy performance from exact fidelity.
- Reviewed every test call into the unified CLI: execution tests use quick/focused cases or validate mode. Full configuration is only parsed or passed to inert `--plan`. The notebook checker creates namespaces without `__file__`, so the mirror's guarded CLI entry point cannot recurse into full checks.
- Tiny complement-state spot checks passed for upstream sparse/off and minimal variants at D(3,2), D(4,3), and D(5,3), addressing the new complementary-excitation coverage.
- README, run guide, solution mirror and notebook prose describe the changed scope. The original challenge notebook and optimized physics module are outside the current diff.

## Independent execution evidence

Environment: project Python `/opt/anaconda3/envs/duquantum/bin/python`; MPLCONFIGDIR and XDG_CACHE_HOME under `/private/tmp/duq-review`; OPENBLAS_NUM_THREADS=1; PYTHONDONTWRITEBYTECODE=1. Test cache disabled, all test outputs under `/private/tmp/duq-thorough-review`.

- Initial focused parser/export/failure tests: 12 passed.
- After fixes, focused defaults/override/actual-export/failure/single-qubit tests: 14 passed.
- Interrupt persistence and subprocess help/full-plan/quick-plan tests: 2 passed.
- `git diff --check`: clean when inspected.

The complete test suite, both notebook executions, exhaustive 266-circuit export coverage, full 420-record density benchmark, generated figure inspection, and full no-flags invocation are owned by the parent execution, not duplicated by this review. No repository edits, hardware calls, Git mutations, Downloads writes, or remote publication were performed by the reviewer.

## Follow-up: optional reference fault isolation

No actionable correctness findings in the reviewed fault isolation. The actual D(5,4) comparison with upstream references enabled, one seed, 20 shots, zero detuning and noise_max_qubits=0 completed successfully. Five candidates returned validated exact circuits. The optional minimal reference retained an explicit error row and complete RouteCQC traceback ending in IndexError at an empty swap-candidate list. The failed request received no fabricated fidelity, CZ count, circuit or sampled score. With noise disabled, the full score and paired arrays were empty, and the CSV numeric fields for minimal were empty. Two PNG and two PDF figures, source snapshots, JSON, CSV and report were saved under the private review directory.

Independent injected RuntimeError probes confirmed that unexpected maintained constructor errors, maintained validation errors, shared noise simulation errors and shared scoring errors all propagate fatally. Existing NotImplementedError behavior still records an explicit unsupported request for maintained or reference builders; the revised prose accurately distinguishes this from unexpected faults. The master run manifest and report were independently checked to retain reference_error_count=1 and the optional-reference warning.

The three targeted comparison tests passed. No full suite or full default was run for this follow-up. The final tiny actual comparison was repeated only to anchor the evidence to the current source hash after the docstring clarification.

Final comparison report: `/private/tmp/duq-thorough-review/reference-isolation/actual-final/20261025T002424Z-e3801e22a481-9b9a84/report.md`

Full actual traceback: `/private/tmp/duq-thorough-review/reference-isolation/actual-final/20261025T002424Z-e3801e22a481-9b9a84/errors/N5-k4-minimal.txt`

Final evidence JSON: `/private/tmp/duq-thorough-review/reference-isolation/final-evidence.json`

Fault-injection evidence: `/private/tmp/duq-thorough-review/reference-isolation/fault-probe-evidence.json`

Verified SHA-256 values:

- `claude/scripts/compare_solutions.py`: `66cc094140f5b5c0cc6ce76acdfad14171931cd76c6182419a838f138b5e62b3`

- `claude/scripts/run_solution.py`: `d6f8afc5e5d591998d52be9db1866e0538a7a9798e4c79e07fdd4b8bfb8b7fcf`

- `claude/tests/test_comparison.py`: `ce772466f707ff107aadde0ecc0269478bdb2d96219dd4ad290e0531d3a16199`

- `ryon/minimal_dicke.py`: `0057bfcfa0c20e9743beebd929ea2735112035c8ebb95cbac0d124f018756a3f`

- `ryon/dicke_solution.py`: `6871a7261e2a93a10f1eff415807b29595868355d71b9f5b03137f914605eeb5`

- `claude/dicke_prep.py`: `75f9cad7b8d8c831fa8df43e6bad26336bc52af786993846c4de4c522adf29ed`

- `Google Quantum AI Challenge.ipynb`: `ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1`

- Final comparison.json: `044a49dedb5405c75035599c965df2e0024f9b300badc6de4a9c0f96d40d32c2`

## Final presentation review

No actionable findings. Visually inspected the actual full-run matched-score rendering and 28-case resource figure: the score panel is 0–2, overflowing means retain numeric labels, boundary triangles identify clipped means or SD extents, the difference panel retains its independent scale, and vertical resource labels are readable.

Private plotting-only probes confirmed singleton overflow (mean 3.5, unchanged difference 2.25), no-finite paired observations, and SD crossing both display boundaries. The plotter did not mutate any input data or numerically cap means. The full report still retains the actual 9.107 mean.

The variant glossary correctly distinguishes the maintained dense/sparse/off policies from upstream sparse/off and the separate minimal constructor; it does not imply that their sparse sequences match or that denser DD is automatically better. Its keys cover all six variants in the actual comparison.

Recomputed input hashes match the presentation metadata for the immutable 420-record benchmark and 168-resource/445-score comparison. Renderer snapshots match current sources. Read the parent suite log confirming 461 passed in 98.33 s; no full suite or science simulation was rerun by the reviewer.

Presentation report: `/Users/valentine/github/hackathons/DuQuantum-2026/benchmark_outputs/plot_updates/20261025T003757Z-score-view/report.md`

Private evidence: `/private/tmp/duq-thorough-review/presentation/review-evidence.json`

Verified presentation/source SHA-256 values:

- `claude/scripts/analyze_benchmark_results.py`: `311bd42cf36b388ff2f8a586e39cde7650ffacde5ba081015e99dfe5918d1705`

- `claude/scripts/compare_solutions.py`: `37ec1259b53dfdcc1541ce054c98146d433e2ac72c1fd6b419b10ac19f1b4c08`

- `README.md`: `c91ec9e4d8af334327f30c95ea1f736ecd6b6d9c1a2b8c4124a79572813c48fe`

- `claude/docs/RUN_GUIDE.md`: `c893678df72062963c4bd16dbadd159e738e4bd476a5e4614337734a868374b9`

- `/Users/valentine/github/hackathons/DuQuantum-2026/benchmark_outputs/plot_updates/20261025T003757Z-score-view/presentation.json`: `d2dcafd1f3f77662029ef5bfaff7325efd4236d5cdd3e101d9659328af09c83b`

- `/Users/valentine/github/hackathons/DuQuantum-2026/figs/plot_updates/20261025T003757Z-score-view/benchmarks/7f34aac54db6370e/noisy_benchmark_insights.png`: `63d831fc405ced2d84dc497a3ad8db751ef5d0b2be3258e3e14ed740a0a11c99`

- Saved benchmark input: `7f34aac54db6370eb9acb0befcc1e99d371d9c2c2d311b547262ff3561a69af1`

- Saved comparison input: `917ae1260972a360eb75147814df9c9fbf1395d15e163d7f03051e36e4c169f2`
