# Minimal-reference routing compatibility — October 24, 2026

The user's full run recorded a real optional-reference failure for D(5,4), while
all maintained variants passed and the run continued. The previous change isolated
this error and preserved its traceback; it did not repair the reference's routing.

## Root cause and bounded fix

The original minimal constructor chooses a five-qubit star around a high-degree hub.
Every edge shares its center, so no two swap edges are disjoint. In the pinned Cirq
1.8.0.dev20261023221525 router, an unresolved single-swap tie reaches paired-swap
selection; its empty candidate list then reaches sigma[0] and raises IndexError.
The actual original function and the user's saved traceback both reproduce this.

The comparison adapter now supplies the original constructor with a private Cirq
namespace containing a RouteCQC subclass. Its sole behavioral guard returns None
when candidate swaps are empty, allowing Cirq's existing fallback to proceed.
Nonempty candidates use the original ranking code. Function bytecode, calibration,
region selection, logical circuit, compilation and moment limit remain original.
No process-wide patch, dependency installation, reference-source edit or maintained
physics change is involved. The adapter is hashed and snapshotted in new comparisons,
and the report identifies its use. Old failed-run records remain intact.

Official routing API: [Cirq RouteCQC](https://quantumai.google/reference/python/cirq/RouteCQC).
The private override is tied to the pinned runtime and tested on the actual star case.

## Completed verification

| Check | Result |
| --- | --- |
| Initial regression | Two expected failures, six passing tests before repair |
| Focused tests after repair | All eight pass, including all four nontrivial five-qubit star states and actual scoring/provenance |
| Full suite | 466 passed in 105.09 s |
| Full small-case comparison | All 168 circuits across 28 cases and six variants pass exact-state/native checks; zero reference errors |
| Repaired D(5,4), noisy comparison | Six valid variants, five seeds, 10,000 shots, two realizations: 30 scores, including all five minimal scores; zero reference errors |
| Minimal D(5,4) circuit | 113 CZ, 227 moments, fidelity one within floating-point roundoff |
| Independent review | Twelve nonempty routing probes match base Cirq; six previously valid cases have identical circuits/qubits; copied function state and global isolation verified |
| Quality | Lint/format, four nonpytest hooks, both working notebooks (6/19 code cells) pass; full pytest ran separately |
| Preservation | Original challenge, all four upstream files and earlier recorded outputs remain unchanged |

Independent review: [REFERENCE_ROUTING_REVIEW.md](REFERENCE_ROUTING_REVIEW.md).
The comparison includes both the unchanged reference source and the adapter source
in its fingerprint/snapshots. Existing exception reporting remains active for unrelated
reference failures; unexpected maintained-constructor or shared scoring failures remain fatal.

Saved verification:

- [Complete repair evidence and both comparisons](../../benchmark_outputs/reference_routing/20261025T010027Z-reference-routing/report.md).
- [All 168 exact/native checks](../../benchmark_outputs/reference_routing/20261025T010027Z-reference-routing/full_exact/20261025T010027Z-f843ed964e1a-12c866/report.md).
- [Five-seed noisy D(5,4) result](../../benchmark_outputs/reference_routing/20261025T010027Z-reference-routing/fixed_case_noisy/20261025T010102Z-181c7afb440c-5e54c4/report.md).

All eight new PNG/PDF files are under figs/reference_routing/20261025T010027Z-reference-routing/.
The unchanged maintained solver SHA-256 remains
75f9cad7b8d8c831fa8df43e6bad26336bc52af786993846c4de4c522adf29ed.
The private override matches the exact locked Cirq version; dependency upgrades must
rerun the star regression and recheck the private router method signature.

The user's preceding full run completed in 367.74 s and retains the old reference
failure in its saved log/report. New invocations load the corrected adapter. That earlier
record is preserved rather than rewritten. No hardware, staging, commits, pushes or
attribution metadata changes were performed.
