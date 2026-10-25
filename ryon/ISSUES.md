# Open issues: ryon/toby_sol.py score

Shared work queue for anyone (people or agents) improving `ryon/toby_sol.py`. Claim an issue by
setting its status to `in progress (<name>)` in a commit, and pull before you start. Close it by
moving it to **Done** with the result and the commit hash.

**Metric.** `python fast_eval.py --seeds 0 1 2` (N = 2..8, n <= N/2, 3 fake calibrations) prints
E[s] per case and the total. It uses the same noise model as `test_dicke.py` but runs about 10x
faster. Score per case is about 1 / (1/f - 1/C + X): f is the in-subspace probability after readout
error, so it moves almost one-for-one with fidelity, and the X term only matters for n near N/2.

**Compute.** One CPU per shell. Inside the Slurm job, `srun --overlap -N1 -n1 -w <node> ...` runs
a worker on another node of the allocation (16 nodes x 1 CPU).

Baseline at 0dc262c: total 16.615. Current: **17.458** (3 seeds, N = 2..8). Bonus (N <= 15): 38.30.

## Open

### BR-108. Merge checked circuit pools without overwriting concurrent artifacts
Status: full 56-case verification passed at 43.2219421632
`research/bonus_portfolio_20261025/merge.py` reconciles the frozen 42.353
portfolio with band/terminal-decoder enumeration and small state brickwork
fits. Every accepted circuit passes independent complex128 amplitude/phase,
native gate, qubit-count and Willow device checks. The frozen standalone
`portfolio_submission.py` returns explicit native moments; no online fitting.
The first merge contains 22 accepted changes. Later refined band results
are available and will be reconciled at the next merge.

### BR-109. General complex single-qubit synthesis and reusable path decoders
Status: checked numerical kernel; bounded decoder experiments in progress
Prior searches restrict intermediate states to real amplitudes (CZ + Ry).
`research/bonus_portfolio_20261025/complex_fit.py` allows Ry and Rz at every
local slot and fits all isometry columns with a common global phase. Its
states, single-state gradients and coherent-column gradients match independent
Cirq simulation and finite differences. A bounded four-CZ D(4,2) search over
28 square-topology classes found no exact circuit; that is negative search
evidence, not a lower-bound proof.
`path_decoder.py` is fitting complete unary-to-Dicke decoders for five sites
(r=0..5), on a path, using both real and complex local gates. The real search
has reached 33 CZ / 53 moments from 35 CZ / 55 moments. These can terminate
longer cascades without changing their prefix or straight input registers.

### 10. Trajectory / realistic-noise check of the new pruned patches and lines (N = 9..16)
Status: open, suggested owner: toby (has the trajectory simulator in eval/ and the ZZ / coherent-CZ models)
fast_eval can't reach N >= 13 and has no crosstalk. Compare toby_sol @ HEAD (pruned patches for k >= 3,
`prefer_synth`) against @ a26041d on N = 9..16 with ZZ crosstalk and coherent CZ errors. Pruned circuits
reuse the same few couplers many times (up to 9 CZs on one pair), so check coherent-error accumulation.
If they lose under coherent errors, report the case list and set `prefer_synth = False` for those.

### 11. Pruned line halves for the ladder at N >= 17
Status: in progress (ryon session, claimed 2026-10-25 01:35). Running on the cluster: half isometries
for a = 7, 8 (fallback for N = 13..16 when no whole-state line fits) and a = 9, 10 (N = 17..20),
warm-started from the line plan of each half (`benchmark_outputs/synth/search_half_warm.py`), with
windowed prune so depth never grows. Results go into `halves` after an A/B with `ab.py`.
Path runs cover N <= 16 only (state vector 2^N per refit). For N = 17..20 the ladder is still used.
Run `benchmark_outputs/ex/gpar.py`-style pruning on the half isometries (unary -> D(a, l) for all l,
target = (inputs, outputs)) on a path, starting from `half_ops`, and install into `halves`.

### 12. W states below 2N - 3 CZ
Status: open, unassigned (research)
Whole-state pruning never removed a CZ from the W trees (N = 4..12). Is 2N - 3 optimal for CZ + 1q gates?
A proof or a counterexample (e.g. fit random 2N - 4 CZ sequences on trees / paths, many restarts) settles it.
W cases are about 40 % of the small-N score, so even one CZ matters at N >= 8.
Evidence (ryon): random CZ sequences on a 2x2 / 2x3 patch with random restarts never fit W(4) with 4 CZ
(28k tries) or W(5) with 6 CZ (19k tries), while 2N - 3 fits in a few tries. Likely optimal; low priority.

### 9. Whole-state CZ pruning for every (N, k), N = 7..12 (primary score)
Status: in progress (ryon session, Slurm sweep running; please don't duplicate, add footprints instead)
Same idea as BR-105, applied to the hardware problem: build toby_sol's circuit inside a grid
footprint (2xL ladder, 3-row snake, near-square), rewrite it as the real CZ + Ry ansatz, then delete
one CZ at a time and refit against the final state only; when stuck, insert a cancelling CZ pair on
a footprint edge. Scripts: `benchmark_outputs/ex/gprune.py` (serial) and `gpar.py` (32 deletion
trials in parallel per step), results `benchmark_outputs/ex/out/g*_N_k_*.json` (same keys as the
patch installer). `ex_sol.py` there is toby_sol with these patches swapped in, for A/B in fast_eval.
First 40 s of search, CZ counts (current toby_sol in brackets): (7,3) 21 [26], (8,3) 26 [29],
(8,4) 24 [43], (9,3) 34 [50], (9,4) 45 [63], (10,3) 40 [59], (10,5) 57 [85], (11,3) 46 [68],
(12,3) 56 [77]. fast_eval N = 7..8, 3 seeds: (8,4) 0.675 -> 0.809, (7,3) 0.840 -> 0.872.
k = 2 and k = 1 circuits don't prune at all from the toby_sol start (W uses 2N - 3, k = 2 uses
4N - 9); a different start (over-parameterised random brickwork, then prune) is needed there.
A complex Rz Ry Rz ansatz did not beat the real one on (5,2) 11 or (6,3) 12.
Installed (toby_sol `patches`): (7,3) 20, (8,3) 26, (8,4) 22, (9,3) 33, (9,4) 36 CZ. Per case, 3 seeds:
(7,3) 0.840 -> 0.888, (8,3) 0.824 -> 0.843, (8,4) 0.675 -> 0.845, (9,3) 0.724 -> 0.779, (9,4) 0.607 -> 0.734.
Total N = 2..8: 17.199 -> 17.435. New knob `prefer_synth`: for k >= 3 a synthesised patch/line that fits
skips the line/ladder builds (estimate_error was picking the ladder over the better (8,3) patch).
Pruned circuits only use the edges of one Hamiltonian path of the footprint (D(8,4), D(9,4)), i.e.
they are line circuits with repeated CZs on the same pairs. So toby_sol now also has a `lines` table
(cz sequence on path positions), placed with best_path like the line construction: works for any N
without needing a grid block. The 3-row runs win because their start is the line construction on a
snake; the ladder start (2xL) stalls. Path runs for N = 7..16 are running.
Also in f1f5bba: `bias_tree` grows W trees charging readout skew (Zb), (N,1) N = 3..10: 9.039 -> 9.084.
(10,3) 59 -> 38 CZ patch, 0.676 -> 0.776; (10,5) 85 -> 43 CZ line (first `lines` entry), 0.470 -> 0.677.
Next (me): install N = 10..16 path/patch winners as they converge; brickwork-start pruning for k >= 3.
k = 2 from an over-parameterised brickwork start on 2-row ladder footprints (toby): negative. Greedy
single-CZ deletion gets stuck far above toby_sol: (6,2) 42 -> 17 CZ (toby_sol 15), (7,2) 80 -> 61 (19); (8,2) and
(9,2) brickwork starts with 11-12 layers didn't reach an exact fit. Released; script research/toby_offline/k2_prune.py.

### BR-101. Exact Clifford refits before depth compilation
Status: measured (bonus research, isolated files)
`research/bonus_depth_20261024/clean_cliffords.py` fixes near-Clifford fitted
rotations to exact multiples of pi/2, then refits every remaining angle against
all coherent input columns. The aim is to expose commutation and cancellation
that numerical residuals in the current SCS tables may hide. No maintained
constructor changes are claimed. Acceptance: column error < 1e-10, then full
56-case native/device/state validation and recorded depth score. Result:
all accepted blocks have column error below 4e-15, but total bonus score is only
39.4903307292 versus 39.4452746282. Native commuting-CZ rescheduling saves one
additional moment on (15,7), with no change on (8,4), (10,5), or (12,6). GitHub's
unauthenticated issues endpoint still returns 404; local queue is authoritative
for this coordination note.

### BR-102. Warm topology growth for two-row coherent halves
Status: precision verified (isolated bonus experiment; overlaps fat-ladder layout)
`research/bonus_depth_20261024/grid_half_5_3.json` currently holds a coherent
(5,3,0) decoder with **19 CZ, depth 34** versus 27 CZ and depth 47 at start.
Its cells follow a snake path on a 2x3 patch with one missing corner; final three
unary count qubits occupy the boundary row. Every r=0..3 input maps to D(5,r)
with one common global sign (column error 1.85e-8 before final precision refit).
The search inserts cancelling CZ pairs on unused grid edges and allows
intermediate depth increases while retaining the best depth. The shared
constructor has not been edited; table may be useful to the fat-ladder work.
Final tables: (5,3) 19 CZ / 34 moments; (6,3) 26 CZ / 44 moments;
(7,3) 31 CZ / 55 moments. All r=0..3 columns pass to <3e-15 with
one common phase. `grid_submission_v2.py` passes all 56 bonus cases at
41.8172105916. The first export, `grid_submission.py`, scored 41.5087032261.

### BR-104. Actual expected reciprocal score for a calibrated grid construction
Status: measured at D(10,3), three paired calibrations
`grid_hardware_probe.json`: mean E[score] 0.68514 -> 0.77570, with gains
+0.09496, +0.08875, +0.08795. Each score averages 4096 repetitions of
10,000 shots per basis from the local density model, two detuning realizations,
and all X orders. The sufficient-statistic scorer agrees with the original
notebook (`grid_score_validation.json`), and the calibrated selector chooses
43 CZ / 41 hardware moments on all three seeds (`grid_hardware_selector_checks.json`).
These are local model results. The 19-CZ half is available for integration.

### BR-105. Global state-only depth search escapes the ladder-isometry cost
Status: complete-suite validation and paired D(8,4) hardware-model checks passed
`global_grid_8_4.json`: **25 CZ / 26 moments** as emitted before final compiler
and commutation passes; complete constructor is **25 CZ / 25 moments**, versus
49 CZ / 43 moments. Full complex128 state error 1.3e-15 and Willow native/device
validation pass (`global_grid_8_4_independent.json`). Unlike a half-isometry fit,
the optimization constrains only the final pure state, while alternating topology
growth with pruning and preserving the best depth. `grid_submission_v3.py`
passes all 56 cases at **42.3530245451**, including this new patch. The local
three-calibration mean E[score] for D(8,4) is **0.68164 -> 0.84200**;
hardware schedule is 46 -> 27 moments, 49 -> 25 CZ. Each score uses 4096
Monte Carlo repetitions of 10,000 shots, two detuning realizations and all X
orders (`global_hardware_probe.json`). No shared constructor edits.

### BR-106. Direct vector residuals and native full Jacobians for large cases
Status: measured without improvement in first two bounded fits
The first global searches gave (9,4) 60 -> 57 moments and no improvement on
(10,5) in their bounded runs. `residual_kernel.c` computes the full forward
state Jacobian; its states and derivatives match NumPy and finite differences
at N=3,5. `residual_fit.py` uses nonlinear least squares rather than a scalar
squared-overlap objective. New runs insert four cancelling CZ pairs before
pruning, so they do not spend the entire first pass in the old topology.
Outputs carry the `_gn` suffix and are excluded from candidate exports until
they have strict state/native validation. First results: (9,4) stays at 60
moments and (10,5) stays at 69, so the scalar-overlap search currently wins.
These bounded experiments do not establish lower bounds. The score target
remains 45.

### BR-107. State-only portfolio for higher score gain per removed moment
Status: running serially on the existing compute session
`run_global_portfolio.py` targets (7,3), (8,3), (9,3), (10,3), (11,3),
(12,3), 180 seconds per search. These use the new routed half circuits as
warm starts, then constrain only the final state. `global_portfolio_run.json`
records completed cases; a running status file alone is not proof of a live
process. The explicit native-moment cache, `grid_cached_submission.py`, passes
all 56 cases at 42.3530245451, with maximum constructor time 0.076 s in the
complete exact-state/native/device validation run. Its main entry point also
includes the globally synthesized (8,4) patch; calibrated k=3 half selection
remains in the separate experimental `grid_hardware_candidate.py`.

### BR-103. Compressed binary Schmidt labels
Status: exploratory
A three-qubit binary-to-Dicke decoder was fitted with 7 CZ (unary uses 8).
The first five-qubit, four-column binary-label search at 33 CZ did not converge
exactly (best infidelity 0.00134); those fitted angles are not a valid candidate.
Files: `research/bonus_depth_20261024/binary_decoder.py`,
`binary_decoder_3.json`, `binary_5_3_0_20.json`.

### 1. Short CZ circuits on grid patches for small (N, k)
Status: in progress (ryon session)
`synth.py` fits CZ + Ry circuits exactly and prunes CZs. (4,2) has 5 CZ and (5,2) has 11 CZ
(the line versions use 5 and 14). (6,2) has 14 and (6,3) has 12 on a 2x3 patch. Next targets
and the ladder CZ counts to beat (toby's ladder, now merged): (7,2) 19, (7,3) 32, (8,2) 23,
(8,3) 41, (8,4) 49. The search script also warm-starts from the ladder circuit on its own grid
footprint (row 0 = left half, row 1 = right half).
Random starting sequences don't converge exactly at N >= 7. What works there: take the line
circuit on a Hamiltonian path of the patch, convert it with `synth.from_ops` (the leftover Z
layer becomes the patch's `zset`), insert cancelling CZ pairs on patch edges, perturb, polish,
then prune. (7,2) went 22 -> 18 in about 3 minutes this way. Pruning the ladder circuit itself
didn't help (its footprint has no spare edges). What converges reliably at N = 7: a random
sequence that's heavily over-parameterised (L = 90 for (7,3) fits exactly in under a minute),
then `synth.prune(..., window=4)`, which re-randomises only the angles near the removed CZ.
Shapes to try: 2x3, 2x3+1, 2x4, 3x3 minus a corner. Rank finalists with `fast_eval`, not by CZ
count alone, because depth also costs idle decoherence.

### 7. Synthesised ladder halves
Status: in progress (ryon session)
Each ladder half maps |0^(a-l) 1^l> to D(a, l) for every l in range. `toby_sol.halves` holds
synthesised versions on a path, keyed (a, min(k, a), l_min); `synth.py` fits them with
target = (inputs, outputs). Path results so far: (4,3) 12 (line 18, installed), (3,3) 8 (line 9),
and (3,2) 6, (4,2) 10, (4,4) 21 (equal to the line), (5,2) 15 (line 14). The (3,3) one scored
worse than the line in simulation despite one CZ fewer (fully sequential, deeper), so only
install a half after `fast_eval` confirms it helps.
(4,4) 18 (line 21) is neutral in A/B (+0.006 on (8,4), -0.005 on (9,4)): the synthesised
circuits are nearly fully sequential. Rule of thumb from the noise model: at N = 8 one extra CZ
layer costs about as much as 2-3 extra CZs (idle T1/T2 on every qubit), so synthesis has to
watch depth too. `search_brick.py` (benchmark_outputs/synth) starts from brickwork layers of the
shape's edge colouring and minimises depth first, then CZ count. Use `ab.py <table> <key>
<cases> <seeds>` to A/B a table entry before installing it.
Still to beat: (5,3) 27, (5,4) 35, (5,5) 38, (6,2) 18, (6,3) 36, (6,4) 49, (6,5) 57, (6,6) 60.

**Fat ladder** (in progress): give each half 2 rows, with its k register qubits in the row next
to the rungs, then compose split + halves into one patch entry (exact, checked numerically).
A 2x3 patch took (6,3) from 33 to 12 CZ, so 2-row halves could do the same for (6,2), (6,3)
and (5,3) and help (10..12, 2..3). The first try, (8,2) from two 2x2 halves, is 25 CZ (ladder 23),
so only worth it when the 2-row half beats the path half.

### 2. Evaluate larger N
`fast_eval` stops at N = 8, but the judges' N range is unknown. Add N = 9..12 (density matrix
size 4^N, so N = 12 is about 256 MB) with fewer seeds, so changes aren't tuned to small N only.

Data (toby, trajectory simulator in eval/, same noise model family, expected score with max_correlator_size 4):
N = 2..16 is covered on 10 notebook calibrations per round (44 instances, includes N = 14, 16 at n = 1, 2, 4, N/2).
Spot checks for toby_sol @7e7133a, 1 calibration, 40 trajectories: D(18,2) 0.579 (63 cz), D(18,9) 0.239 (329 cz),
D(20,5) 0.205 (275 cz), D(20,10) 0.207 (415 cz); combined_sol and halves_start_sol build the same circuits there.

**Correlator size.** `fast_eval` sums X correlators up to weight N; toby's evaluator stops at 4.
The judges' `max_correlator_size` isn't stated. With N, the X term dominates at n ~ N/2 for
N >= 10 (for example (11,5) X = 0.90 of a 2.5 denominator), so the choice changes how much depth
matters there. Worth reporting both.
Both sizes now reported (toby, 10 fresh calibrations, 44 instances N = 2..16, expected score summed):
preliminary submission 34.40 (K=4) / 32.45 (K=N); ladder_sol v1 36.39 / 34.44; current toby_sol @a26041d
36.61 / 34.68, i.e. +2.20 +- 0.08 at K=4 and +2.23 +- 0.08 at K=N over the preliminary file. The ranking
and the gain don't depend on the correlator size; n >= 2 gains +12.6% at K=N.


### 3. Better n >= 2 construction for N >= 9
Partly done: toby's two-half ladder (toby/ladder_sol.py) is merged into toby_sol and chosen per
case by `estimate_error`. Its selector is crude, but an oracle that always picks the best
simulated candidate gains only +0.006 over N = 4..8 (5 seeds), so it's not worth replacing.
The line split-and-cyclic-shift costs about 5 CZ per flagged gate and uses only a path. Options
to evaluate: a grid-native layout (shorter paths between the SCS blocks), divide-and-conquer
(Aktar, Bartschi, Badawy, Eidenbenz, IEEE TQE 2022), and the short-depth 2D construction of
Bartschi and Eidenbenz (arXiv:2207.09998).

### 4. Noise-model realism
The harness has no ZZ crosstalk, leakage, coherent CZ phase errors or drift. Add a simple ZZ
term (for example, about 100 kHz static ZZ between idle neighbours) and check that the DD and
scheduling choices still win.

Result (toby, 6 calibrations, N = 4..14, expected score summed over 25 cases): with 100 kHz static ZZ on every
coupled pair, ryon/toby_sol.py (preliminary submission) 16.08 vs the ladder (toby/ladder_sol.py) 20.36, +4.28 +- 0.07
(6/6); with coherent CZ phase errors (per-coupler conditional + local Z phase, sigma 0.03 rad) 20.03 vs 21.05,
+1.03 +- 0.20 (6/6). The shorter ladder circuits gain the most under crosstalk; DD (one x-x pair per idle window
>= 8 moments) stays on in both.

### 5. Bonus question: adaptive circuits with lower depth (2 <= N <= 15)
The bonus compares moment counts and allows mid-circuit measurement with feed-forward. The current
code returns the packed standard circuit. Ideas: measurement-based fusion of W states, or the
constant-depth LAQCC Dicke constructions (Buhrman, Folkertsma, Loff, Neumann 2023). Respect the
readout-line rule: qubits with the same row + col can't be measured on their own.

### 6. X-basis term for n near N/2
For (8,4), X is about 0.42 out of 1.77 in the denominator. High-weight X correlators decay with
dephasing. Check how much comes from depth and how much from CZ error, and whether a different
DD placement or a shallower schedule recovers it.

Diagnosis (toby, D(12,6) with toby_sol @7e7133a, 2 calibrations, noise sources switched off one at a time):
full E 0.457 (X 0.332, f 0.556); no detuning 0.470 (X 0.325); no Tphi 0.509 (X 0.281); no T1 0.580 (X 0.155);
no gate error 0.609 (X 0.129). The X term near N/2 comes from T1 decay and gate error, not dephasing: DD already
removes the detuning, so DD placement can't recover it. Only shorter circuits (less T1 time) and fewer CZ help.

## Done
- Ported start blocks (restricted-range scs steps) from toby/halves_start_sol.py; ryon/toby_sol.py logic now matches it. Bonus 37.81 -> 38.30, N <= 8 unchanged.
- Ported multi-split ladder search from toby/combined_sol.py (tries splits outward from balanced for 8 s): 17.173 -> 17.192. Max build time 20 s at N = 20.
- Ladder half (4,3) on a path: 18 -> 12 CZ. (7,3) 0.789 -> 0.830, (8,3) 0.768 -> 0.824, and (9,3) 50 -> 44 CZ.
- Merged toby/ladder_sol.py (ladder split, doubling tree, two-variant bonus) with the patch table: 16.755 -> 17.077, bonus 26.35 -> 37.81.
- (6,2) 18 -> 14 CZ and (6,3) 33 -> 12 CZ on a 2x3 patch: E[s] 0.932 -> 0.962 and 0.825 -> 0.934.
- (5,2) on a 5-qubit patch: 11 CZ, E[s] 0.986 -> 1.005 (0dc262c).


## Coordination update — 2026-10-25, bonus W native-depth result

PORT-002 remains assigned to `w_depth`. Contributor `bonus-depth` completed
921 W decomposition/topology trials and produced a 56-case native circuit pool
scoring **45.14220419051065**. Newly accepted W circuits pass full-state,
relative-phase, native-gate and Willow checks; standalone export/build-time
verification is pending. Evidence: `research/bonus_band_20261025/w_results.json`;
circuits: `research/bonus_band_20261025/w_circuits.json`.
`operations(root, children, kinds)` in `w_variants.py` is reusable: it selects
between two exact broadcast-edge decompositions on the single-excitation
subspace. `w_depth`: please review/reuse these results before repeating that
search; your existing ownership is preserved.

Follow-ups are recorded in `research/bonus_portfolio_20261025/tasks.json`:
PORT-004 (calibrated W integration) is assigned to `bonus-depth`;
PORT-005 (certified terminal-decoder integration) is available, with the existing
BR-108 integration worker suggested but not assigned;
PORT-006 (adaptive weight-band uncomputation) is available to claim.
Five/six-site decoder fitting and the claimed k=2 brickwork searches remain
with their current workers. Hardware comparisons will use a fresh maintained
solver snapshot rather than the older bonus-research baseline.

**Request to other workers:** please append your best candidate circuit/data
paths, source hashes, emitted native depths/CZ counts, validation evidence,
remaining unmet needs and current claims here. For score comparisons, include
the calibration/noise assumptions and correlator cutoff. Frozen native circuits
are preferred for safe comparison across concurrent work. Continue proposing
improvements beyond the 45-point milestone.


### Verified export follow-up — 2026-10-25 01:33 EDT

The frozen native portfolio now scores **46.1786336531** across all 56
corrected bonus cases, with maximum constructor time 0.002769 s.
Candidate: `research/bonus_band_20261025/milestones/20261025T053345Z/submission.py`; evidence: `research/bonus_band_20261025/milestones/20261025T053345Z/validation.json`;
SHA-256: `e4dc392bad5ed96a956446d509e402d7980343008ca2fbf10975968a5eabeff4`. This combines the W/terminal improvements with
independently checked peer patches and aligned-splitter circuits. The existing
PORT-002 owner is preserved; PORT-004 is assigned to bonus-depth. A portable
exact W helper is available at `research/bonus_band_20261025/w_broadcast.py`.
The 45-point milestone is reached; please continue posting better circuits and
unmet needs. No additional primary gain is claimed from the identical D(8,4)
comparison against the fresh maintained solver.


### Continued checkpoint — 2026-10-25 01:53 EDT

The validated native portfolio is now **46.5862094107** after merging
peer W improvements; immutable evidence is `research/bonus_band_20261025/milestones/20261025T055319Z/validation.json`.
The named publication branch is `bonus-native-20261025T053245Z` (first checkpoint
commit `6e7dbdbc28796918a68756c6c7954c9c23d403b7`; further checkpoints stay on that branch).
PORT-004's N=8,10 pilot is complete: unconditional all-Givens substitution is not
accepted for the main solver. See `research/bonus_band_20261025/w_hardware_summary.json`;
next work is calibration-aware selection accounting for single-qubit cost and
schedule duration. PORT-007 is the preserved duplicate, tracked by PORT-004.
Please continue posting better native circuits, hashes, validation and unmet
needs; the 45 milestone is not a stop condition.


### PORT-004 research handoff — 2026-10-25

Fixed-tree decomposition and compiled-tree placement pilots are complete at
N=8,10, calibration seeds 0..5 (held-out 3..5), four detuning realizations,
10000 shots per basis and 32768 score repetitions. The main constructor is
unchanged. Fixed-tree state-aware selection kept baseline all 12 cases.
Count-cost held-out mean score changes were -0.0111802 (N8) and -0.0022420 (N10).
Tree-placement held-out means were +0.0050858 (N8) and 0 (N10); the N8 mean has
conditional MC standard error 0.0049055. These small mixed pilots do not
establish a production gain. Every evaluated candidate passed native/device
and exact-state checks; maximum tree-selection build was 0.514 seconds.

Evidence and rerun commands: `research/bonus_band_20261025/w_experiment_manifest.json`;
summaries: `w_cost_summary.json` and `w_tree_summary.json` in that directory.
PORT-004 remains assigned to bonus-depth: next derive first-order valid-Z-string
probabilities and test within-sector bias against scaled-noise simulation.
Source-backed research hypotheses are in `research_followup.json`.
PORT-005 is being coordinated separately for fresh peer artifact integration.
Please post additional explicit native circuits and remaining unmet needs with
source hashes and supported coherent input ranges.


### Independently verified 47.4262 checkpoint — 2026-10-25

The standalone bonus portfolio now scores **47.426166194653**
(+0.839956783964) across all 56 corrected cases.
Immutable candidate/evidence: `research/bonus_band_20261025/milestones/20261025T063113Z`.
Candidate SHA-256: `91f5cb0b69af173bf1a3e89b3fbe00511975f9d57512c47caafbbc55e199619d`.
Max constructor 0.002808424 s; max L2 error 2.11986719e-07.
The main entry point is preserved. Integration results and reusable compiled
five/six-site decoders are in `research/bonus_terminal_integration_20261025`.
Remaining N15/asymmetric coverage is explicitly unfinished. PORT004 continues
with a first-order output-probability model; recent primary-source literature
and a finite-resource audit are recorded under PORT008.


### PORT-004 promising candidate and further pickup — 2026-10-25

`research/bonus_band_20261025/w_z_selection.py` ranks a bounded tree shortlist
using first-order valid-Z-string probabilities. The independently checked
channel derivative error is 2.46e-8 on four qubits. Fresh seeds 6..11 give
mean sampled E[score] changes +0.0219758 at N8 and +0.0210585 at N10; nine
improvements, one loss, two baseline choices. Max build1.127s; all native,
device and state checks pass. Results include both cutoff4/all-X scores,
conditional MC errors and descriptive across-seed uncertainty. Main unchanged.
See `w_z_summary.json` and `w_z_manifest.json` in the same directory.
The PORT004 owner will check original baseline seeds and coordinate realistic
noise validation before main integration. PORT009 is available for remaining
N15/asymmetric terminal integration; PORT008 is assigned for a read-only
finite-resource audit of recent symmetrization literature.


### Confirmed W-selector handoff and completed resource screen — 2026-10-25

PORT-004: unchanged selector confirmed at original seeds 0..5: all-X mean score
changes +0.0103312 (N8) and +0.0110804 (N10), with 11 improvements and 1 retained
baseline. Combined with fresh seeds 6..11: 20 improvements, 1 decline, 3 retained
baselines across 24 comparisons. Native/device/state checks pass throughout;
main remains unchanged. Sources: `research/bonus_band_20261025/w_z_baseline_manifest.json`.
The maintained W-related functions still match the frozen baseline.
Next work: coherent-error/crosstalk comparison and guarded integration. Workers
with the realistic-noise evaluator can reuse the selector directly; please post
any additional integration constraints or artifacts on PORT-004 before duplicating
its synthetic-calibration studies.

PORT-008: finite arithmetic resource screen is reproducible with stdlib Python
in `research/bonus_symmetrization_audit_20261025/resource_audit.py`. Direct
outer-register bounds are 48/89/116 qubits for N8/12/15 before scratch. The separate
literal generic-merge screen is 128/250/322 under its stated assumptions. These
are construction-specific; full native depth/routing remain undetermined.
Audit SHA256: 61320acc0a80ec76a096254cd666046b554eb1af457f6926fd3d2acd7b21ccb7.
PORT-009 remains available for unfinished N15/asymmetric decoder integration.


### Verified 47.8780 checkpoint and hardware stress follow-up — 2026-10-25

The standalone bonus now scores **47.878031742696336**, all 56 cases verified;
max constructor 0.002442s, max state L2 error2.1198672e-7, max depth 119.
Immutable evidence: `research/bonus_band_20261025/milestones/20261025T070208Z`.
PORT-009/010 finished the defined balanced/adjacent-split worklist, 31 valid groups
complete. Two passes improved nine cases beyond the prior published 47.4262.
Their frozen inputs, coverage, circuits and results are in
`research/bonus_terminal_completion_20261025` and
`research/bonus_terminal_finalpass_20261025`.

PORT-004: shared-physical-chip stress tests retained nominal/coherent mean gains
but exposed losses under assumed 100 kHz uniform ZZ. No main promotion. A
second-order ZZ-output model passed an independent coefficient check to 5.3e-11;
its fresh-seed 12..14 pilot has positive mean deltas in all three modeled regimes.
Confirmation on the earlier stress cohort is next. Full evidence:
`research/bonus_band_20261025/w_stress_manifest.json` and `w_zz_manifest.json`.
These models omit leakage, outside spectators and pulse overlap, and 100 kHz is
not asserted as a measured Willow parameter. PORT-011 is a narrow fixed-topology
precision repair of an existing decoder, coordinated separately.


### Bonus and hardware handoff — 2026-10-25

Verified standalone bonus **48.0185710188**, all56 cases; checkpoint
`research/bonus_band_20261025/milestones/20261025T071120Z`.
PORT-011 fixed-topology precision repair completed; all reconstructible source,
comparison and certification evidence is in `research/bonus_half_precision_20261025`.
PORT-004 coupling-aware W selector confirmation is complete: positive mean sampled
score changes under nominal, coherent and assumed100kHz ZZ models for N8 and N10,
with all36 baseline rows exactly reproduced from the earlier stress study.
Evidence: `research/bonus_band_20261025/w_zz_confirmation_summary.json`.
These are simulated model results, not hardware measurements; main is unchanged.
Next: bonus-integration owns remaining certified-decoder coverage; bonus-depth
owns standalone hardware-selector validation. Other agents: please post missing
requirements, superior circuits and uncovered cases in this queue.


### Standalone selector and continuation handoff — 2026-10-25

PORT004 standalone hardware candidate validated at
`research/bonus_band_20261025/hardware_submission.py`, SHA-256
`7c962504b1962c192ea274aaf13494e484cbd17b3df248a0b56f143a32e3b49d`.
All18 evaluated selectors match, all56 bonus circuits are identical, maxbuild1.241s;
non-W paths use the current761433b main snapshot. Maintained solver unchanged.
PORT013 completed399 additional comparisons with no gain; best48.0185710188.
Frozen coverage/provenance: `research/bonus_half_completion_20261025`.
PORT014 compressed-label audit is assigned to bonus-integration. PORT015
held-out signed-ZZ stress is complete and blocks selector promotion: N10 mean
delta -0.01438, with seed17 delta -0.09346. Maintained main stays unchanged.
PORT016 is assigned to bonus-depth to model heterogeneous coupler interactions;
see `research/bonus_band_20261025/w_heterogeneous_summary.json`.
Please post better high-weight coherent terminal circuits or integration needs.


### PORT-014 symbolic converter audit — no native-depth claim

`research/bonus_binary_resource_audit_20261025/audit.py` gives an exact seven-qubit binary-to-unary converter for r=0..7 using four Toffoli gates and ten CNOTs, with no extra qubits outside the output. All eight input mappings pass; the six-CNOT Toffoli implementation also passes eight exact phase checks over rational cyclotomic arithmetic, with amplitude+1 on every mapped basis state. Thus the converter has34 CZ before routing. A deliberately unoptimized SWAP-and-restore route on an existing verified Willow path costs376 CZ; this is an upper bound, not an optimized route.

Two converters add68 CZ; even assigning zero preparation cost to the compressed root, its three cross-register CNOTs replace a13-CZ unary root, giving a naive module-count disadvantage of58 CZ. This does **not** prove a native-depth loss: gates can parallelize, fuse or cancel. The next distinct mechanism must be fused seven-site binary decoding or concrete boundary cancellation, not a repeat of BR103 random fits. The full routed preparation remains unbuilt. Evidence and source hashes: `converter_audit.json` and `handoff_manifest.json` in the same directory. No floating state simulation, fit, or hardware/main change was made.
