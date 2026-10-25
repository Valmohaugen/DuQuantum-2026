# Terminal diagnostic table

Request: display N, n, variant, native CZ/moments/build time, rule check, ideal fidelity,
sector survival f, Zfloor, Zbias, X penalty, E[s] proxy and sampled score. Print one table
per seed. Preserve the original challenge notebook and all earlier artifacts.

## Derivation from the original scorer

Let S be Z shots, M>0 the observed target-sector count, C=binom(N,n), q_i the conditional
probabilities inside that sector, and A_i the counts. The original scorer simplifies to:

Z = (1/C) sum_i[(A_i-M/C)^2/(M/C)] / (M/S)
  = S/M^2 sum_i(A_i-M/C)^2.

Given M, A is multinomial(M,q). Each squared deviation has expectation
Var(A_i)+(E[A_i]-M/C)^2 = M q_i(1-q_i)+M^2(q_i-1/C)^2.
Therefore E[Z|M] = S/M(1-sum q_i^2)+S sum(q_i-1/C)^2.
M is binomial(S,f). Conditioning on M>0 gives:

Zfloor = S E[1/M|M>0](1-sum q_i^2), Zbias = S sum(q_i-1/C)^2.

Compute the conditional binomial expectation in log space. Avoid cancellation in
1-sum q_i^2 by using 2 sum_{i<j}q_i q_j, evaluated with suffix sums.
At f=1 the floor is 1-sum q_i^2. For uniform two-state support, S=2,f=1/2,
M|M>0 has probabilities 2/3 at M=1 and 1/3 at M=2, giving Zfloor=5/6.
A one-state sector has zero Zfloor and Zbias. At f=0 they are undefined.

For an X outcome with Hamming weight w, the average order-r parity over all subsets is
h_r(w)=sum_j(-1)^j binom(w,j)binom(N-w,r-j)/binom(N,r).
For S independent outcomes, mean estimator variance is Var(h_r)/S. Thus each squared
correlator error has mean (mu_r-e_r)^2+Var(h_r)/S. Divide by e_r^2 when nonzero,
otherwise by1, exactly as the original scorer, then sum over requested orders to get X.
For r=N, h_r=(-1)^w. For ideal D(2,1), order1 contributes1/S and order2 contributes0.

The requested E[s] column is 1/(Zfloor+Zbias+X), conditional on observing target-sector Z
shots. It is an inverse-mean-penalty proxy, not E[1/(Z+X)]. The terminal footer and saved
metadata make this explicit. Nonfinite sampled outcomes and empty sectors stay explicit.

## Plan

- [x] Add exact finite-sample/statistical and live-output regressions; observe failures.
- [x] Implement shared diagnostics/formatting and integrate benchmark/comparison tables.
- [x] Save metrics, preserve cached behavior and keep density computation bounded.
- [x] Run focused/full gates and a bounded actual terminal run; update usage/status.

## Verification

406 tests passed in91.97s; all five pre-commit hooks pass. Independent exact enumeration
checked36small-sample cases with maximum discrepancy8.88e-16, plus tiny/near-one survival.
Overflow, empty sectors, missing fields and cached rows have regressions. Sampled scores
and RNG streams are unchanged; probability arrays are reused without extra simulation.
Standard six-case90record run and a two-case/two-seed comparison were executed. All earlier
artifacts remain separate; the protected original notebook is unchanged. Definitions are
also stored in raw JSON. Review: TERMINAL_TABLE_REVIEW.md.
