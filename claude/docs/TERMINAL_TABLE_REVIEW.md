# Independent terminal-table review

October 24, 2026. Narrow read-only review of `claude/score_diagnostics.py` and
its benchmark/comparison integration. No repository, Git, historical artifact,
dependency, or hardware mutation was performed. New evidence is confined to
`/private/tmp/duq-table-review/`. No full test suite or density benchmark was repeated.

Reviewed helper SHA-256:
`807a522d419c7e29bcd9412acacc7ad5cfe36429dea4f635d1014fbb43a25de3`.

## Strengths

The table keeps the exact requested fourteen headers, in order:

```text
N n var CZ mom build rules ideal f Zfloor Zbias X E[s] sampled
```

The Z derivation is correct for the protected original scorer. Given target-sector
count M>0, the score is `S/M**2 sum_i(A_i-M/C)**2`; multinomial conditional moments
therefore give:

```text
E[Z | M>0] = S E[1/M | M>0] (1-sum_i q_i**2)
             + S sum_i(q_i-1/C)**2.
```

The implementation conditions the binomial count distribution in log space, rather
than replacing the random count by its mean. Its suffix-sum expression for
`1-sum(q**2)` avoids subtractive cancellation. The f=1, one-state sector, and empty
sector limits are handled consistently.

The X derivation correctly uses the variance of the per-shot average parity over
all subsets of an order. This retains covariance between subsets measured in the
same shot. Summing squared-error expectations across orders requires no additional
cross-order covariance term. The correlator cutoff is clamped to the same effective
range as the existing scorer.

`E[s]` is explicitly defined as the inverse conditional mean penalty, not the expected
reciprocal sampled score. The caveat is printed with the table and stored in the
benchmark signature/final payload and comparison identity/data/report. The original
finite-shot scorer and nonfinite sampled-score policy remain intact.

Both runners reuse the probability arrays already used for scoring. Diagnostic
calculation performs no simulation or random draw. Benchmark cache hits print saved
resource/diagnostic records before any reconstruction or sampling. Source provenance
now includes the diagnostics implementation, preventing incompatible old records
from masquerading as current table data.

## Issues

### Critical — none

### Important — none remaining

Two concrete edge issues were found, fixed, and independently rechecked:

1. A positive subnormal penalty could produce an overflowing reciprocal labeled
   finite, violating strict JSON serialization. The helper now stores a null value
   with explicit infinite status for an unrepresentable reciprocal. The original
   reproducer serializes successfully with `allow_nan=False`.
2. The formatter previously applied proxy status to unrelated missing numeric
   columns, which could print `ideal=inf` for an unavailable fidelity. Only score
   and proxy values now consult their respective statuses; other missing fields
   display `--`, while undefined/infinite scores display `undef`/`inf`.

The saved proxy-definition metadata was also added to match the documentation's
promise. No further implementation change is requested.

### Minor — none required for this request

The `E[s]` header remains potentially suggestive by itself, but retaining it is the
user's explicit formatting request. The adjacent terminal note and saved definition
adequately distinguish the diagnostic proxy from an expected sampled score.

## Independent verification

- **36 exact small-sample enumerations:** N=2–4, every n=0…N, S=1,2,3. Random fixed
  Z/X probability vectors were checked by enumerating complete shot sequences.
  X subsets and target correlations were enumerated directly, independently of
  the implementation's Krawtchouk expression. Maximum discrepancy across conditional
  Z means, X means/bias, and no-sector probabilities was `8.88e-16`.
- **Numerical survival limits:** f=`1e-300`, `1e-12`, 0.5, `1-1e-12`, and 1 at
  S=10,000 remained stable and strict-JSON-safe. For uniform two-state support,
  the conditional Z floors approach S/2 as f tends to zero and 1/2 as f tends to one.
- **Analytical fixtures checked:** S=2,f=1/2 gives Zfloor=5/6, X=1/2, proxy=3/4;
  full survival q=(3/4,1/4), S=4 gives Zfloor=3/8, Zbias=1/2, X=1/4,
  proxy=8/9. Empty target sectors remain explicitly undefined.
- **Fresh benchmark integration:** one case, two seeds, two modes, with a fixed
  synthetic probability provider. Exactly two probability-provider calls and eight
  basis-sampling calls occurred, matching the previous cache behavior. All four
  sampled scores matched direct calls to the original scorer with the original
  RNG seed/domain and arrays.
- **Cached benchmark integration:** construction, probability simulation, and
  sampling were replaced with functions that raise. A full cache hit printed all
  four stored rows and completed with zero new calls.
- **Comparison integration:** one case, two seeds, three hybrid variants, with the
  same synthetic provider. Six probability-provider calls and twelve basis-sampling
  calls occurred, confirming that passing the arrays to the scorer avoids double
  simulation. Both seed tables contained the requested header.
- **Final edge verification:** reciprocal overflow is explicit and strict-JSON-safe;
  unrelated missing columns stay unavailable; the exact header order is unchanged;
  the current benchmark signature carries the complete table-definition note.

Evidence: `enumerate_score.py`, `results.json`, `integration_probe.py`,
`integration_results.json`, `final_checks.json`, and the fresh/cached/comparison
stdout files under `/private/tmp/duq-table-review/`. Runner integration probes used
synthetic probabilities and did not run density-matrix simulations.

The protected original challenge notebook was rehashed and remains
`ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1`.
The coordinator owns the final full-suite run and actual bounded terminal examples.

## Declined to judge

- Expected reciprocal-score claims: the new column deliberately does not make one.
- Hardware performance or a DD policy: outside this formatting/statistics request.
- Infinite-shot or unbounded allocation performance: the documented algorithm is
  O(shots), and this workflow uses bounded finite-shot experiments.
- Re-running full suites or prior physics/noise benchmarks: the coordinator is
  doing the required final quality gate; duplication was explicitly excluded.

## Assessment

**Ready to merge? Yes for the narrow table change, subject to the coordinator's
final project quality gate.**

The diagnostics match the original scorer's conditional mean penalties, preserve
subset covariance, and clearly label the retained `E[s]` header as a proxy. Both
table integrations preserve original sample draws and cached results. No remaining
review finding blocks the local handoff.
