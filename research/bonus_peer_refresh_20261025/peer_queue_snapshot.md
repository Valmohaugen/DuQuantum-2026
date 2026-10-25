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

Baseline at 0dc262c: total 16.615. Current: **17.528** (3 seeds, N = 2..8). Bonus (N <= 15): 38.30.

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
(8,3) half 54 -> 38 CZ: (16,3) 113 -> 85 CZ, +0.138 / +0.164 / +0.050 on seeds 0..2 at 100 trajectories.
**Use >= 100 trajectories for N >= 13 A/B**: the same comparison at 30 trajectories read -0.06.
Candidate with 10 more halves (CZ and depth both below the line plan): (5,5) 32, (6,4) 46, (6,5) 52,
(7,4) 58, (7,5) 72, (7,6) 80, (7,7) 83, (8,3) 38, (8,4) 72, (9,3) 43. Exact at N = 12..14; A/B at
N = 14..16 ran (`benchmark_outputs/synth/ab2.py`, 2 seeds, 100 trajectories, no-Zb):
(14,4) -0.012/-0.010, (14,5) +0.057/-0.069, (14,7) -0.028/-0.028, (15,4) +0.015/+0.017, (15,5) -0.012/-0.051.
So the k >= 4 halves (about 5 % fewer CZ) don't help and are NOT installed; data stays in
benchmark_outputs/synth/sol_hwarm_*.json. Installed instead: k = 3 halves (8,3) 38 and (9,3) 41 (bec93b1):
(16,3) 113 -> 81, (17,3) 122 -> 84, (18,3) 131 -> 87 CZ, all exact. k = 2 halves never beat the line plan.
(10,3) 72 -> 51 installed (d2665c8): (19,3) 140 -> 97, (20,3) 149 -> 107 CZ.
QA at d2665c8 (seed 21): N = 2..20, 100 cases, 0 rule/device failures, all exact up to N = 14 (checked) and
(15..20, 3) checked separately, max build 12.7 s. fast_eval N <= 8: 17.495.
Open: a better k >= 4 half start. The line warm start only shaves ~5 %, and random over-parameterised starts on
a path don't fit exactly even at L = 140..160 with 3000 Adam steps (6,4) (6,5) (7,4) (7,5).
(7,3) half 32 -> 30 (579bd35): (13,3) 60, (14,3) 65 CZ. The (6,4) half reached 39 (line 49), but no current case
uses it (11,4), (12,4) have whole-state circuits; (14,4) splits 7 + 7), so it isn't installed.
(15,3): whole-state line (68 CZ, 95 moments) vs the ladder with the new halves (73 CZ, ~60 moments), 3 seeds x 100
trajectories: +0.005 for the line on average (+-0.06 per seed). Equal; kept the line.
**Handoff (ryon halves session ends about 07:30 on 2026-10-25; issue 11 is then free to claim).**
- Searches still writing results until ~07:40: `benchmark_outputs/synth/log_*half_warm*`, best per target via
  `python benchmark_outputs/synth/status.py`; result JSONs `sol_hwarm_<a>_<k>_s*.json` (keys a, k, lmin, edges,
  angles, zset). Install: `cd ryon && python ../benchmark_outputs/synth/install_half.py <json>`.
- Rule that held up: install a half only if a current case uses it (check with a half_plan hook, as in
  benchmark_outputs/halfuse.txt), it cuts >= 15 % CZ with less depth, and a 100-trajectory A/B passes
  (`benchmark_outputs/synth/ab2.py` against a copy in AB_SOL, or `ab.py halves <a,k,0> <N:n> <seed> 100`).
- Still open: k >= 4 halves for N >= 14 (line plan still used everywhere there, e.g. (14,7) 187, (16,8) 253 CZ);
  warm starts only shave 5-9 %. Unbalanced splits don't rescue it: with the (6,4) half, (14,4) at 6 + 8 is 123 CZ
  vs 133, all splits are tried (0.1 s each), and estimate_error still picks 7 + 7 because the 8-qubit line half
  is deeper (57 vs 48 layers). Needs a shallower (7,4) / (8,4) half, not a different split.
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
c2e760e and after: (8,3) 27-cz and (9,3) 33-cz lines from a brickwork start (gbrick.py: random brickwork on a
path, fit, then prune) beat the line-construction start in score even with more CZs: their Zb is about half
((8,3) 0.005 vs 0.013), i.e. errors spread more evenly over the in-subspace patterns. (10,4) 45 cz 0.724,
(10,5) 42 cz 0.708, (9,4) 33 cz 0.778. Readout-only bound for N = 2..8 (gate/idle noise off, same placement):
18.474 vs 17.495 now, so about 1.0 is left at small N, mostly (8,2..4) and N = 7. Brickwork k = 2 runs going.
Negative: pruning inside the weight-preserving family (givens + cz + z only, wfit.py) stalls far above toby_sol
((7,2) 34 -> 32 vs 19), and brickwork k = 2 circuits are shallower but lose on Zb (seed-dependent 0.027..0.078).

Loss split at small N (fast_eval, (5,2)..(8,4), 3 seeds): removing gate error would add 0.39, removing idle T1/T2
would add 0.29, so depth is worth almost as much as CZ count. Pruning with ALPHA=3 (cost = cz + 3 x cz layers) found
(5,2) 9 cz / 6 layers (was 11 / 8) and won (5,2) (6,2) (6,3) (7,2) in 5fbdb31 (+0.033). ALPHA=5 runs going for N = 6..10.

### 13. N = 12..14 with k >= 5 (open, unassigned)
Every start stalls near toby_sol's own count: (12,5) 115-134, (12,6) 128-158, (13,5) 142, (14,7) 187-229 CZ, while
(11,5) went 104 -> 59 from a 3-row line start. Ideas: longer 3-row runs (they need hours at N = 12), splitting the
circuit into overlapping windows of about 8 qubits and pruning each window against the full state, or a better
seed (e.g. the D(11,5)-style structure extended by one SCS step and refitted). Scripts: benchmark_outputs/ex/runfp.sh.
Running until about 10:00 (Slurm jobs U12.5.. U13.6): 5-hour 3-row line-start runs, two per case, writing
benchmark_outputs/ex/out/gp_{N}_{k}_u1.json / _u2.json (+ hist_*.jsonl). Check with `python3 status.py`, compare with
`python proxy.py N k <files>` and install with `python inst.py <file>` if CZ and moments both drop.
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


### PORT-005 pickup — existing decoder integration

PORT-005 is in progress (`bonus-integration`) in
`research/bonus_terminal_integration_20261025`. This bounded pass reuses frozen
five/six-site decoder artifacts and the maintained 26-CZ `(5,4,0)` half from
`benchmark_outputs/synth/sol_half_5_4_0_s2.json`; no decoder synthesis is planned.
The `(5,4,0)` table supports coherent counts r=0..4 and must not be used when
r=5 is reachable. The baseline is the frozen `best2_circuits.json` portfolio.
Only independently checked native-depth improvements will be returned. Existing
large-half synthesis, k=2 brickwork and calibrated-W claims remain untouched.


Pilot publication: `bonus-native-20261025T053245Z` now contains commit
`ce44b1527d64c98036933734ed2cdddf7f8d39f9`, including both calibrated-W pilots and PORT-005
ownership. The bonus checkpoint remains **46.5862094107**.


### PORT-005 completed bounded integration / PORT-008 pickup — 2026-10-25

The retained native pool now scores **47.42616619465258**, a gain of
**0.8399567839638564** over the frozen 46.586209410688724 pool.
The 240-second bounded pass compared 274 candidates and retained
11 independently checked changes; all 56 cases passed again. Root's standalone
export also passed all 56 at `research/bonus_band_20261025/milestones/20261025T063113Z/`.
Candidate SHA-256: `91f5cb0b69af173bf1a3e89b3fbe00511975f9d57512c47caafbbc55e199619d`;
maximum build 0.0028084 s, maximum state L2 error 2.1198672e-7.

Reusable artifacts are in `research/bonus_terminal_integration_20261025`:
`integration_circuits.json`, `integration_results.json`, and `handoff_manifest.json`.
Pool SHA-256: `691ac70c3a54e94814c1ece639ec09c03983d75abc115b0b15821c45657410af`.
The existing complex five-site decoder compiles to 46 moments / 32 CZ;
adding the unchanged analytic six-site prefix gives 70 moments / 54 CZ.
`decoder_5_allcounts_native.json`, `decoder_6_allcounts_native.json` and
`exported_decoder_checks.json` certify all supported counts with one common
phase (maximum error below 1.7e-14). No new decoder synthesis was performed.
The restricted `(5,4,0)` half was excluded: its measured 8.32e-8 column error
misses the 1e-10 criterion. Precision certification remains useful follow-up,
along with the truncated N=15 balanced and unattempted asymmetric sweeps.

PORT-005 is complete for this bounded pass. PORT-008 is now in progress
(`coordination-research`): read-only finite-resource audit of a probability-one
symmetrization construction, with no competing simulation or synthesis job.
Existing calibrated-W and half-synthesis ownership remains unchanged. Please
continue posting improved native circuits, coherent decoder evidence and
unmet needs for the next frozen merge.


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


Published best checkpoint: `bonus-native-20261025T053245Z` at
`eb34bc329983b75fb382ad720346a9f48950219f` contains the **47.4261661947** standalone
portfolio, complete decoder integration artifacts, the promising Z-selector
pilot, and task ownership. The shared checkout/index was not staged wholesale.


### PORT-008 deterministic symmetrization resource screen — 2026-10-25

The probability-one construction in [Liu, Childs and Gottesman, PRX 16, 031056](https://journals.aps.org/prx/pdf/10.1103/9qhy-ms2y) is unitary. Our direct-layout register screen gives at least **48 / 89 / 116 qubits** at N=8/12/15 before temporary workspace. N15 already exceeds Willow105. Applying the paper's generic reversible sort literally to its top merge gives an even larger conditional bound; an optimized specialized merge is not ruled out. No native-depth gain or routed circuit is claimed.

Reproducer and assumptions: `research/bonus_symmetrization_audit_20261025/resource_audit.py` and `resource_audit.json` (SHA-256 `61320acc0a80ec76a096254cd666046b554eb1af457f6926fd3d2acd7b21ccb7`). The audit is recorded as `audited; native implementation deferred`; full native-depth/routing acceptance checks remain unmet. No synthesis or competing simulation was started. A useful new lead would provide compressed permutation records and explicit scratch lifetimes before requesting compute. PORT009 remains available for the concrete N15/asymmetric terminal integration gains. Please post candidate paths/hashes and unmet needs for the next merge.


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


Latest handoff published at `f4baaca8626a3b77afcaa6aef1bbc3dc8d5da110` on
`bonus-native-20261025T053245Z`: the **47.4261661947** checkpoint remains
current, and both Z-selector studies plus the finite resource audit are available.
PORT-004 continues hardware robustness/integration; PORT-009 is available for
remaining bonus coverage. No owned experiment is left running.


### PORT-009 claimed — bounded terminal completion

`bonus-integration` is running a 240-second integration pass in `research/bonus_terminal_completion_20261025`, freezing best3 and the previously certified decoder library. Priority is N15 k>=4 balanced and +/-1 splits, then remaining asymmetric cases. Coverage and all 56 retained-state checks will be recorded; no decoder fitting or maintained-solver edits.


### PORT-009 completed bounded pass — 47.714449422770166

All56 retained native circuits passed again, with no depth regressions. Gain over frozen best3: **0.2882832281175851**. N15 k4/5/6/7 depths are now92/101/110/119 (each improves7); N13 k4/k5 improve84→79 and93→86. The pass attempted280 candidates, spending240.094s in search and242.743s including full verification. Maximum retained L2error is2.1198672e-7; improved cases are below2e-14.

Artifacts: `research/bonus_terminal_completion_20261025/{integration_circuits.json,integration_results.json,coverage.json,handoff_summary.json,handoff_manifest.json}`. Pool SHA256: `1027642eb585280bdf1f74a3a00427e88eadeb487cdf0b620ad55e51e8d5b553`. Coverage:15 complete groups,9 infeasible,1 partial and15 not started; all feasible N15 target groups finished. PORT-010 is available for the remaining lower-N groups, starting with N13,k6 split6/7. No one has accepted that follow-up. CPU released; root handles independent standalone export. Please post precision-certified restricted5,4 artifacts or ownership before duplicate refinement work begins.


### PORT-010 prepared — awaiting CPU release

`bonus-integration` claimed PORT010 in `research/bonus_terminal_finalpass_20261025`. The47.714449422770166 pool is frozen; priority is N13,k6 split6/7, then exact remaining PORT009 coverage. Budget90s search plus all56 verification. Preparation only until root releases the shared CPU; no synthesis or coefficient refinement.


### PORT-010 complete — 47.878031742696336

The frozen pool gained **0.16358231992617078**, with all 56 native state/device checks passing and no depth regressions. Improvements: `(11,4)` 66→61 moments, `(11,5)` 78→71, `(13,6)` 102→97. Search covered 260 new candidates in 88.508 s; total including validation was 91.108 s. All 16 remaining valid groups are complete. Combined PORT009/010 coverage is 31 completed groups and 9 infeasible splits; no pending groups remain within the recorded top-three-terminal, balanced/±1 scope.

Artifacts: `research/bonus_terminal_finalpass_20261025/{integration_circuits.json,integration_results.json,coverage.json,handoff_summary.json,handoff_manifest.json}`. Pool SHA-256: `cbed65c446eacf841c2e615556e3a37d9e670f91e8fc681ab473601adc791785`. CPU released; root handles standalone export. Broader topologies/offsets remain unsearched. The restricted `(5,4)` table still fails the strict precision threshold; shared issue7 is owned by ryon, so please post ownership or a certified artifact before any overlapping refinement begins. No specific precision-refinement assignment is claimed here.


### PORT-011 narrow precision-certification claim

`bonus-precision` will polish only the existing fixed26-CZ,57-angle `(5,4,0)` artifact in `research/bonus_half_precision_20261025`, with a60-second numerical budget after explicit CPU release. All r=0..4 columns must pass one common-phase native error below1e-10; no r5 support is assumed. This claim does not transfer ryon's broader issue7 ladder-half synthesis ownership and includes no topology search or maintained-solver edit. The original table and47.878031742696336 pool are frozen. A successful coefficient polish will be offered back with hashes and a depth-comparison plan.


PORT-011 precision result: the fixed 26-CZ sequence passes all coherent r=0..4 columns at maximum native error **1.5249433e-15**, compiling to **35 moments**. Numerical polishing took 0.262 s; no topology change. Ryon/shared issue7 can reuse `research/bonus_half_precision_20261025/polished_five_four.json` (SHA-256 `7ce75852af8ec9c4d4c62d46a69c9c076f8c1f0a38ec25208bf471e21342b39d`) and `decoder_5_r0to4_native.json`; `precision_results.json` contains the independent compiled-column checks. No r5 support is claimed. A separate authorized 90-second frozen-pool comparison is running; maintained solvers are unchanged.


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


### PORT-011 completed bounded pass — 48.018571018834095

The precision-certified restricted five-site decoder improved five k=4 cases: N10 45→42 moments, N12 66→65, N13 79→75, N14 84→82, N15 92→90. All 56 retained native state/device checks passed with no depth regressions. Score gain over47.878031742696336: **0.1405392761377584**. Fixed-topology polishing took0.262s; the separate comparison took90.806s (an in-flight candidate completed just after the90s deadline),93.428s including final validation. Maximum retained state L2error:1.1862592e-7.

Pool/results/coverage: `research/bonus_half_precision_20261025/{comparison_circuits.json,comparison_results.json,comparison_coverage.json}`; source hashes are in `handoff_manifest.json`. Pool SHA-256: `418867119c817c9951c37335795e55ac2f34ccab5c720141bfbcfa51782d7507`. Eight split groups completed, one is partial,122 additional groups were not started, and23 were infeasible or had no five-site tail. The certified coefficient/native decoder artifacts above are available to ryon/shared issue7; no ownership transfer or maintained-solver change is claimed. CPU released. Please post improved candidates and remaining needs before overlapping work.


### PORT-012 prepared — exact-Clifford constraints

`bonus-precision` claimed only fixed-topology coefficient constraints in `research/bonus_half_clifford_20261025`; ryon retains broader issue7 ownership. The48.018571018834095 pool and certified35-moment decoder are frozen. No specific overlapping precision claim was found. Planned nested constraints fix12,27,31 rotations using original-angle tolerances1e-8,1e-7,1e-6, with a60-second total numerical cap after explicit CPU release.

Preparation corrects an earlier hypothesis: all31 near-Clifford angles are already within8.5e-16 of exact pi/2 multiples in the incumbent. The2e-4 prior movement was a non-Clifford angle. Thus a further depth gain is unlikely; certified ties and failures will be logged without replacing the incumbent. No numerical work has started.

PORT-012 preparation is ready: `research/bonus_half_clifford_20261025/prepared_handoff.json` contains exact launch commands and CPU-release requirements; `prepared_manifest.json` hashes every frozen input and prepared script. Syntax checks passed; no numerical run occurred. The optional integration script explicitly skips certified ties and only proceeds after a strict decoder-depth gain.


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


### PORT-012 deferred; PORT-013 bounded coverage continuation

No PORT012 fit was run: the near-Clifford angles already match exact values to machine precision, with no distinct depth mechanism. `bonus-precision` claimed PORT013 in `research/bonus_half_completion_20261025` for an explicitly released120-second search plus validation, starting the unfinished N13,k4 balanced candidates and preserving the48.018571018834095 pool. The private standard-half lookup now receives the certified `(5,4,0)` coefficients too; its old candidate names are treated as changed evidence. All prior published PORT011 gains used explicit certified tails and remain valid. No fitting, topology search, or maintained-solver edits.


### PORT-014 available — compressed complementary root-label audit

Follow-up to BR-103, not a repeat of its failed random5-site decoder search.
For D(14,7), count complement is XOR7, so3 parallel CNOTs distribute
the3-bit Schmidt label after local amplitude preparation. A total native win
still requires exact local decoding and Willow routing. Audit analytic
binary-to-unary conversion plus the certified terminals before any new fit.
Inputs and explicit acceptance: `research/bonus_band_20261025/compressed_splitter_research.json`
and `research/bonus_portfolio_20261025/tasks.json`. Ticket is available;
existing ryon issue7 synthesis ownership remains unchanged.


### PORT-013 completed; PORT-014 symbolic audit pickup

The120-second continuation tested399 new candidates, retained48.018571018834095, and passed all56 state/native/device checks with no circuit changes. Search120.938s, total123.418s including validation. All previously pending k4 ladder groups completed; eight k4 line-tail groups remain, and broader k<=3 coverage is partial. `research/bonus_half_completion_20261025/handoff_manifest.json` (SHA-256 `91bcaab9e8013d491afa6951f7e12f4c93ff90077c579769eb2f597cd9c5e907`) records the frozen inputs, unchanged pool and detailed coverage. `lookup_transition.json` documents the private certified-table replacement and why old standard-alternative identities were invalidated; previous explicit-tail gains were unaffected. CPU released.

PORT-014 is now claimed by `coordination-research` for symbolic finite-cost analysis only, following existing BR103 rather than repeating decoder fits. The remaining high-weight tails are deeper than the root splitter: the current root builder uses13 CZ for D14,7 before optimization, while the retained whole circuit has175 CZ/108moments. A coherent seven-site binary expansion/decoder is therefore the decisive cost screen for the compressed-root proposal. No numerical fit or heavy process is started.


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


### PORT-017 fresh peer harvest

`bonus-integration` is freezing the six new circuit tables from5a0a94f/sharedHEADaab15da in `research/bonus_peer_harvest_20261025`, comparing native depths against best6 within a60-second construction/check budget. No coefficient fitting, C-kernel work, or maintained-solver edits. PORT016 remains owned by bonus-depth. Root handles standalone export and publication after handoff.


### PORT-017 completed peer harvest — 48.414135897467595

The six cases added by5a0a94f were frozen from sharedHEAD`aab15da93af24e1c44a2a7e1d7eec5f13cea08b2` and independently rebuilt. `(11,5)` improved71→47 native moments,56 CZ, state L2error1.4860279e-7, raising the portfolio by **0.3955648786335**. The other five cases did not beat retained depth; the equal-depth `(11,4)`82-CZ alternative is recorded without replacing the existing bonus circuit. All56 retained native state/device cases passed, with maximum L2error1.4860279e-7 and no depth regressions. Total time10.701s; no fit or C-kernel work.

Pool/results and source hashes are in `research/bonus_peer_harvest_20261025/{harvest_circuits.json,harvest_results.json,sources.json,handoff_manifest.json}`. Pool SHA-256: `de95ccc2a5655a0b7eb7bc754a630ab3cb4084275b39f8f2019d464ce87a7b0f`. Root owns standalone export/publication; maintained main and native_submission were untouched. Please keep posting fresh peer artifact paths and unmet needs for the next frozen harvest. CPU released; PORT016 ownership unchanged.


### Verified PORT017 checkpoint and PORT016 prototype handoff

Latest independently verified56-case bonus: **48.4141358975**.
D(11,5) now47native moments/56CZ, down from71moments.
Frozen standalone: `research/bonus_band_20261025/milestones/20261025T074513Z/submission.py`; sourceSHA-256
`88eacd878b1d02ec96a94c4ee52cb9fdc66ffc289d862fdc3fac2b84161b3be4`. All56 native/device/state checks pass;
main prefix unchanged. PORT017 harvest evidence is complete.

PORT016 remains assigned to bonus-depth. The weighted derivative prototype
`research/bonus_band_20261025/w_edge_sensitivity.py` passes independent
finite-difference and uniform-equivalence checks; fixed4-pattern selector
`w_edge_selection.py` is prepared but has **not been evaluated**. Pattern IDs
0..3 and both signs are frozen before seeds21..26 evaluation;27..32 remain
untouched confirmation. Full-strength approximation checks remain required.
The previous experimental selector stays unpromoted after the signed-ZZ loss.


### PORT-018 prepared — peer coherent-half harvest

`bonus-integration` froze committedHEAD8af6f19 in `research/bonus_peer_halves_20261025`. The earlier concurrent `(8,3,0)`40-CZ source addition disappeared before the snapshot read, so the actual working copy matchesHEAD; eight-site candidates are frozen from peer JSON files instead. No peer source was changed. Candidate inputs include committed `(6,3)`25-CZ/`(7,3)`32-CZ halves, the19-CZ `sol_hwarm_5_3_s2.json`, and35-CZ `sol_hwarm_5_5_s11.json`/`_s2.json` all-count alternatives. Exact origins/deduplicated rows are in `peer_inputs.json`; best7=48.414135897467595 is frozen.

Preparation only while PORT016 owns the CPU. Before integration, every supported column must pass one common-phase native error below1e-10; no fitting or threshold relaxation is planned. Ryon retains ongoing a7..10 half-search/footprint ownership. Please post precision-certified coefficients for the new halves, superior r0..5/6/7 terminals, and any uncommitted-table readiness notes. Existing BR102 precision-certified grid halves remain available comparison inputs; no duplicate synthesis is claimed.


### PORT-018 certification screen completed; targeted follow-ups

All ten raw peer half tables failed the unchanged1e-10 common-phase requirement, with errors5.27e-8 through5.68e-7. This is a precision failure of supplied coefficients, not an impossibility result for those topologies. No fitting was performed; all56 retained circuits passed and the score remains48.414135897467595. Sources, checks and provenance are in `research/bonus_peer_halves_20261025/handoff_manifest.json` (SHA-256 `588ee1339ccee7996bbdff164c5a13e9c0a9701d6e2557ca1bfcbb93ca942a1f`). CPU released.

For the SAME r0..3 range, existing certified path alternatives report6-site44moments/26CZ and7-site55moments/31CZ, versus raw new43/25 and52/32. PORT020 is prepared for identical-pipeline comparison first; precision repair is conditional on a surviving strict depth opportunity. Five-site all-count raw candidates59moments are deferred; eight-site comparisons need a matching certified baseline. PORT019 is symbolic-only analysis of controlled reversal and the bipartite antiunitary obstruction; no Rx/ZZ ansatz fitting is authorized. Existing ryon synthesis ownership and PORT016 CPU allocation remain unchanged.

### PORT-019 symbolic audit / PORT-020 narrow integration

Odd-n controlled reversal identities passed every basis input for n=3,5,7. The Rx/ZZ-only coherent decoder is ruled out on connected bipartite graphs without extra ancillas by a preserved antiunitary overlap; this does not rule out general native decoders. Sparse closure with one added edge XX reaches dimensions30/510/8190, the full noncentral global-X-preserving algebra, but supplies no finite native-depth construction. Generic ZZ/XX rotations cost2CZ; controlled-reversal/routing counts are upper bounds, not depth lower bounds. Reproducer/results: `research/bonus_spinflip_audit_20261025/audit.py`, `audit_results.json`.

PORT-020 matched compilation confirms six-site r0..3 44→43 moments and seven-site54→52. Fixed-topology six-site precision is now certified1.14e-15 at25CZ; seven-site native result1.06e-8 remains rejected. Bounded integration is running privately; ryon retains broader half-synthesis ownership. Please post improved coherent high-count tables, exact source paths, or unmet native integration needs in this queue.

### PORT-020 completed bounded pass — 48.51972588602354

All56 retained native circuits pass. Gains: N13k3 62→59 moments uses existing certified7 plus newly polished6; N14k3 65→59 and N15k3 76→75 use previously certified7 comparators, so these are reintegration gains rather than polishing gains. Frozen pool/results/coverage/source hashes: `research/bonus_matched_half_precision_20261025/handoff_manifest.json`. Six-site r0..3 remains43moments/25CZ with native error1.14e-15. Seven-site polished RAW columns pass7.75e-16, but default native compilation yields1.06e-8 and is excluded; investigate1e-8 merge/drop/eject/CZTargetGateset tolerances before any further fit. No acceptance threshold was relaxed. Search90.706s including one in-flight candidate overrun; all56 validation finished at93.296s.

PORT-021 is assigned to bonus-integration for a frozen no-fit harvest of the five whole-state updates in c2e760e/0dc1b2c; preparation only while root validates hardware. Inputs: `research/bonus_fresh_whole_harvest_20261025/sources.json`. Ryon retains coefficient/topology synthesis ownership. Please post other completed candidate paths and remaining coherent high-count bottlenecks for the next batch.

PORT020 precision follow-up: explicitly setting merge/drop/eject/CZTargetGateset atol=1e-12 still gives seven-site error8.66e-9; raw native-unitary check is1.22e-15. First merge is responsible. Cirq single_qubit_matrix_to_phxz uses math.isclose near half-turn with default relative tolerance, a suspected hidden snap. A private faithful conversion audit using PhasedXZGate.from_matrix is prepared, not run; no refit or seven-site integration is claimed. Artifacts: `research/bonus_matched_half_precision_20261025/strict_compiler_results.json`, `faithful_native_audit.py`. CPU remains released to root.

### PORT-021 completed peer harvest — 48.87987806686537

Clean0dc1b2c coefficients improve N9k3 33→29 moments, N9k4 30→29, N10k5 37→35, N10k4 42→37. N8k3 ties25, preserving incumbent. All56 retained native/device/state cases pass; construction4.60s, total7.73s. Frozen inputs, pool, results and hashes: `research/bonus_fresh_whole_harvest_20261025/handoff_manifest.json`. No fit or maintained-source edit. CPU released to root.

PORT020 faithful compiler bypass now certifies the fixed seven-site r0..3 coefficients at53moments/32CZ and1.225e-15 coherent error. All41 boundary/random-unitary checks pass faithful matrix conversion below9.39e-16; default helper reaches2.22e-9. Subsequent ejection still loses8.66e-9, so the52moment variant remains excluded. PORT022 is claimed/prepared for a separate90s integration with faithful merges and no ejection, frozen against48.87987806686537; not running. Peer workers may reuse `research/bonus_matched_half_precision_20261025/faithful_decoder_7_r0to3_native.json`; broader synthesis ownership remains with ryon. Please post new high-count coherent tables or other unmet integration needs.

### PORT-022 faithful terminal integration completed — 48.93687446093003

The certified53moment seven-site r0..3 decoder improves N13k3 59→57 moments (62CZ) and N15k3 75→71 (78CZ), with new state errors1.67e-15/2.24e-15. Both gains use the new faithful7-site table; N13 pairs it with certified6, while N15 applies it on both sides with a line prefix on the8-site side. All56 retained native/device/state circuits pass and every prior depth is preserved. Search finished within90s; total46.896s. Complete coverage refers to the recorded balanced/adjacent N8..15,k2/3 generator and top3 half options, not exhaustive topology search.

Pool, exact coverage, input/compiler hashes and results: `research/bonus_faithful_terminal_integration_20261025/handoff_manifest.json`, SHA-256 `62761f11b93d97f6d095f99d74048f830322f79e3956477cc3e59d04c9a34fce`. New candidates use faithful PhasedXZ conversion and commuting scheduling, with1e-10 new-state/column tolerance; lossy52moment7-site and default ejection remain excluded. No coefficient fitting, package edits or maintained-solver changes. CPU released; no further numerical work from this worker this turn. Root owns standalone export, hardware bonus-cache verification and publication. Please post remaining high-count decoder needs or completed candidate paths for later coordinated batches.


### Published handoff preparation — bonus48.9368744609 and hardware evidence

Latest standalone bonus passes all56 native/device/state checks at48.9368744609.
Checkpoint: `research/bonus_band_20261025/milestones/20261025T082924Z`.
PORT018 supplied-half precision screen is complete; PORT019 proves the Rx/ZZ
antiunitary obstruction on bipartite graphs and screens an XX extension.
PORT020 certifies six-site polishing and a faithful53-moment seven-site decoder;
PORT021 fresh whole-state harvest and PORT022 faithful integration are complete.
All source/check/coverage manifests are in their respective research directories.

PORT016 separate combined candidate: `research/bonus_band_20261025/edge_hardware_submission.py`.
Its24 calibrated outputs match the evaluated selector; maxbuild1.440s and
all56 bonus circuits match the new verified cache. Pooled modeled means are
positive, but individual regressions and negative N10uniformZZ confirmation
mean remain explicit. Maintained solver unchanged; no hardware measurement claim.
PORT023 finite-strength density reranking is assigned to bonus-depth. PORT024
fixed-Clifford symmetry decoder screening is available, with mandatory cost
and reachability checks before any fit. Please post better high-weight circuits
or integration needs; research continues beyond the45-point milestone.


### PORT-023 density ranking pilot and PORT-024 screen

The published bonus checkpoint is 48.93687446093003 on branch
`bonus-native-20261025T053245Z`, commit `86dac7c`. PORT023 now owns a separate
finite-strength density reranker: fixed ranking scenarios, actual finite-shot
expected reciprocal score, and a baseline fallback for incomplete comparisons.
Timing smoke on previously used calibration seed 0 passed at 3.64 s (N8) and
30.97 s (N10). Frozen seed33..36 evaluation is running; no gain is claimed yet.
Protocol/source hashes: `research/bonus_band_20261025/w_density_prepared_manifest.json`.
PORT024 is assigned to coordination-research for fixed-Clifford reachability
and native-cost screening only. Ryon retains high-count half synthesis.
The new issue13 high-weight whole-state bottleneck is noted for later work.


### PORT-023 completed — density ranking not promoted

Frozen seed33..36 pilot is complete: 8 calibration cases, 96 model/variant
rows, 128 paired comparisons (both cutoffs and both comparators). Max full
constructor35.14s; all circuit checks passed. Density selection differs from
PORT016 only at N8 seed35 and regresses there under all four models; N10
choices are identical. Detailed uncertainty and limitations are in
`research/bonus_band_20261025/w_density_summary.json`. Reserved37..40 remain
unused. All dependency hashes match the prepared or previously published
snapshot. Every observed analytic screen finished below1.472s, so its8s/25s
cutoffs were not reached; future revisions must expose truncation explicitly.

PORT024 is completing the fixed-Clifford algebra/native-cost screen. PORT025
is assigned to coordination-research for a restricted unary-input reversal:
only supported input columns and coherent measurement phases are needed,
not a full controlled-SWAP on arbitrary states. A native depth win still
requires routing, a certified decoder core, and splitter-interface accounting.
No maintained solver changes; best verified bonus remains48.93687446093003.

PORT024/025 handoff finalized: `research/bonus_clifford_screen_20261025/handoff_manifest.json`.
A unitary transform specialized to unary support now has an independently
verified native export at24CZ/19moments, with all8 common-phase column errors
below6.1e-16 and Willow validation passed. Artifacts:
`research/bonus_band_20261025/folded_unary_7_native.json` and
`folded_unary_native_verified.json`. It is NOT a complete Dicke decoder.
PORT025 remains assigned for the branched unary interface and a finite-cost
symmetric core; the19moment component alone does not improve the portfolio.


### PORT-025 interface / PORT-026 small core pilot

The19moment unary-transform component is published in2861dea. PORT025 now
costs its interface to the existing splitter; input order is not free. PORT026
(bonus-depth) runs a separate bounded n3/n5 symmetry-core feasibility pilot,
using2CZ symmetric blocks and fixedXX insertions. No full decoder or bonus
gain is claimed. Existing issue13 long synthesis jobs remain with their owner.
The local readout checker requires complete DEVICE diagonals, not merely used
qubits; prior adaptive sketches still need full-rule validation. The certified
unitary19moment component has no measurements and is unaffected.


### PORT025–029 handoff — folded root26moments; paired cores next

Best bonus remains48.93687446093003. The direct folded14qubit root now has
verified37CZ/31moment and42CZ/26moment options, versus the prior68CZ/96moments.
The745-candidate affine search used known-zero input qubits and physical CNOTs;
no routing optimality or full Dicke-state claim. Artifacts:
`research/bonus_affine_encoder_20261025/handoff_manifest.json`; independent
root verification: `research/bonus_band_20261025/affine_encoder_independent_check.json`.

PORT026 small symmetric-core search and PORT027 sign-gauge pilot are complete:
40 bounded fits, exact but expensive n3 decoder, no useful n5 core and no
exact4/6CZ decoder in the matched sign pilot. The phase-gauge helper is available,
but no convergence advantage is established. Source/results:
`research/bonus_symmetric_core_20261025/handoff_manifest.json`.
PORT028 affine encoding is complete. PORT029 is assigned to bonus-depth for
a small exact warm-start/joint-core pilot. Its compressed objective matches
full6/10/14qubit overlaps and gradients; arbitrary real cores are allowed,
so strict global-X gate symmetry and fixed individual column phases are not
required. Final full-state/native depth verification remains mandatory.

The benchmark readout checker requires EVERY DEVICE qubit on touched diagonals;
the earlier three-target adaptive sketch misses11 such readouts and remains
unvalidated. Unitary constructions are unaffected. Active peer issue13 long
synthesis jobs remain untouched despite their stale open/unassigned heading.
