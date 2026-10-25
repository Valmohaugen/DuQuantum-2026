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

Baseline at 0dc262c: total 16.615. Current: **17.077** (3 seeds, N = 2..8). Bonus (N <= 15): 37.81.

## Open

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
then prune. (7,2) went 22 -> 18 in about 3 minutes this way.
Shapes to try: 2x3, 2x3+1, 2x4, 3x3 minus a corner. Rank finalists with `fast_eval`, not by CZ
count alone, because depth also costs idle decoherence.

### 2. Evaluate larger N
`fast_eval` stops at N = 8, but the judges' N range is unknown. Add N = 9..12 (density matrix
size 4^N, so N = 12 is about 256 MB) with fewer seeds, so changes aren't tuned to small N only.

### 3. Better n >= 2 construction for N >= 9
Partly done: toby's two-half ladder (toby/ladder_sol.py) is merged into toby_sol and chosen per
case by `estimate_error`. That selector is crude: on (5,2) and (6,2) it sometimes picks the
option that simulates worse. A better estimate (or a small numpy noise simulation for N <= 8,
since numpy is a cirq dependency) would fix it.
The line split-and-cyclic-shift costs about 5 CZ per flagged gate and uses only a path. Options
to evaluate: a grid-native layout (shorter paths between the SCS blocks), divide-and-conquer
(Aktar, Bartschi, Badawy, Eidenbenz, IEEE TQE 2022), and the short-depth 2D construction of
Bartschi and Eidenbenz (arXiv:2207.09998).

### 4. Noise-model realism
The harness has no ZZ crosstalk, leakage, coherent CZ phase errors or drift. Add a simple ZZ
term (for example, about 100 kHz static ZZ between idle neighbours) and check that the DD and
scheduling choices still win.

### 5. Bonus question: adaptive circuits with lower depth (2 <= N <= 15)
The bonus compares moment counts and allows mid-circuit measurement with feed-forward. The current
code returns the packed standard circuit. Ideas: measurement-based fusion of W states, or the
constant-depth LAQCC Dicke constructions (Buhrman, Folkertsma, Loff, Neumann 2023). Respect the
readout-line rule: qubits with the same row + col can't be measured on their own.

### 6. X-basis term for n near N/2
For (8,4), X is about 0.42 out of 1.77 in the denominator. High-weight X correlators decay with
dephasing. Check how much comes from depth and how much from CZ error, and whether a different
DD placement or a shallower schedule recovers it.

## Done
- Merged toby/ladder_sol.py (ladder split, doubling tree, two-variant bonus) with the patch table: 16.755 -> 17.077, bonus 26.35 -> 37.81.
- (6,2) 18 -> 14 CZ and (6,3) 33 -> 12 CZ on a 2x3 patch: E[s] 0.932 -> 0.962 and 0.825 -> 0.934.
- (5,2) on a 5-qubit patch: 11 CZ, E[s] 0.986 -> 1.005 (0dc262c).
