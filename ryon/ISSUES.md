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

Baseline at 0dc262c: total 16.615. Current: **17.480** (3 seeds, N = 2..8). Bonus (N <= 15): 38.30.

## Open

### BR-110. Verified bonus portfolio exceeds 45
Status: scientific checkpoint complete; a qualifying published checkpoint independently verified
`research/bonus_portfolio_20261025/portfolio_submission.py` scores
**46.2165739570** over all 56 corrected bonus cases. Full complex128 amplitudes
and relative phases, native gates, Willow edges/qubits, inclusive moment limit,
and per-call construction time all pass (`validation.json`). Maximum state
L2 error is 1.21e-7; the slowest observed constructor call was below 0.1 s.
The portfolio merges independently verified complete circuits, and returns
explicit native moments with no fitting or hidden nested circuits at runtime.
README records both the archived 43.222 checkpoint and the current best.
The concurrent checkpoint on `bonus-native-20261025T053245Z`, commit
`6e7dbdbc28796918a68756c6c7954c9c23d403b7`, was fetched from GitHub and
independently revalidated over all 56 cases at **46.1786336531**. Its committed
candidate SHA-256 matches the published validation report. Evidence:
`research/bonus_portfolio_20261025/remote_publication_audit.json`.
This supplies the requested periodic publication. The higher local 46.216574
checkpoint remains available on the separately prepared branch pending its
requested review; no duplicate remote push was made. Open follow-up tasks and
their current owners remain in the shared task board.

### BR-111. Mixed exact splitting identities shorten W-state broadcasts
Status: complete; calibrated main-path integration is available for pickup
`research/bonus_w_20261025/random_w_circuits.json` has W depths for N=5..15
of **9,9,9,10,10,11,12,12,12,12,13**, all with the same CZ counts 2N-3.
Gain relative to the former frozen W portfolio: **+1.3693639694** bonus points.
The fresh-target split and full Givens split agree on the reachable vacuum/
single-excitation columns; choosing identities per edge changes which local
rotations cancel. All 11 full-state/native/device checks pass to <1.5e-15.
The standalone bonus portfolio includes these improvements. The main constructor
can use the same identity choices after a paired calibrated E[score] comparison.

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
Partial result (ryon, fast_eval + per-coupler coherent CZ error: extra |11> phase and local Z phases, sigma 0.03 rad,
fixed per coupler, 2 seeds): sum over (7,3) (8,4) (9,3) (9,4) (10,3) (10,4) (10,5) is 3.836 @ a26041d vs 5.264 @ 8993717,
every case better. Repeated CZs on one coupler don't hurt at this level. Crosstalk and N >= 11 still open.
Trajectory result (toby, eval/ trajectory sim, N = 9..16 all n <= N/2 = 48 cases, 6 fresh calibrations, @ 313d9ec vs
@ a26041d, expected score summed): base 29.82 -> 30.14 (+0.32 +- 0.21, 5/6); coherent cz (sigma 0.03 rad per coupler)
27.17 -> 27.65 (+0.48 +- 0.21, 5/6); zz 100 kHz crosstalk 25.89 -> 26.27 (+0.39 +- 0.16, 5/6). Same at K = N. The
changed cases all gain under every model: (9,4) +0.11 / +0.22 coherent / +0.18 zz, (9,3) +0.05 / +0.08 / +0.08. The
apparent (16,1) loss (-0.10) is one calibration where the split-half Zb estimator blew up at 80 trajectories (3.2);
at 400 trajectories it is 0.909 vs 0.888, a gain. No case for prefer_synth = False. Re-running at HEAD for (10..11, k).
At HEAD 59f8300 (6 more calibrations, >= 300 trajectories): base 29.82 -> 30.51 (+0.69 +- 0.08), coherent cz
27.69 -> 28.77 (+1.09 +- 0.11), zz 100 kHz 25.75 -> 26.72 (+0.97 +- 0.05), 6/6 calibrations each; K = N +0.81 / +1.09 /
+0.99. Every changed case gains under every model, largest (10,5) +0.17 / +0.32 / +0.27, (11,3) +0.11 / +0.16 / +0.13.
Status: done (toby). The pruned circuits are more robust to crosstalk and coherent error than the ladder, not less.

### 11. Pruned line halves for the ladder at N >= 17
Status: in progress (ryon session, claimed 2026-10-25 01:35). Running on the cluster: half isometries
for a = 7, 8 (fallback for N = 13..16 when no whole-state line fits) and a = 9, 10 (N = 17..20),
warm-started from the line plan of each half (`benchmark_outputs/synth/search_half_warm.py`), with
windowed prune so depth never grows. Results go into `halves` after an A/B with `ab.py`.
Results so far (installed; they went in with 5a0a94f): (6,3) 36 -> 25 CZ and (7,3) 45 -> 32 CZ halves.
Trajectory A/B (2 seeds, 60 trajectories, no-Zb): (12,3) +0.006, (13,3) +0.070, (14,3) +0.118 (95 -> 69 CZ).
Also found, not used by any current case: (5,3) 19, (5,5) 35. `synth.py` now has a C kernel for fid_grad
(15-25x faster, 3a43d2a), so half searches up to a = 10 are running again from the line plan.
Path runs cover N <= 16 only (state vector 2^N per refit). For N = 17..20 the ladder is still used.
Run `benchmark_outputs/ex/gpar.py`-style pruning on the half isometries (unary -> D(a, l) for all l,
target = (inputs, outputs)) on a path, starting from `half_ops`, and install into `halves`.

### 12. W states below 2N - 3 CZ
Status: open, unassigned (research)
Whole-state pruning never removed a CZ from the W trees (N = 4..12). Is 2N - 3 optimal for CZ + 1q gates?
A proof or a counterexample (e.g. fit random 2N - 4 CZ sequences on trees / paths, many restarts) settles it.
W cases are about 40 % of the small-N score, so even one CZ matters at N >= 8.
Evidence (ryon, numerical, not a proof): W3 with 2 CZ fails for every 2-CZ sequence on 3 qubits, even with
general complex 1q gates (U3 everywhere, 12 BFGS restarts each, best infidelity 0.127). W4 with 3 or 4 CZ fails
on the path and the 4-cycle with real (Ry) gates (best 0.25 and 0.067). The split step alone (|10> -> a|10> + b|01>,
|00> fixed) needs 2 CZ. So 2N - 3 holds for N = 3, 4 in these searches.
Evidence (ryon): random CZ sequences on a 2x2 / 2x3 patch with random restarts never fit W(4) with 4 CZ
(28k tries) or W(5) with 6 CZ (19k tries), while 2N - 3 fits in a few tries. Likely optimal; low priority.
Exhaustive (toby, research/toby_offline/w_bound.py): every CZ sequence up to qubit relabelling, all-to-all
connectivity (a superset of any chip), general u3 on every qubit before, between and after, 40 restarts each.
W(3) with 2 CZ: best infidelity 0.127. W(4) with 4 CZ: all 39 canonical sequences stop at 0.066987 = 1 - (2+sqrt3)/4;
with 5 CZ they fit exactly. So 2N - 3 is optimal at N = 3, 4 (numerically); no CZ to gain for W on hardware there.

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
Path (line) versions now win for (7,3) 0.903, (8,3) 0.847, (9,3) 0.803, (10,4) 54 cz 0.634; (11,3) 44-cz patch 0.633 -> 0.763.
k = 2 selection (3 seeds): pruned circuits (17-18 cz for (7,2)) have higher f but larger Zb (gate-error pattern makes
the in-subspace distribution uneven; C(N,2) is small, so shots/C is large) and end up equal or worse: best gain +0.003
((10,2) gp_10_2_a2), not installed. Any k = 2 work should score with fast_eval's Zb, not CZ count.
Installed for N >= 11 (5a0a94f, chosen by estimate_error on 2 calibrations; fast_eval takes ~20 min per
candidate at N = 12): (11,4) 82, (11,5) 62, (12,3) 51, (12,4) 96, (13,4) 112, (15,3) 68 CZ.
Search notes: for N >= 11 the 3-row footprint started from the line construction is what prunes ((11,5)
117 -> 62); path and 4-row/square footprints stall; ladder starts barely move at N >= 13. Deletion
screening (fold the CZ's angles into neighbours, try lowest-loss deletions first; SCREEN=1 in gpar.py)
did not beat random deletion order, so it is off by default. A grow-from-D(N-1,k-1) seeding idea is
impossible (window unitary can't raise the Schmidt rank across the window boundary from k to k+1).
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
`ryon/traj_eval.py` (ryon): state-vector trajectories of the same noise model, so N up to ~20 fits
(N = 12: 7 s per 10 trajectories). Unbiased squared terms; f, Z floor and X match fast_eval within
a few 1e-3 at 300 trajectories at N = 6..8. The Z-bias term stays noisy (shots x squares), so use
its `no-Zb` column for A/B at large N. `--kmax 4` gives the other correlator-size convention.
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


### Published pickup pointer — 2026-10-25

The immutable **46.17863365311297** bonus checkpoint is published on
`origin/bonus-native-20261025T053245Z`, commit
`6e7dbdbc28796918a68756c6c7954c9c23d403b7`.
Candidate and evidence are `research/bonus_band_20261025/milestones/20261025T053345Z/submission.py`
and the adjacent `validation.json`: all 56 cases passed; maximum constructor
0.0027686692774295807 s. Candidate SHA-256:
`e4dc392bad5ed96a956446d509e402d7980343008ca2fbf10975968a5eabeff4`.

PORT-004 is **in progress (bonus-depth)**: planned paired W comparisons at
N=8 and N=10, three fake calibrations (seeds 0,1,2), all-X-order and cutoff-four
scores, against a fresh frozen maintained solver. No new primary gain is yet
claimed. To resolve a concurrent ticket-ID collision, the newly added,
unassigned PORT-004 was renumbered to PORT-007;
its original title/content are preserved and its work is tracked by the
accepted PORT-004. Completed PORT-001/PORT-002 ownership and evidence remain
unchanged.

**Worker pickup/request:** please post remaining unmet needs and improved
explicit native circuits here, including artifact paths, source hashes,
actual depths/CZ counts and validation evidence. State any current claim so
other workers can coordinate the next frozen merge. Research continues beyond
this published milestone.


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


Publication pointer: `bonus-native-20261025T053245Z` now contains commit
`cde1672e759b831e1dfd9b931b70097fbfea3f5e` with the validated **46.5862094107**
checkpoint, completed peer decoder/W artifacts, and the calibrated-W pilot.
The existing PORT-004 owner continues calibration-aware selection; completed
PORT-001/002 owners and the remaining available tickets are preserved.
