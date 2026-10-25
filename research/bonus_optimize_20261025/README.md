# Combined bonus checkpoint: 52.16161121597764

Use **`submission.py`** as the current bonus-first standalone submission.
Both required entry points are present. All 56 corrected bonus cases pass
complex128 state, relative-phase, native-gate, Willow-connectivity and
constructor-time checks. `validation.json` records the tested runtime and
stable-Cirq Willow alias. The main constructor and all executable constructor
ASTs match the preceding checkpoint; only the native bonus table changed.

| Case | Previous moments | New moments | Previous CZ | New CZ |
| --- | ---: | ---: | ---: | ---: |
| D(5,2) | 13 | **11** | 9 | 10 |
| D(6,3) | 12 | **11** | 12 | 15 |
| D(8,3) | 23 | **21** | 25 | 33 |
| D(11,3) | 33 | **32** | 53 | 55 |
| D(11,4) | 61 | **60** | 85 | 82 |
| D(12,3) | 39 | **38** | 55 | 74 |
| D(13,3) | 55 | **50** | 60 | 96 |
| D(14,3) | 57 | **50** | 65 | 99 |
| D(15,3) | 67 | **51** | 73 | 102 |

Score rises from **51.33366706608946** to **52.16161121597764**,
a gain of **0.82794414988818**. Nine cases improve; the other 47 circuits
are exactly unchanged. The bonus objective remains
`sum(N*k/emitted_native_moments)` for N=2..15, k=1..floor(N/2).
The highest depth remains 119. This is a verified local improvement, not a
claim of a global optimum or a guaranteed win against unseen submissions.

The independent optimization stage reached **51.66344324819931** with two
learned small circuits and D(13,3)/D(14,3) recompilation gains. Those stage
artifacts are preserved as `independent_stage_summary.json` and
`independent_stage_submission.py`. A newer shared portfolio at revision
`f8572d0` independently validates at **51.83665440807965**; its seven strict
improvements are combined with the learned D(5,2)/D(6,3) circuits. CP-SAT then
removes one more moment from each of its D(13,3), D(14,3), D(15,3) circuits.
The final export improves that newer portfolio by **0.32495680789799**.
`fresh_peer_checks.json` records its source hash, checks and timings.

## What helped

1. Exact native circuit simplification plus forward/reverse commuting schedules
   reduced D(13,3) and D(14,3) in the independent stage. The accepted variants used collective phase zero;
   testing other collective Z phases produced no further gain in this pass. Those
   cases were superseded by the fresh shared portfolio during integration.
2. Offline variational optimization learned general complex single-qubit
   rotations for deliberately shallow CZ-layer architectures. D(6,3) uses five
   perfect matchings of a 2x3 grid; D(5,2) uses five maximum matchings of a
   five-site square-with-tail graph. Six single-qubit layers alternate with
   five CZ layers, giving eleven emitted moments. More CZ gates are worthwhile
   for this objective.
3. Analytic complex adjoint gradients and L-BFGS fit the exact Dicke target.
   A residual-based least-squares pass refined state errors to **7.94e-13**
   (D5k2) and **4.46e-14** (D6k3). Finite differences and an independent Cirq
   state calculation check the gradient implementation.
4. Learned weights are compiled into the immutable native-layer cache. Every
   call reconstructs a fresh circuit. The export uses the same imports and
   constructor code as the previous standalone; no solver or training library
   is needed at submission time. The shared portfolio's runtime squeeze and state
   simulations are also compiled away into the cache.

The existing cache already reconstructs circuits in milliseconds. More runtime
memoization does not change the number of emitted moments, so it does not
increase the bonus score. The useful learned weights are the angles that make
a shallower topology exact.

## What did not help, and limits

- CP-SAT proved all 56 pre-fitting gate lists optimally scheduled under the
  modeled diagonal-commutation constraints: 35 hit their direct lower bound,
  and 21 were certified by the solver. The two new learned circuits also hit
  their fixed-list lower bound of eleven. Exact scheduling improved three fresh
  shared circuits by one moment each; `summary.json` includes their optimality
  certificates. These are fixed-gate-list statements,
  not global circuit-depth lower bounds.
- The real Ry-only architecture search completed 64 fits without an exact
  improvement. General complex rotations found the successful six-qubit case;
  698 complex starts were recorded across the six-qubit targets.
- Warm-start complex refits after deleting individual CZ gates completed 324
  trials without another accepted reduction. The five-qubit architecture search
  found its accepted circuit on trial 229.
- A six-moment square D(4,2) architecture was tried from 256 starts without an
  exact fit. Keep the existing seven-moment circuit; failed fitting is not an
  impossibility proof.
- Search budgets are bounded CPU experiments with deterministic seeds. They
  do not exhaust all layouts or architectures. No new adaptive construction
  is claimed. Full-device readout-diagonal constraints still apply to any
  future adaptive scheme.

## Reproduce and continue

`best_circuits.json` and `submission.py` are the retained combined checkpoint.
`fresh_peer_circuits.json` freezes the independently checked shared inputs; the
export merges only strict depth improvements and preserves its primary code.
`summary.json` lists changes and the export hash; `validation.json` contains
all 56 state/resource checks; `priorities.json` ranks marginal one-moment gains.
Training sources, fitted angle vectors, exact scheduling certificates, logs
and failed-trial records are kept alongside them.

With the existing Cirq environment:

```bash
python -m research.bonus_optimize_20261025.validate
```

Offline optimization additionally uses SciPy, GCC and OR-Tools 9.12.4544;
`runtime.txt` records the full environment. Example steps, in dependency order:

```bash
python -m research.bonus_optimize_20261025.search --seconds 240
python -m research.bonus_optimize_20261025.exact_schedule
python -m research.bonus_optimize_20261025.complex_fit
python -m research.bonus_optimize_20261025.learn_five
python -m research.bonus_optimize_20261025.refine_weights
python -m research.bonus_optimize_20261025.export
python -m research.bonus_optimize_20261025.validate
```

`complex_kernel.c` is compiled only in the local `__pycache__` for training.
Its weights are refined and frozen before export. Preserve the published
checkpoint before rerunning scripts, since experiment files are writable.
The independent real-angle and single-CZ pruning experiments have their own
scripts and logs. Other promising work is architecture search that permits
more parallel CZs, shared multi-column decoder learning, and exact adaptive
constructions with legal readout. Validate full complex states before accepting
any learned circuit; depth-only reward without correctness is insufficient.
