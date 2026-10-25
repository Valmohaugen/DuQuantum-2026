# Bonus-first checkpoint

The primary optimization target is now the bonus objective:

`sum(N*k / emitted_native_moments)` for `N=2..15`, `k=1..floor(N/2)`.

Best verified checkpoint: **51.33366706608946**, across all **56 cases**.
Maximum emitted depth: **119 moments**. The competition awards one extra point
to the strongest bonus submission; this checkpoint is not a guarantee against
unseen competitors. Keep a valid main constructor, but prioritize bonus depth
over noisy-score tuning or CZ count. Higher CZ count is acceptable if it reduces
validated emitted moments. Avoid adding runtime synthesis or simulation.

- `submission.py`: self-contained submission with both entry points; all bonus
  circuits are compiled and stored as native layers. Its main path is preserved.
- `circuits.json`: editable Cirq circuits, indexed by `"N,k"`.
- `validation.json`: fresh complex128 state, native/device and constructor-time checks.
- `priorities.json`: per-case marginal score gain for removing one moment.
- `validate.py`: repeatable independent validation:
  `python -m research.bonus_priority_20261025.validate`.

The source matches the previously verified best13 standalone SHA-256
`b5a4e8bedaac1255ef88c1ff8bb7a148a6f0fcf98541f496e1ff4ccb361629f2`.
Validation records whether the stable-Cirq Willow device alias was needed.
The original challenge notebook is unchanged.

Next work should optimize the emitted schedule, then explore lower-depth native
topologies for the cases with meaningful attainable marginal gains. The ranking
in `priorities.json` is not a feasibility claim: Bell-state depth three is already
minimal. Interesting small cases include D(6,3) at 12 moments and W states with
N=7..15. Large balanced states have substantial depth, but removing one moment
there contributes less bonus score than many small-case reductions.

For each candidate, preserve Willow adjacency and the native gate set, and check
the full complex state including relative phase. Accept only strict depth gains;
retain the stronger state certificate on ties. Recompute all 56 contributions
before replacing this checkpoint. Adaptive schemes must obey the full-device
readout-diagonal constraint and prepare the correct state on every outcome;
postselection is not a valid shortcut.

Historical experiments under `research/bonus_band_20261025` and the shared issue
queue document prior no-gain searches. This package is sufficient to inspect,
validate and improve the best circuits without those experiments.
