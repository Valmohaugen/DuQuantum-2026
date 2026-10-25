# Protecting the work and running saved diagnostics

The active working branch is `main`. It combines the reviewed solution workflow with
upstream main `4225b90`, including the teammate additions under `ryon/` and `toby/`.
Those source files are preserved as comparison references; the supported preparation
and evidence pipeline live in `claude/`. Reference files are excluded from maintained-code
lint/format checks. Earlier integration records describe the versions present at their
recorded commits. The protected original challenge notebook remains unchanged.
See [MAIN_INTEGRATION.md](MAIN_INTEGRATION.md) for this checkpoint and publication steps.

## Backups and Git checkpoints

The complete pre-integration snapshot is outside the checkout:

`/Users/valentine/.Codex/backups/DuQuantum-2026/2026-10-24T215713Z/`

It contains `workspace.tar.gz`, `files.json`, `receipt.json`, `tracked-changes.patch`,
`status.txt` and `history.bundle`. Every archived file was checked against its SHA-256.
It includes ignored figures/results and untracked source files. A branch name alone does
not save uncommitted files. The historical 240-record dataset was already unavailable before
this backup; it is not restored by this snapshot.

To make the reviewed source changes a permanent local Git checkpoint, run these commands
yourself from the repository root after inspecting the changes:

```bash
conda activate duquantum
git switch main
git status --short --branch
git add -- .gitignore README.md solution.py solution.ipynb claude .github .pre-commit-config.yaml .python-version environment.yml pyproject.toml
pre-commit run --all-files
git diff --cached --stat
git commit -m "Integrate validated Dicke preparation and diagnostic tooling"
```

The commands above stage and commit locally; no push is included. If output stripping edits a
notebook, stage that notebook again and repeat the checks before committing. Git records the
staged contents, so `git commit -am` alone would omit newly created files. See the official
[commit documentation](https://git-scm.com/docs/git-commit).

For future teammate updates, fetch and inspect before choosing an integration:

```bash
git fetch origin
git status --short --branch
git log --oneline HEAD..origin/main
git diff --stat HEAD...origin/main
git diff
```

`fetch` updates remote-tracking information without merging it into the working branch.
The final `git diff` shows local tracked edits; `status` also shows untracked additions.
A branch without an upstream is normal for a local review branch; the earlier `pull` error
was not evidence of overwritten work. See the official [fetch documentation](https://git-scm.com/docs/git-fetch).

`figs/` and `benchmark_outputs/` are saved locally and intentionally ignored by Git. Preserve
new experiment artifacts separately when you want a lasting copy on another disk or machine:

```bash
artifact_stamp=$(date -u +%Y%m%dT%H%M%SZ)
tar -czf "../DuQuantum-artifacts-${artifact_stamp}.tar.gz" figs benchmark_outputs
```

To inspect the pre-integration backup in a separate new directory, clone its Git bundle there
and extract its workspace archive into that clone. Keep the active checkout in place while
checking the restored copy.

## Run the combined solution and save the complete report

From the repository root, with the project environment active:

```bash
conda activate duquantum
python -u solution.py
```

Or activate the environment and run in one shell command:

```bash
conda run --no-capture-output -n duquantum python -u solution.py
```

This validates the selected constructor, runs/resumes DD/no-DD/ideal paired simulations,
analyzes their sampled scores, saves all eight diagnostic views, compares maintained and
upstream variants under the same model, and exports a standalone constructor with the
selected preparation settings. The default **full** workflow also runs software checks,
both notebooks and exact main/bonus export validation before scoring. It benchmarks all
28 nontrivial cases N=2–8, n=1–(N−1), with five seeds, 10,000 shots per basis, two detuning
realizations and all X orders through each case's N. DD/no-DD/ideal produce 420 records.
Both exported functions are validated at every N=2–15, n=0–N: 133 cases, 266 circuits.
Resource-only probes cover 2, 4, 8, 15, 16, 30, 60, 90. Density simulation is bounded to small
cases; the larger checks use pure state vectors or constructor-only checks.

Each invocation saves a unique `benchmark_outputs/solution_runs/<run-id>/` directory with:

- `report.md`: index linking to every stage's saved result.
- `run.json`: resolved settings, source hashes, run status and output paths.
- `terminal-output.log`: complete terminal tables, progress and any failure traceback.
- `validation.json`, analysis and diagnostic Markdown/JSON/CSV, comparison source/circuit
  snapshots, and a standalone `submission.py` with the selected preparation defaults.
- `bonus_validation/report.md`, `results.json` and `results.csv` in a full run, covering
  both actual exported functions, state fidelity, native rules, CZ counts and moments.

**All figures are saved automatically** under `figs/solution_runs/<run-id>/`.
Diagnostics and comparison each save PNG/PDF; analysis saves PNG. Raw reusable checkpoints
remain under `benchmark_outputs/runs/<fingerprint>/`. The terminal prints the run index
and figure directory. A failed stage returns a nonzero status and preserves completed
stages, the traceback and failed manifest. Temporary settings are restored when called from
Python/notebooks. No hardware, Git commit, push or submission is part of this command.

The wider comparison can expose unsupported cases or bugs in optional reference solvers.
Reference construction or validation errors are saved as explicit error rows with full
tracebacks in the comparison's `errors/` directory. Those requests receive no score, and
the run index reports their count. Unexpected maintained-solver errors and failures in the
shared noise/scoring pipeline still stop the run. The reference source files remain verbatim.

The known minimal-reference D(5,4) routing failure is repaired through a local adapter:
when Cirq has no candidate swap pair, it proceeds to its existing fallback. The reference
constructor body, calibration, graph selection and compilation are preserved. New comparison
JSON records `reference_adapters` and hashes/snapshots `reference_routing.py`. The shared Cirq
module and original reference files are unchanged. Earlier reports retain the original
failure; rerun the comparison to obtain the repaired result. See
[REFERENCE_ROUTING_FIX.md](REFERENCE_ROUTING_FIX.md).

```bash
python -u solution.py --preset quick
python -u solution.py --no-check --no-bonus-check
python -u solution.py --cases 2,1 4,2 6,3 --seeds 1,2,3,4,5 --shots 20000 --dd-strategy sparse
python -u solution.py --mode validate --cases 15,7
python -u solution.py --mode compare --cases 2,1 4,2 15,7 --seed 42
python -u solution.py --mode diagnose --results path/to/noisy_benchmark_results.json
python -u solution.py --plan
python -u solution.py --help
```

| Option | Effect |
| --- | --- |
| `--preset quick`, `standard`, `full` | Two cases/one seed/1,000 shots/one realization; six cases/three seeds/10,000 shots/two realizations; default full 28 nontrivial N≤8 cases/five seeds/10,000 shots/two realizations |
| `--cases N,n ...` | Explicit qubit/excitation pairs; overrides preset cases |
| `--nmin 2 --nmax 8` | Generate n=1…floor(N/2) for the selected N range; mutually exclusive with `--cases` |
| `--all-excitations` | With `--nmax`, include every n=1…N, including complementary and product states |
| `--seed 42` or `--seeds 1,2,3` | One replicate or a unique comma-separated list; one replicate cannot estimate uncertainty |
| `--shots`, `--realizations` | Samples per basis and physical detuning realizations per replicate |
| `--calibration-seed` | Synthetic calibration used consistently for validation, benchmark, diagnostics and comparison |
| `--dd-strategy dense` or `sparse` | DD-on benchmark/export policy; no-DD remains paired, and comparison evaluates all three hybrid policies |
| `--construction optimized` or `analytic` | Default exact four-CZ/square synthesis, or the preserved previous constructor; recorded data keep their original choice |
| `--max-correlator-size` | Override the X scoring cutoff; full defaults to all applicable orders, quick/standard to four; grading cutoff remains undisclosed |
| `--detuning-khz`, `--t1-us`, `--tphi-us` | Physical noise settings, with explicit units |
| `--gate-1q-ns`, `--gate-cz-ns` | Gate durations used by the noise model |
| `--beam-width`, `--search-seconds` | Layout search controls |
| `--sparse-min-idle-slots`, `--max-routing-qubits` | Sparse-DD window threshold and bounded routing limit (zero disables routing fallback) |
| `--resource-sizes 2,4,8,16,30` | Constructor-only scaling probes; larger sizes do not trigger large density simulations |
| `--diagnostic-case 4,2`, `--detuning-levels 0,10,20,50` | Illustrative state and sensitivity sweep levels in kHz |
| `--fresh` | New separate benchmark repeat; matching checkpoints resume by default |
| `--no-ideal`, `--no-upstream`, `--skip-comparison` | Omit ideal benchmark baseline, upstream reference variants, or the comparison stage in all mode |
| `--baseline /path/to/module.py` | Add a frozen preparation module to the comparison |
| `--output-dir`, `--figures-dir` | Override data/report and figure roots; defaults are repository `benchmark_outputs/` and `figs/` |
| `--check` / `--no-check` | Include/skip lint, format, protected artifacts, full pytest and both notebook executions; automatic for unfocused full all-mode |
| `--bonus-check` / `--no-bonus-check` | Include/skip exact checks of both exported entry points; full default covers 133 cases, focused runs check the selected cases |
| `--plan` | Print effective settings/stages and exit without running experiments or creating output folders |

`benchmark` mode includes validation, analysis and the eight-view report. `compare` is a
fresh shared-model code comparison; noise sampling is bounded to N≤6. `validate` checks
exact fidelity through N=16 and gates/connectivity/depth for larger sizes. `diagnose` uses
an explicitly supplied dataset's recorded noise/calibration/preparation settings; without
`--results`, it produces six state/circuit views for the CLI model and has no paired score
data. Benchmark/all density cases are limited to N≤10. N=10 can be much slower than the
default full N≤8. `--check` runs both notebook exploration checks headlessly in temporary
directories, preserving the saved notebooks and earlier hand-run outputs. Scientific
report figures are saved separately in the run's persistent figs directory.

For focused experiments, `--preset quick`, `--preset standard`, a narrower `--mode`, or
explicit `--cases`/`--nmax` skips broad software/bonus suites by default. Focused cases also
become the default resource probe sizes; `--resource-sizes` overrides this. Add `--check`
and/or `--bonus-check` when desired. Use `--mode validate --cases 15,7 --bonus-check` to
check that one state in both exported functions. `--plan` prints all resolved choices.

Matching source/model checkpoints resume; incompatible configurations use separate run folders.
The density model is approximate and all computation is local CPU simulation.

To regenerate figures/report from a chosen completed run without rerunning its benchmark:

```bash
python -u -m claude.scripts.diagnose --results benchmark_outputs/runs/<run-id>/noisy_benchmark_results.json
```

An exact-state/noise/resource report without a raw score dataset has six figures; the paired-score
and seed-convergence views require completed score data. Source changes produce a new diagnostic
identity. The old report and measurements remain separate evidence for their recorded sources.

## Compare implementations under the same experimental conditions

```bash
python -u -m claude.scripts.compare_solutions
python -u -m claude.scripts.compare_solutions --cases 4,2 6,3 --seeds 1,2,3,4,5 --shots 10000 --correlator-size 6
python -u -m claude.scripts.compare_solutions --no-noise
```

The default compares hybrid dense/sparse/off, upstream sparse/off, and the minimal reference.
Use `--baseline /absolute/path/to/older/dicke_prep.py` to add a frozen older implementation.
The six default resource cases reach N=15; density simulations stop at N=6. Every returned
circuit is checked against the native gate rules and the exact Dicke target before scoring.
Searches use each implementation's defaults; heuristic routing choices may depend on runtime.
Saved circuits identify the choices actually made in that run.

Each invocation gets a new directory under `benchmark_outputs/comparisons/`, containing:

- `report.md`, `comparison.json`, `resources.csv`, `scores.csv`;
- source snapshots with recorded hashes under `sources/`;
- native circuit JSON under `circuits/`, with explicit output-qubit coordinates in the data;
- resource/paired-score figures in PNG/PDF under `figs/comparisons/<run>/`.

The calibrated maps, noise parameters, scorer, shots, correlator cutoff and paired RNG seeds
are shared. Large cases provide structural/exact-state evidence rather than dense-noise scores.
Intervals are approximate, small-sample comparisons of reciprocal scores. The analytical
`E[s]` proxy in the upstream harness is not used. Local choices do not predict hidden grading.

The hybrid adopts the known-input first-split saving and a bounded connected-patch routing
fallback while retaining the efficient native-path core. Dense DD stays the default; sparse
DD is an explicit experiment choice:

```python
from claude.dicke_prep import PrepConfig, create_dicke_state

config = PrepConfig(dd_strategy="sparse", sparse_min_idle_slots=4)
circuit, qubits = create_dicke_state(N, n, *calibration, config=config)
```

Sparse pulses fill virtual single-qubit slots. Previously empty slots can become emitted
moments, so sparse DD can increase depth relative to DD-off. The constructor always reapplies
the 1,750-moment limit. `max_routing_qubits=0` disables the routing fallback; its default bound
is 15 qubits to keep the fallback construction workload limited.

## Notebook exploration

```bash
jupyter lab solution.ipynb
jupyter lab claude/tutorial/Dicke_Tutorial.ipynb
```

Run the tutorial setup and cells in order. Its exploratory plot calls now save PNG/PDF under
`figs/notebooks/tutorial/<kernel-session>/` before displaying. Different slider views receive
content hashes; unchanged views are deduplicated. Missing or damaged saved images are restored
when that view is shown again. `figures.json` records paths, hashes and save times.
The report figures use their own recorded `figure_dir` and are also displayed in the notebooks.

For additional plots you write yourself, use the same helper explicitly:

```python
from claude.notebook_figures import save_and_show

# Construct or update your matplotlib figure here.
save_and_show("solution-experiments")
```

This preserves the plotting backend and saves before display. Ordinary new `plt.show()` calls
and implicit frontend displays do not themselves promise files on disk; use the helper for
those additions. Notebook outputs are cleared before commits, while saved figure files remain.
Tests and headless notebook checks override figure destinations with temporary directories.

## Terminal table

Benchmark and comparison commands print one aligned table per seed:

```text
N  n  var  CZ  mom  build  rules  ideal  f  Zfloor  Zbias  X  E[s]  sampled
```

`ideal` is noiseless target fidelity; `f` is modeled Z target-sector survival.
`Zfloor` is the exact conditional mean Z sampling penalty; `Zbias` is the conditional Z
nonuniformity penalty. `X` includes both squared correlator bias and finite-shot variance.
The requested `E[s]` heading is an inverse-mean-penalty proxy, not an expectation of the
reciprocal official score. `sampled` is the unmodified official finite-shot score.
Undefined/infinite outcomes remain explicit. Cached benchmarks print stored values and
original build times without resampling. Unsimulated cases show `--` for unavailable columns.
All component values are saved with the raw JSON and comparison CSV rows.

The matched DD/no-DD score figure uses a **0–2** y-axis. Triangles at the plot boundaries
mark means or standard-deviation bars outside the view; overflowing means are labeled.
This changes the display range only. The official reciprocal score can exceed 2, and
the report table and raw records retain the full values. The difference panel has its
own scale; its values are not absolute scores.

`var` means implementation/DD variant. DD is dynamical decoupling: echo pulses placed
in idle windows to suppress sensitivity to detuning. Pulse overhead can also add noise,
so a denser policy is not assumed to score better.

| Variant | Implementation and policy |
| --- | --- |
| `hybrid dense` | Maintained solver; dense DD in eligible idle slots |
| `hybrid sparse` | Same solver; canceling X-pulse pairs only in long idle windows, controlled by `--sparse-min-idle-slots` |
| `hybrid off` | Same solver; DD disabled |
| `upstream sparse` | `ryon/dicke_solution.py`; that reference's sparse echo policy |
| `upstream off` | `ryon/dicke_solution.py`; DD disabled |
| `minimal` | Separate `ryon/minimal_dicke.py` reference implementation, with the recorded local Cirq empty-candidate routing guard |
| `baseline` | Optional module supplied with `--baseline`; its own defaults |

The hybrid label identifies the maintained solver's combined construction strategies.
It does not combine implementations during the benchmark. Different implementations'
sparse policies can yield different pulse sequences. In the simpler benchmark table,
`dd` is the selected maintained DD policy, `no-dd` disables DD, and `ideal` is a nearly
noiseless, zero-error-calibration baseline with finite measurement shots.
