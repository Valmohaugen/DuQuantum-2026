# Optimized synthesis verification — October 24, 2026

Both useful candidate ideas were integrated with closed-form angles: a four-CZ replacement
for each eligible first Givens/MUX pair, retaining the rest of the pruned stage, and a
five-CZ D(4,2) square selected only when its calibration cost is competitive. The downloaded
81 approximate block tables and square fit constants are not shipped. Existing first-split,
complement, DD, routing, timing and moment-limit protections remain in place.

## Verification

| Check | Evidence |
| --- | --- |
| Initial feature regressions | 17 expected failures before implementation, then all passed |
| Exact kernel, square layouts/fallbacks and consumer checks | 170 physics tests and 72 consumer tests passed before final broad gate |
| Independent mathematical audit | Exact symbolic four-CZ and square identities; 152 full logical states through N=16, worst amplitude residual 5.26e-16 |
| Independent implementation review | 152 old-sequence checks, 304 edge-count checks, 216 scheduled-state probes, worst amplitude residual 5.78e-15; square-cost enumeration/fallbacks pass |
| Compatibility regressions | Legacy-data and configured bonus-export failures reproduced, fixed and independently rechecked |
| Final complete suite | **450 passed in 102.19 s** |
| Final pre-commit | All five hooks passed |
| Notebook execution | solution: 6 code cells; tutorial: 19 code cells, executed in memory with temporary artifacts |
| Current-source evidence | 64 resource rows, 240 comparison score records, 90 benchmark records; all source hashes/links and 25 images verified |
| Preservation | All 709 pre-existing result/figure/reference/original notebook files byte-identical to pre-integration snapshot; Downloads source unchanged |

Review details: [mathematics](OPTIMIZED_SYNTHESIS_AUDIT.md) and
[implementation](OPTIMIZED_SYNTHESIS_REVIEW.md). Derivation: [exact synthesis](OPTIMIZED_SYNTHESIS.md).
No correctness findings remain. The complete software gate is recorded in
/private/tmp/duq-optimized-integration/final-gate.log; targeted regressions and notebook
logs are in that same directory. Supporting exact certificates are also retained beside
the final matched comparison manifest below, without adding a runtime dependency.

## Matched comparison and resource improvement

All comparisons use calibration seed 1234, identical physical noise assumptions, 10,000
shots per basis, correlator orders through six, and seeds 1–5. Each compares three current
DD variants to one preserved baseline. The old maintained baseline retains its dense DD
default; the downloaded baseline retains its own sparse policy, and the corresponding
current sparse comparison uses the same eight-slot threshold. These policies are treatments,
not assumed identical pulse sequences. No case above N=6 receives a density-noise score.

| State | Previous maintained CZ / moments | Downloaded candidate CZ / moments | Current CZ / moments |
| --- | ---: | ---: | ---: |
| D(4,2) | 12 / 21 | 5 / 9 | **5 / 9** |
| D(6,2) | 26 / 41 | 18 / 31 | **17 / 29** |
| D(6,3) | 35 / 51 | 33 / 50 | **29 / 43** |
| D(8,4) | 70 / 93 | 68 / 89 | **61 / 81** |
| D(15,7) | 279 / 235 | 274 / 235 | **258 / 223** |

All listed states passed independent exact preparation and device-rule checks. These are
the requested calibration's results; a costly/missing square uses the general path and
non-path connectivity can require routing overhead. Primitive and fallback tests cover these.

Under the dense policy, mean modeled correct-weight Z probabilities across five seeds changed
from 0.93268→0.96105 for D(4,2), 0.86635→0.89965 for D(6,2), and 0.83417→0.85502 for D(6,3).
These are observed-sector probabilities, not quantum fidelity. Finite sampled scores need
separate interpretation: current-minus-old aggregate score difference was −0.01404 with an
approximate 95% paired t interval [−0.07845,0.05037]. For current sparse versus the downloaded
baseline, the difference was −2.77057 with interval [−13.1540,7.61289], strongly affected by the
small two-qubit reciprocal-score outliers. Five seeds do not establish an overall score
winner. No hardware-wide advantage or DD preference is inferred.

The mathematical gate savings and noiseless correctness are established. Noise-score
conclusions remain conditional on the stated finite synthetic model and limited replicates.

## Saved current artifacts

- Complete diagnostic/run index:
  [report](../../benchmark_outputs/solution_runs/20261024T233528Z-bc30a1d0/report.md).
- Raw 90-record benchmark is linked by that run's run.json and terminal log.
- Final matched-run manifest:
  [matched_runs.json](../../benchmark_outputs/optimized_integration/final/20261024T233654Z/matched_runs.json).
- Against previous maintained solver:
  [report](../../benchmark_outputs/optimized_integration/final/20261024T233654Z/before/20261024T233654Z-c5d833e4250d-2f2d01/report.md).
- Against downloaded test_sol.py:
  [report](../../benchmark_outputs/optimized_integration/final/20261024T233654Z/reference/20261024T233715Z-889892105db2-f88ceb/report.md).

The exact before/reference report paths are authoritative in matched_runs.json, alongside
verification.json and certificates/. Each comparison preserves source snapshots, individual
score statuses/records, native circuits and output qubits. All eight diagnostic PNG/PDF pairs,
two comparison PNG/PDF pairs per baseline and the analyzer PNG are saved under figs/.

The pre-integration snapshot is outside the checkout at
/Users/valentine/.Codex/backups/DuQuantum-2026/2026-10-24T231953Z-pre-optimized-blocks/.
It contains 1,383 workspace files, a verified SHA-256 ledger, tracked diff and source reference.
Historical raw-data-loss disposition remains unchanged; missing 240 records were not reconstructed.
Everything remains local and unstaged on codex/repair-diagnostics. No commits, pushes, remote
writes, hardware jobs, original-challenge edits or upstream-reference edits were performed.
