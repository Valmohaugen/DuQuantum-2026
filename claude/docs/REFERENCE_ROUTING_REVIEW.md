# Independent review: minimal-reference routing repair

Assessment: ready for the parent verification/release workflow. No actionable correctness findings in this scoped review.

The fix matches the root cause in the pinned Cirq 1.8.0.dev20261023221525 source: an empty disjoint-swap candidate sequence previously reached sigma[0]. Returning None follows the existing _route contract and selects its established brute-force fallback. The override signature matches the pinned private API. Nonempty candidates delegate to the original implementation.

The adapted original constructor retains code, defaults, keyword defaults, closure and signature. Its globals are copied, and the private Cirq module differs from the installed module only in RouteCQC. The original card-dealing helper, graph selection and compilation calls remain the same objects. Process-wide RouteCQC class/method identities and reference bytes remained unchanged after all probes.

Independent checks:
- function bytecode/defaults/kwdefaults/closures/signature retained; copied globals and Cirq namespace differ only at RouteCQC
- 12 nonempty ranking/lookahead probes match original exactly; empty candidates return None
- six formerly valid N2–4 cases return identical circuits/qubits before and after adaptation
- all four nontrivial five-qubit-star Dicke states pass exact/native validation
- unmodified original still reproduces D5,4 IndexError, proving no global router patch
- actual six-variant D5,4 comparison completes with zero reference errors; adapter hash/snapshot/metadata retained; no-noise score list stays empty
- unexpected maintained constructor and validation failures still propagate fatally
- process-wide router class/method identities and reference source hash unchanged after all probes

The saved no-noise comparison has six valid resource rows, zero reference errors and no fabricated scores. It includes the adapter hash, source snapshot and reference_adapters disclosure. Its original minimal-source hash matches the unchanged reference file. Construction and exact validation remain independent of the routing workaround.

Declined to judge:
- Compatibility with other Cirq versions: the project locks this exact version; future upgrades require the actual star regression and private-signature review again.
- Broad reference coverage and the full suite: owned by the parent run and intentionally not duplicated here.
- New noisy performance estimates: no scientific simulation was rerun in this review; only pure-state/native checks and the requested no-noise comparison were performed.

Evidence: [evidence.json](evidence.json), [probe log](probes.log).

Actual comparison: [/private/tmp/duq-reference-routing-review/comparison/20261025T010200Z-3a0ab8d9fd78-3dd9d0/report.md](/private/tmp/duq-reference-routing-review/comparison/20261025T010200Z-3a0ab8d9fd78-3dd9d0/report.md)

Verified SHA-256 values:
- `claude/reference_routing.py`: `664e150363a27384defd3a573e83f4348739aa0a037290244692354e28cc1d5c`
- `claude/scripts/compare_solutions.py`: `cdba9d7d8335fb8dfe1cde5ae8bda96e0fcf755a8136daf2f75b3bdcab3d987b`
- `claude/tests/test_comparison.py`: `eae32fcdc206ed4753d79dfef45c77d0ed5552bf76b9a4671839da5741eed668`
- `claude/dicke_prep.py`: `75f9cad7b8d8c831fa8df43e6bad26336bc52af786993846c4de4c522adf29ed`
- `ryon/minimal_dicke.py`: `0057bfcfa0c20e9743beebd929ea2735112035c8ebb95cbac0d124f018756a3f`
- `ryon/dicke_solution.py`: `6871a7261e2a93a10f1eff415807b29595868355d71b9f5b03137f914605eeb5`
- `Google Quantum AI Challenge.ipynb`: `ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1`
