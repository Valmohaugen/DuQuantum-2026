# DuQuantum 2026 — Dicke-state preparation

Prepare exact weight-n Dicke states on calibrated Willow qubits using CZ and
`cirq.PhasedXZGate`. Hardware judging compares Z distributions and X correlators.
The bonus rewards depth and permits the current non-adaptive construction.
The organizer's email confirms bonus grading for **2 ≤ N ≤ 15** and corrects
`test_circuit` to use `range(len(qubits))`. The original notebook stays unchanged;
[the recorded corrections](claude/docs/CHALLENGE_CORRECTIONS.md) govern interpretation.
Grading cases and `max_correlator_size` remain undisclosed.

## Source of truth and artifacts

| Path | Purpose |
| --- | --- |
| `Google Quantum AI Challenge.ipynb` | Protected original challenge; reference only |
| `claude/dicke_prep.py` | Canonical tested physics, layout, synthesis, scheduling, and entry points |
| `solution.ipynb`, `solution.py` | Thin working notebook and jupytext mirror; imports are inert |
| `claude/scripts/run_solution.py` | Validated CLI settings and complete local workflow, logs and run index |
| `claude/reference_routing.py` | Local pinned-Cirq compatibility guard for minimal-reference comparisons; original source preserved |
| `claude/validation.py` | Independent exact-state and gate/routing/depth checks |
| `claude/scripts/noisy_benchmark.py` | Local density-matrix experiments with explicit model/provenance |
| `claude/scripts/analyze_benchmark_results.py` | Matched-seed analysis with explicit score exclusions |
| `claude/tutorial/Dicke_Tutorial.ipynb` | Generated tutorial, including independent shot/noise controls |
| `claude/scripts/build_submission.py` | Export both entry points as one standalone Python file |
| `claude/docs/REVIEW_2026-10-24.md` | Historical review and exact reproductions |
| `claude/docs/REPAIR_PLAN.md`, `claude/docs/PLAN_STATUS.md` | Repair plan and current verification status |

## Environment and checks

Use Python **3.12** and a project environment. The lock is generated with pip-tools for the
tested macOS environment; the local CI definition uses macOS and the same Python version.
Willow105 requires the pinned Cirq 1.8 development build.

```bash
conda env create -f environment.yml        # from repository root, for a new environment
conda activate duquantum
python -m pip install -r claude/requirements.txt  # update an existing project environment
python -m pip check
python -m pytest -q
python -m ruff check solution.py claude
python -m ruff format --check solution.py claude
python -m claude.scripts.check_artifacts
pre-commit install
pre-commit run --all-files
```

The original notebook is excluded from output stripping and checked by SHA-256. Working
notebooks must have cleared outputs before committing. Python sources are linted/formatted;
generated notebooks are checked for valid syntax/schema, clear outputs, and source consistency.
To update the lock deliberately, edit `claude/requirements.in`, then run
`pip-compile --output-file claude/requirements.lock claude/requirements.in` and rerun the checks.

## Working notebooks

```bash
jupyter lab solution.ipynb
jupyter lab claude/tutorial/Dicke_Tutorial.ipynb
jupytext --sync solution.ipynb
python -m claude.scripts.build_tutorial
```

The Python physics module is independent of notebook files. After editing notebook-only
exploration, synchronize the working mirror; after editing the tutorial generator, regenerate
the tutorial. Both import the same module. There is no hardware execution toggle or job path.
The original challenge's `test_circuit` calls `range(qubits)` on a set; keep it unchanged and
use `validate_preparation` instead.

## Preparation

For n=1, a low-error spanning tree distributes the excitation using subtree-size Givens angles.
The first known-input split uses one CZ; later Givens splits use two. The same first-split
saving applies to the general line construction. A bounded connected-patch routing fallback
handles small cases without a full path, using the existing logical construction.
For n≥2, a nearest-neighbor split-and-cyclic-shift construction follows
[Bärtschi and Eidenbenz](https://arxiv.org/abs/1904.07358). Its five-CZ flagged gate is valid on the
reachable subspace, rather than a general controlled rotation. For n>N/2, bitwise X complements
the smaller-weight state. The module includes the derivations and limiting cases.

The default `optimized` construction merges a reachable first Givens/MUX pair into four
CZ gates, saving three while retaining the other pruned gates and known first split.
For D(4,2), an exact five-CZ square is selected when its calibration-cost estimate beats
the general path. Both improvements were derived from the user-provided `test_sol.py`;
the fitted angle tables have been replaced by closed-form angles. No runtime file or
optimizer is needed. Missing or costly squares retain the path/routing fallback.
See [the derivation and validation](claude/docs/OPTIMIZED_SYNTHESIS.md).

Use `python -u solution.py --construction analytic` to run the previous constructor,
or `--construction optimized` for the new default. This choice reaches benchmark,
diagnostics, comparison, notebook consumers and standalone export, and enters the
checkpoint fingerprint. Existing recorded datasets without this setting retain their
original analytical construction when reanalyzed.

The constructor enforces the **1,750-moment inclusive limit** and rejects unsupported inputs
with `NotImplementedError`. A failed beam search is a heuristic failure, not proof that no path
exists. Routing, gate restrictions, exact small states, DD phase preservation, and the provided
bonus range through N=15 are checked independently, including complementary and boundary
excitation counts. The original N=16–20 cases remain additional structural stress tests.

## Reproducible simulation

With the `duquantum` environment active, the default command runs the complete supported
workflow: software checks, both notebooks, validation, configured export, full bonus-range
checks, the paired benchmark, analysis, all eight diagnostic views and solution comparison:

```bash
python -u solution.py
```

Use flags when you want a smaller or specific experiment:

```bash
python -u solution.py --preset quick
python -u solution.py --cases 2,1 4,2 6,3 --seeds 1,2,3,4,5 --shots 10000 --dd-strategy sparse --max-correlator-size 6
python -u solution.py --no-check --no-bonus-check
python -u solution.py --plan
python -u solution.py --help
```

The default **`full`** preset benchmarks all **28 nontrivial (N,n) cases through N=8**,
including complementary excitations, with five seeds, 10,000 shots per basis, two detuning
realizations and all applicable X-correlator orders. DD/no-DD/ideal produce 420 records.
Both exported entry points are also checked exactly for every **N=2–15, n=0–N**:
133 cases and **266 circuits**, including product boundaries. Larger resource probes extend
through N=90 without density simulation. The software checks include lint, formatting,
protected/generated artifact checks, the full test suite and both notebook executions.

`--preset standard` retains six cases through N=6 and three seeds. `--preset quick` uses
two cases, one seed, 1,000 shots and one realization; its uncertainty is unestimated.
These smaller presets, narrower modes and explicit `--cases`/`--nmax` runs skip broad
software/bonus suites by default. Add `--check` or `--bonus-check` to include them. An
explicit bonus check with focused cases checks those cases in both exported functions.
`--no-check` and `--no-bonus-check` skip those suites in a full run. Explicit model/case
options override preset values; `--fresh` saves a separate benchmark repeat.

Every invocation prints its run index and saves `report.md`, `run.json`, the complete
`terminal-output.log`, stage reports/data, comparison source/circuit snapshots, and a
standalone `submission.py` under `benchmark_outputs/solution_runs/<run-id>/`.
Full runs also save `bonus_validation/report.md`, `results.json` and `results.csv` with
every main/bonus check; failures retain completed rows and their traceback.
The export uses the selected preparation settings. Noise and shot settings belong to local
testing and do not modify the exported constructor. All figures are saved automatically,
under **`figs/solution_runs/<run-id>/`**, including PNG/PDF diagnostic and comparison views
and the analyzer PNG. Matching raw benchmark checkpoints remain under
`benchmark_outputs/runs/<fingerprint>/`. Reports link to the actual saved figures.

Optional reference construction/validation errors are reported with full tracebacks and
receive no score. The run index counts these failures, while unexpected maintained-solver
or shared noise/scoring errors stop the run. The reference source files remain unchanged.
The minimal reference uses a local compatibility guard for the pinned Cirq router's empty
swap-candidate case, including the five-qubit star at D(5,4). It retains the original
constructor body and records the adapter source in comparison provenance. See
[the routing repair](claude/docs/REFERENCE_ROUTING_FIX.md).
The matched DD/no-DD score plot displays 0–2, with boundary markers for clipped means or
SD bars and numeric labels for overflowing means. Full scores remain in the report and
raw data. Comparison reports explain every implementation/DD variant; the same glossary
is in [the run guide](claude/docs/RUN_GUIDE.md#terminal-table).

For narrower runs:

```bash
python -u solution.py --mode benchmark --nmax 6 --seed 42 --shots 2000
python -u solution.py --mode compare --cases 2,1 6,3 15,7
python -u solution.py --mode validate --cases 15,7 --dd-strategy sparse
python -u solution.py --mode diagnose --results path/to/noisy_benchmark_results.json
```

`benchmark` includes validation, analysis and diagnostics; `compare` builds a fresh comparison;
`validate` performs rule checks and exact fidelity through N=16 (structural checks above
that); `diagnose` uses the supplied dataset's recorded model and preparation settings, or
generates six state/circuit views without score data when no dataset is supplied.
Density benchmarks are bounded to N≤10; solution comparison samples noise only through
N=6 and validates larger circuits. Constructor-only `--resource-sizes` probes may be larger.
See [RUN_GUIDE.md](claude/docs/RUN_GUIDE.md) for flags, output details and preservation.

The individual tools also remain available:

```bash
python -u -m claude.scripts.noisy_benchmark
python -u -m claude.scripts.analyze_benchmark_results path/to/noisy_benchmark_results.json
```

CLI noise/preparation overrides reach every applicable stage and enter the checkpoint
fingerprint. The individual benchmark module still supports its legacy explicit settings.
New results go under `benchmark_outputs/runs/<fingerprint>/`. The original historical
report and PNG survive; the historical raw JSON was lost in the documented
[regression-test incident](claude/docs/DATA_RECOVERY_2026-10-24.md), and the user chose to retain
the surviving summaries only. The corrected workflow preserves existing files. Its fingerprint
covers effective noise/preparation settings, calibration, source,
original scoring code, and runtime versions. Matching checkpoints resume; incompatible records
are not reused. A forced fresh run receives a separate repeat directory.

Shot seeds and physical-noise seeds are independent. Paired comparisons use matching finite
seed observations, and the aggregate uncertainty is estimated across paired seed means.
Across-case spread describes different cases, not uncertainty of that aggregate. Infinite or
undefined official scores use explicit JSON statuses and are not silently clipped into finite
averages. A singleton does not estimate uncertainty. Historical data without fingerprints is
clearly labeled legacy.

The noise model is approximate. Native single-qubit gates can temporarily change excitation
number, so detuning inserted between compiled gates can change final leakage. The tutorial
uses the same detuning ensemble for its plotted distribution and displayed score. Density
simulation is bounded to ten qubits because its memory grows as 4^N; structural checks support
larger circuits without constructing huge state vectors.
The default correlator cutoff of four and the selected benchmark cases are local experimental
settings; they do not predict the organizer's hidden grading choices.

## Diagnostic notebooks and saved reports

Both working notebooks now save and display a diagnostic bundle. Their examples reuse an
existing current raw score run when available; they do not silently launch a full benchmark.
The report marks paired comparisons unavailable when no raw dataset is supplied.

```bash
python -u -m claude.scripts.diagnose --benchmark       # six cases, five paired seeds, 10,000 shots
python -u -m claude.scripts.diagnose --results path/to/noisy_benchmark_results.json
python -u -m claude.scripts.diagnose --qubits 4 --excitations 2
python -u -m claude.scripts.diagnose --full-benchmark # all 16 cases through N=8
python -m claude.scripts.check_notebooks             # clean in-memory notebook execution
```

Reports are saved under `benchmark_outputs/diagnostics/D<N>_<n>-<fingerprint>/` with
`report.md`, strict `diagnostics.json`, and three CSV cost tables. All saved figures go into
the repository's **`figs/`** directory: diagnostic PNG/PDF under
`figs/diagnostics/D<N>_<n>-<fingerprint>/`, analyzer plots under `figs/benchmarks/<dataset-hash>/`,
and the surviving original PNG under `figs/historical/`. Reports and notebook displays use the
recorded figure directory. Tests and isolated notebook checks override it with a temporary root.
The diagnostic views are:

| View | What it diagnoses |
| --- | --- |
| Exact state | Fidelity, leakage, global-phase alignment, relative phase and amplitude residuals |
| Distributions | Hamming weights, conditional Z uniformity, ideal/observed X correlators |
| Placement and cost | Actual coupler use, readout proxies, single-qubit overhead and idle time |
| Native schedule | Single-qubit/CZ activity against modeled time, with and without DD |
| Scaling | Gate count, moments, additive error proxy, runtime and unsupported requests |
| Noise sensitivity | Detuning-induced population/coherence errors in a fixed physical ensemble |
| Paired scores | Individual observations, exclusions, paired differences and approximate t intervals |
| Seed convergence | Dependence on replicate count; uncertainty is unavailable at one replicate |

Six figures are available without score data; all eight are available with a completed dataset.
`figs/` is ignored by Git, so generated binaries are not staged by the usual add-all command.
The figures use an explicit rendering canvas and preserve a live notebook's plotting backend.
The JSON records all participating source hashes, noise/calibration settings, runtime versions,
and raw-score dataset identity. CSV coupler endpoints are numeric columns for analysis.
Intervals are approximate for reciprocal scores and conditional on a single synthetic rate map;
calibration-rate uncertainties are not propagated. No plot turns a small simulation comparison
into a hardware-wide DD policy.

## Submission

```bash
python -m claude.scripts.build_submission submission_outputs/submission.py
```

Use the [submission checklist](claude/docs/SUBMISSION_CHECKLIST.md) and review the original
challenge and current upload form for all required supporting material. Upload by hand
after reviewing the form. Nothing commits, pushes, publishes, or submits automatically.

## Teammate integration and repeatable local runs

Work continues on `main`, combining the reviewed workflow with the latest teammate changes
from upstream main. The upstream files under `ryon/` and `toby/` remain comparison references;
the tested canonical implementation remains `claude/dicke_prep.py`. See the
[integration status](claude/docs/MAIN_INTEGRATION.md) and
[run and preservation guide](claude/docs/RUN_GUIDE.md) for local Git checkpoint commands,
teammate comparisons, and artifact retention.

```bash
python -u -m claude.scripts.diagnose --benchmark
python -u -m claude.scripts.compare_solutions
```

The first command saves the complete eight-view report and PNG/PDF under figs/diagnostics/.
The second saves common-model comparisons, raw score/status records, source/circuit snapshots
and PNG/PDF under figs/comparisons/. Comparison invocations use distinct directories.
Tutorial exploration plots also save automatically through save_and_show under figs/notebooks/.
Use that helper for additional matplotlib plots you write. Generated results are local and
Git-ignored; the guide includes a separate artifact archive command. Sparse DD is optional and
can add emitted moments when filling empty slots; the depth cap is checked afterward.

Both benchmark and comparison runs print aligned terminal tables with:
`N n var CZ mom build rules ideal f Zfloor Zbias X E[s] sampled`, grouped by seed.
The columns use the actual native circuits, ideal validation and modeled measurement probabilities.
`Zfloor` and `X` include finite-shot sampling variance. The requested `E[s]` heading denotes an
inverse-mean-penalty proxy, not the mean sampled reciprocal score; the console and JSON record
this definition. See [the derivation and column definitions](claude/docs/TERMINAL_TABLE.md).
