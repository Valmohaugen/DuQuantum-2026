# Final independent integration review

October 24, 2026. Read-only review of the integrated DuQuantum implementation after
the additive upstream fast-forward to `d8f148d` and final review fixes.

Reviewed source hashes:

| File | SHA-256 |
| --- | --- |
| `claude/dicke_prep.py` | `b47ad0891e8970cd2f3732ce117b8a2beef9efc4b993b6cbc06425c33e848d5a` |
| `claude/notebook_figures.py` | `fd1965c2fd6b650df6c66bea07bcec3c6d5d3253c5dc84ce831ffeaea42fd0bb` |
| `claude/scripts/compare_solutions.py` | `14e5375d7c50af6beabde24942efdb8042aab1de61d4eaf1b9e543a9626fd4ca` |

The reviewer changed no repository file, Git state, dependency, protected notebook,
or pre-existing output. New scratch evidence is under `/private/tmp/duq-compare/reviewer/`.
No hardware, full test suite, or duplicate density-matrix benchmark was run by this reviewer.

## Strengths

### Preparation physics and scheduling

- The one-CZ first split is applied only where its known input is valid. On the line,
  the first gate has p=N−1−k, with initial a=0,b=1 for 1≤k≤N−1. On the W tree, the
  root starts in 1 and its first child in 0. `Ry_a(2 theta)` followed by `CNOT(a,b)`
  gives the required positive amplitudes; all subsequent Givens gates retain their
  full behavior. Zero/full product states have no line split. The module derives
  the identity and checks its zero, transfer, and Bell-state limits.
- The native edge-count model correctly subtracts exactly the first saved CZ.
  Independent probes compared actual CZ counts on every line edge with
  `line_edge_cz_counts` for every excitation count through N=10.
- The routed fallback reuses the same verified logical preparation, routes it onto
  exactly N output nodes, recompiles SWAPs to full CZ/PhasedXZ operations, and
  retains the outer time and moment guards. It is bounded by configuration and
  can be disabled with `max_routing_qubits=0`.
- The routing-permutation argument is correct. All qubits begin in zero; routing
  transports the entire logical preparation, including initial X operations.
  Its final permutation bijects the set of weight-k strings, each with the same
  amplitude. Consequently it leaves the Dicke target unchanged. Complementing
  all output qubits afterward also commutes with that permutation. The chosen
  patch introduces no ancilla.
- Sparse DD inserts two X pulses only inside a detector-verified uninterrupted
  gap on that qubit. Operations on other qubits commute with the pair, so the
  full arbitrary-input unitary is preserved. Dense DD remains the default.
  The final documentation correctly distinguishes virtual slots from emitted
  moments: filling a previously globally empty slot may increase depth, after
  which the constructor checks the challenge cap again.

### Comparison and evidence pipeline

- All candidates use one supplied calibration, one density-noise implementation,
  the same shot/correlator settings, and domain-separated seed streams. The code
  does not import the upstream analytical score proxy or its order-dependent
  fake calibration generator into the evidence pipeline.
- Native gate, routing, qubit-count, device, and bounded exact-state validation
  precede scoring. Unsupported cases remain explicit. Large cases are exact-
  checked through the stated limit and otherwise structurally checked; density
  simulation remains bounded to six qubits in the comparison.
- Each invocation gets a unique result and figure directory. Source snapshots,
  source/runtime/calibration identities, native circuits, output-qubit coordinates,
  raw score/status observations, resource CSV, score CSV, Markdown, PNG, and PDF
  are persisted. An empty zero-weight circuit now still records its N output qubits.
- The report calls finite-shot scores exploratory, retains nonfinite statuses,
  exposes paired exclusions, and describes approximate t intervals for reciprocal,
  potentially heavy-tailed scores. It makes no universal hardware/DD claim.
- The final score plot uses an explicitly labeled symlog difference axis while
  retaining the outlying observations and intervals. Independent numerical checks
  confirmed the complete interval range is inside the axis limits.

### Notebook figure retention and integration

- Tutorial figure displays now save both PNG and PDF without forcing a backend.
  Hash-addressed views preserve changed slider states and deduplicate unchanged
  views. The manifest records format hashes and the saving implementation.
- The repaired helper verifies existing files, atomically regenerates missing or
  corrupt formats, updates the existing manifest entry, preserves the original
  `saved_at`, and records `restored_at`. The undamaged format is preserved.
- The README documents the integrated source of truth, repeatable comparison and
  diagnostic commands, figure locations, explicit helper use for new plots,
  optional sparse DD, and the preservation guide.
- All four upstream files remain byte-identical to the independently reviewed
  commit copies. They are documented as provenance references, outside the
  maintained implementation's Ruff scope. This does not certify the upstream harness.

## Issues

### Critical — none

### Important — none remaining after the review fixes

The following findings were corrected and independently rechecked:

| Finding | Final resolution and evidence |
| --- | --- |
| Dedup skipped deleted PNG/PDF files | Five scratch scenarios passed: missing PNG, missing PDF, both missing, corrupt PDF, and corrupt PNG. File signatures/hashes, unchanged-format preservation, original timestamp, restoration timestamp, dedup, and changed-view history were checked. |
| Empty circuit lost its output-set identity | A zero-weight comparison saved two output coordinates for each hybrid variant; reading the empty circuit JSON with those coordinates reconstructed a four-dimensional state vector. |
| Sparse DD could be described as depth preserving | The docstring and README now state that globally empty virtual slots can become emitted moments; outer depth validation remains in place. |
| Large reciprocal-score interval flattened smaller differences | The regenerated plot uses labeled symlog scaling and retains every interval endpoint. Numeric plotted limits contain the complete interval range −1080.30…1727.11. |
| Import description omitted newly used NetworkX | The module docstring now identifies the Cirq NumPy/NetworkX dependencies. The direct pin, runtime provenance, and submission import allowlist include NetworkX. |

### Minor — no required follow-up

Tree selection still uses a heuristic error/depth proxy, as it did before. The bounded
routing fallback need not be globally optimal, and sparse DD is an experimental option.
These are accurately scoped algorithm choices rather than correctness failures.

## Verification evidence

Independent focused physics probes, run against an immutable integration snapshot:

- **195 exact line states:** N=1–10, all n=0…N, each with off/dense/sparse DD.
  Every actual line-edge CZ count matched the placement model.
- **18 routed branching-tree states:** valid six- and eight-node Willow trees with
  branching and no Hamiltonian path; n=2, half filling, and complementary filling,
  each with off/dense/sparse DD. Exact states, physical couplers, native gates,
  output sets, and device validation passed.
- **120 arbitrary-input unitary checks:** 40 random native operation streams,
  each with off/dense/sparse scheduling, compared as complete four-qubit unitaries.
- Separate star checks covered every n=0…4 with dense and sparse DD, including
  empty/full products and excitation complements.
- A real CLI run with `--cases 2,0 2,2 --no-noise --shots 40 --seeds 1` succeeded,
  retained explicit unsupported minimal-product cases, and saved both figure
  formats plus JSON/CSV/Markdown entirely under scratch roots.
- After final documentation changes, the preparation module's executable AST
  with docstrings removed was identical to the module used by those probes.

Physics evidence files are `reviewer/probe_integrated.py`,
`reviewer/integration_probes.json`, and `reviewer/integration_probes.log`.
Restoration evidence is `reviewer/figure_repair_probes.json`. The physics probe
completed in 3.7 seconds; no full-suite run was duplicated here.

The final real comparison was inspected at:

`benchmark_outputs/comparisons/20261024T221541Z-b98ebfe737a7-11ac8b/`

- 42 resource rows: 41 valid and one explicit unsupported minimal D(15,7).
- 84 finite-shot observations and 28 paired summaries.
- 15 Python source snapshot files, covering every recorded source hash.
- 41 native-circuit JSON files; every valid row records N distinct output coordinates.
- Two PNG and two PDF figures under the matching `figs/comparisons/` directory.
- Recorded preparation hash matches the final module hash above.
- Lowest reported exact fidelity is 0.9999999999999789, consistent with accumulated
  floating-point error under the validator's stated tolerance.
- Both comparison figures were visually inspected. The final symlog figure was
  rechecked after regeneration; axis bounds retain all confidence intervals.

The final standard diagnostic report completed at
`benchmark_outputs/diagnostics/D6_3-42ba04fe7b0c/report.md`.
The final JSON and figure directory were checked: all eight named PNG/PDF views
exist after the final source fixes. The coordinator
owns the full 399-test, pre-commit, notebook-execution, and export quality gate;
this reviewer does not claim to have rerun those checks.

The protected original challenge notebook was rehashed and remains
`ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1`.

## Recommendations

Complete the coordinator's final quality gate and use the new comparison and
diagnostic commands for future local runs. Retain dense DD as the default unless
broader evidence supports a different policy. Keep the upstream source copies,
historical artifacts, and unique new run directories as separate provenance.
No additional implementation change is requested by this review.

## Declined to judge

- Universal hardware score superiority or optimal DD choice: local approximate
  noise models, one synthetic rate map, and a small seed set cannot establish it.
- Hidden main-task sizes or correlator cutoffs: the organizer has not disclosed them.
- Official bonus claims above N=15: those are additional stress cases only.
- Global optimality of placement, routing, or moment count: heuristic algorithms
  and bounded cases do not establish an optimum.
- Reconstructing lost historical raw data: explicitly outside scope; no such run
  was repeated or overwritten by this review.
- The full-project quality gate: the coordinator is executing it separately;
  this independent review provides focused evidence without duplicating it.

## Assessment

**Ready to merge? Yes, for the local integration reviewed, subject to the coordinator's
final project quality gate. No GitHub publication is authorized or performed.**

The integrated changes preserve the tested physics, introduce the one-CZ saving
under its correct known-input invariant, and extend topology support with a bounded
verified fallback. The comparison and notebook persistence paths retain concrete
reviewable evidence, and all actionable issues identified in this final review are
resolved. No remaining code finding blocks the local handoff.
