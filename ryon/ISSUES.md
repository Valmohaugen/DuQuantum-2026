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

Baseline at 0dc262c: total 16.615. Current: **17.192** (3 seeds, N = 2..8). Bonus (N <= 15): 37.81.

## Open

### BONUS-010. Exact Clifford refits before depth compilation
Status: in progress (bonus research, isolated files)
`research/bonus_depth_20261024/clean_cliffords.py` fixes near-Clifford fitted
rotations to exact multiples of pi/2, then refits every remaining angle against
all coherent input columns. The aim is to expose commutation and cancellation
that numerical residuals in the current SCS tables may hide. No maintained
constructor changes are claimed. Acceptance: column error < 1e-10, then full
56-case native/device/state validation and recorded depth score. GitHub's
unauthenticated issues endpoint still returns 404; local queue is authoritative
for this coordination note.

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
- Ported multi-split ladder search from toby/combined_sol.py (tries splits outward from balanced for 8 s): 17.173 -> 17.192. Max build time 20 s at N = 20.
- Ladder half (4,3) on a path: 18 -> 12 CZ. (7,3) 0.789 -> 0.830, (8,3) 0.768 -> 0.824, and (9,3) 50 -> 44 CZ.
- Merged toby/ladder_sol.py (ladder split, doubling tree, two-variant bonus) with the patch table: 16.755 -> 17.077, bonus 26.35 -> 37.81.
- (6,2) 18 -> 14 CZ and (6,3) 33 -> 12 CZ on a 2x3 patch: E[s] 0.932 -> 0.962 and 0.825 -> 0.934.
- (5,2) on a 5-qubit patch: 11 CZ, E[s] 0.986 -> 1.005 (0dc262c).
