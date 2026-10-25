# Independent upstream comparison review

Review date: October 24, 2026. Read-only review of teammate commit
`d8f148d271aeef552c450af668be169c192bc058`, which adds `ryon/dicke_solution.py`,
`ryon/minimal_dicke.py`, `ryon/judge.py`, and `ryon/test_dicke.py`.

The comparison is against the repaired working version of `claude/dicke_prep.py`,
snapshotted before integration into `reviewer/canonical_dicke_prep.py` with SHA-256
`bcd8dce0d38fd4f40602c4c78ec18c276d4a4d73eb4edaa44c862e47faf6667d`.
The canonical module may subsequently change in the parent integration task.
Upstream's `dicke_solution.py` SHA-256 is recorded in `reviewer/state_resources.json`.

No checkout, Git, notebook, existing report, saved result, or installed dependency was changed
by this review. Probe sources and new evidence are under `/private/tmp/duq-compare/reviewer/`.
No hardware, full benchmark, or full test suite was run.

## Strengths

- Both implementations correctly prepare the complete positive-amplitude Dicke state in the
  tested cases. Upstream's general SCS circuit and its constant propagation each passed all
  excitation counts through N=11. These are independent state-vector checks, including
  relative phase, amplitude, leakage, and normalization rather than Z populations alone.
- Upstream's exact CRy and CCRy primitives are sound. Full-unitary comparisons at angles
  0, pi/7, pi/2, and pi pass, including all control basis states. Its angle convention and
  complement trick agree with the Dicke recursion in
  [Bärtschi and Eidenbenz, Sections 2–3](https://arxiv.org/html/1904.07358v1).
- The first W split is a real gate saving: it uses one CZ because it only needs the known
  preparation input, rather than the full two-qubit Givens unitary. The remaining splits
  retain excitation-preserving Givens rotations. The idea also applies to the first line
  split in the canonical implementation.
- Upstream's sparse echo is an intelligible experimental option: two X pulses in a long
  idle window preserve the full unitary and use fewer single-qubit gates than dense DD.
  A separate three-qubit unitary check with a trailing idle window passed and added exactly
  two pulses without increasing moment count. This is a correctness result, not evidence
  of a hardware score improvement.
- Weighting readout costs by n/N in `dicke_solution.py:50–55` follows the exact target's
  one-qubit marginal probabilities. Canonical currently uses an equal zero/one average.
  This is a reasonable future placement refinement, subject to matched comparisons.
- The general routed SCS can work on connected patches that have no N-qubit simple path.
  A valid four-node Willow star supported exact D(4,2) upstream with 12 CZ gates and
  25 moments, while canonical appropriately raised `NotImplementedError` because its
  general path construction cannot use that graph. Routed SCS could be a fallback.
- NetworkX is a Cirq dependency and is allowed by the challenge's stated import rule.
  Ignoring the final routing permutation is valid for a permutation-symmetric Dicke
  target initialized from all zeros; the pinned Cirq API explicitly returns a circuit
  equivalent up to a final qubit permutation.

## Issues

### Critical — none found in tested state preparation

No incorrect Dicke relative phase, leakage, disallowed gate, invalid listed coupler, or
over-depth circuit was found in the tested upstream cases. This is bounded evidence for
the stated cases rather than a proof for all inputs or a hardware evaluation.

### Important

1. **The upstream bonus entry point depends on a sibling module on `sys.path`.**
   - Location: upstream `ryon/dicke_solution.py:458–466`, specifically `from judge import get_device`.
   - Reproduction: import `dicke_solution`, remove its sibling directory from `sys.path`, then
     call `create_dicke_state_adaptive(3, 1)`. It raises
     `ModuleNotFoundError("No module named 'judge'")`.
   - Impact: copying the solution into a standalone submission, or importing it as
     `ryon.dicke_solution` from repository root, does not provide a reliable bonus entry point.
     The challenge permits Cirq and standard/dependency imports, not a separately supplied
     custom `judge` module.
   - Recommendation: retain canonical's standalone `cirq_google.Willow105.metadata` entry point
     and export path. Keep upstream files intact as provenance/reference files.

2. **The analytical score proxy has the wrong Z shot-noise floor when survival is below one.**
   - Location: upstream `ryon/test_dicke.py:177–201`, especially line 191; displayed as `E[s]`
     at lines 227–228 and 260.
   - Let S be shots, K>0 the in-sector count, C the target sector size, and q_j the conditional
     in-sector distribution. The official statistic simplifies to
     `Z = S/K**2 * sum_j (n_j - K/C)**2`.
   - Conditional multinomial moments give
     `E[Z | K] = S/K * (1 - sum(q_j**2)) + S * sum((q_j - 1/C)**2)`.
     Replacing K by S*f gives floor `(1-sum(q_j**2))/f`; upstream instead uses
     `(1-f*sum(q_j**2))/f`. They coincide only at f=1 or in limiting approximations.
   - Reproduction: N=2, n=1, S=10,000, probabilities `[0.5,0.25,0.25,0]`, so f=0.5 and
     q=(0.5,0.5). Upstream reports floor 1.5. The conditional formula is 1.0000485 after
     averaging over K, and 100,000 independent multinomial draws give official Z mean
     1.00521 ± 0.00450 standard error. This is count sampling, not a noisy circuit run.
   - It also omits finite-shot X-estimator variance and the expectation of a reciprocal
     differs from the reciprocal of expected errors. The value must not be presented as
     an expected official score even after fixing the Z term.
   - Recommendation: retain the repaired official scorer and paired finite-shot analysis.
     If this proxy is imported later, fix the derivation and label it explicitly as an
     approximation, with defined behavior for K=0 / f=0.

3. **The upstream fake calibration is order-dependent despite a fixed seed.**
   - Location: upstream `ryon/judge.py:103–129` and `133–141`.
   - Its random draws are assigned to `list(device.metadata.qubit_set)` and
     `list(device.metadata.qubit_pairs)` without canonical ordering.
   - Reproduction: provide identical metadata in forward versus reversed iteration order
     and call `fake_calibration(1234)`. The maps have 4 different qubit dropout keys,
     19 different coupler dropout keys, and changed rates on 162 common couplers.
   - Impact: results cannot be reproduced from seed alone across equivalent metadata
     representations. They also cannot be compared directly with saved canonical runs
     having a different map. The remote helper draws SQ rates before couplers, whereas
     canonical draws couplers first, so matching its numerical seed is insufficient even
     after sorting.
   - Recommendation: preserve canonical calibration generation, explicit shared maps,
     content fingerprints, and separate noise/shot RNGs.

### Minor and non-blocking limitations

- Upstream `test_dicke.py:285–303,325` defaults its bonus loop to N=20. The organizer's
  correction confirms 2 ≤ N ≤ 15. N=16–20 can remain explicitly labeled stress tests;
  including them in a claimed official bonus aggregate would be misleading.
- The upstream main `time_budget_s` is checked between routed candidates only
  (`dicke_solution.py:422–424`). It does not cap patch selection, logical compilation,
  one route attempt, or final compilation, and there is no final elapsed-time check.
  All selected N≤15 cases here finished far below a minute, so this is a limitation,
  not an observed challenge timeout. Preserve canonical's final time/depth guard.
- `dicke_solution.py:38–47` only adds qubits appearing on a usable edge. Consequently an
  isolated usable qubit cannot prepare even a one-qubit product state in this graph
  builder. `minimal_dicke.py:30–31` deliberately declines all product states. Both can
  legally return `NotImplementedError`, so these are support limitations rather than
  incorrect returned states.
- Upstream `test_dicke.py:133–167,211–255` shares one RNG across detuning and shots and
  consumes it sequentially across variants. Its DD comparison therefore lacks matching
  physical noise draws for the variants and does not provide a paired uncertainty
  estimate. The parent task is carrying out a separate common-model comparison.
- Remote sparse pulses can land in CZ moments on other qubits, while canonical DD is
  confined to existing single-qubit slots. Those choices preserve the ideal state, but
  pulse timing and modeled duration differ. Preserve that distinction in comparisons.
- The upstream files lack many annotations, diagnostics, calibration validations, and
  artifact protections already present in the repaired project. Keeping them as unchanged
  provenance avoids creating a second competing source of truth.

## Resource and state evidence

Uniform full Willow maps, sorted keys, native CZ error 0.0025, SQ error 0.0004,
zero readout 0.005, and one readout 0.01. These are structural comparisons, not
predictions of hidden grading cases or hardware performance. Canonical defaults
use dense DD; upstream defaults use sparse DD. Their no-DD variants have the same
CZ and moment counts as the corresponding rows shown below.

| State | Canonical CZ / moments | Upstream CZ / moments |
| --- | --- | --- |
| D(2,1) | 2 / 5 | 1 / 3 |
| D(3,1) | 4 / 9 | 3 / 7 |
| D(4,2) | 13 / 23 | 12 / 25 |
| D(6,3) | 36 / 53 | 43 / 77 |
| D(8,4) | 71 / 95 | 96 / 168 |
| D(10,5) | 118 / 137 | 165 / 222 |
| D(12,6) | 177 / 179 | 263 / 340 |
| D(15,7) | 280 / 237 | 444 / 472 |
| D(15,8) | 280 / 237 | 444 / 472 |
| D(15,14) | 28 / 21 | 27 / 19 |

At D(15,7), the canonical constructor took about 0.5 seconds and upstream about
6.2 seconds in this environment. Timing depends on the machine and warm caches.
Upstream does have a one-CZ advantage at D(4,2) before the proposed canonical
first-split optimization; canonical wins moment count there. Neither implementation
dominates every resource on every case.

Separate selected bonus calls passed exact state and device checks at (2,1),
(4,2), (8,4), and (15,7). At (15,7), canonical produced 280 CZ / 236 moments and
upstream 444 CZ / 518 moments. The upstream bonus uses its own map iteration and
`objective="moments"`; do not conflate these numbers with the uniform sorted-map
main comparison above.

Checks performed with Python 3.12.15, Cirq/cirq-google 1.8.0.dev20261023221525,
NumPy 2.5.4, CPU complex128, one OpenBLAS thread, and scratch cache roots:

- 150 logical exact states: N=2–11, every n=0…N, both simplify=False and True.
  Minimum fidelity 0.9999999999999973, maximum phase-aligned amplitude residual
  1.11e-15, maximum outside-sector population 1.17e-31.
- 52 upstream compiled exact states: N=2–9, every n=0…N, sparse DD. To bound review
  cost, these use one routed candidate (`n_candidates=0,time_budget_s=0`);
  default options are covered in the next group. Minimum fidelity
  0.9999999999999984; maximum amplitude residual 2.61e-15.
- 40 default-option resource cases: the ten rows above, each with canonical
  dense/no DD and upstream sparse/no DD, all checked exactly and against the
  allowed gate/coupler/device constraints. Maximum amplitude residual 2.09e-15.
- Eight full-unitary controlled-rotation primitive comparisons.
- Eight selected bonus exact/device checks, one star-graph state check, and
  a full-unitary sparse-echo check.
- Edge probes for standalone import, isolated product requests, calibration
  ordering, and the analytical score floor.

Primary evidence files:

- `reviewer/probe_review.py`, `reviewer/state_resources.json`, `reviewer/state_resources.log`
- `reviewer/probe_edge_cases.py`, `reviewer/edge_cases.json`
- `reviewer/bonus_cases.json`, `reviewer/star_graph.json`

The full probe ran in 50.5 seconds. No density-matrix benchmark was run here.

## Recommendations

1. Preserve the repaired canonical module, independent validator, reproducible benchmark,
   artifact persistence, protected original notebook, and standalone export as the main path.
2. Adapt the known-input first split into both W trees and the first line split. Retain the
   general Givens primitive for subsequent uses and all of its phase tests. For an initial
   pair |01>, `Ry_a(2 theta)` followed by `CNOT(a→b)` gives
   `cos(theta)|01> + sin(theta)|10>` with one CZ after native decomposition. The first line
   gate has p=N−1−k and initially a=0,b=1 for 1≤k≤N−1; product-state cases have no split.
   Update the layout's edge CZ weights to include the saving.
3. Add sparse echo as a configurable option within the canonical scheduler, preserve dense
   default pending matched noise evidence, and test full-unitary equivalence, short gaps,
   trailing gaps, complements, gate count, and unchanged moment count. Two X pulses on the
   same otherwise idle qubit cancel; this alone does not establish noise suppression.
4. Retain the four upstream files unchanged as provenance, document which ideas are adapted,
   and let one canonical module drive notebooks, diagnostics, submission, and comparison.
5. Consider routed-SCS fallback and target-weight readout placement as separate future
   improvements with explicit tests; they are larger architecture changes than the two
   local synthesis/scheduling improvements.

## Declined to judge

- Absolute noisy-score or hardware superiority: the local approximation and hidden grading
  settings do not establish it; the parent runs a separately controlled small comparison.
- Hidden choices of (N,n) or correlator cutoff: not disclosed by the organizer.
- Official bonus behavior at N=16–20: explicitly outside the confirmed 2–15 range.
- Performance on all main-task sizes or every dropout topology: finite exact/structural
  probes cannot establish universal coverage; unsupported requests may raise NotImplementedError.
- Changes made by the parent after the saved canonical snapshot: require the requested
  narrow post-integration review.
- Historical lost raw data: the user chose to retain the surviving original report PNG;
  this review neither reconstructs nor reruns that historical experiment.

## Assessment

**Ready to merge? With fixes through selective adaptation.**

The teammate's preparation physics is sound in extensive bounded checks, and its first
known-input split and sparse-echo idea are useful. Keep the repaired architecture and
efficient general line construction, adapt those small improvements with independent
verification, and keep the upstream score/calibration/import behavior out of the canonical
submission and evidence pipeline.

Sources consulted: [Bärtschi and Eidenbenz](https://arxiv.org/html/1904.07358v1),
[Mukherjee et al.](https://arxiv.org/html/2007.01681v2),
[Cirq Givens API](https://quantumai.google/reference/python/cirq/givens),
[Cirq RouteCQC API](https://quantumai.google/reference/python/cirq/RouteCQC), and
the installed pinned-version API docstrings. No external source is used to infer
organizer-specific hidden grading choices.
