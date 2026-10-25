# Independent review: optimized synthesis integration

Final disposition: CLOSED. Both findings below were fixed by the parent and independently rechecked against the resulting files. No open actionable findings remain in the reviewed optimized-synthesis scope. The original findings and reproducers are retained below as pre-fix evidence.

## [P2] Keep the omitted-construction fallback for legacy datasets

Location: `/Users/valentine/github/hackathons/DuQuantum-2026/claude/scripts/diagnose.py:263–268`.

The new `construction="analytic"` fallback is applied only when `has_complete_provenance(dataset)` is true and the DD preparation mapping is nonempty. A legacy dataset without that provenance reaches `dp.PrepConfig()` instead, whose new default is `optimized`. Thus supported historical input without the field changes its reconstructed diagnostic circuit, despite the explicit plan/README guarantee that omitted construction retains the original analytical constructor. D(6,3), for example, changes from the original 35 CZ to 29 CZ, so the reconstructed depth, coupler loads and noise illustrations no longer describe its previous constructor.

Concrete reproducer, accepted by both the analyzer and CLI:

```python
legacy = {
    "complete": True,
    "signature": {"calibration_seed": 1234},
    "results": {
        "6,3,7,dd": {"score": 1.0},
        "6,3,7,no-dd": {"score": 1.1},
    },
}
# Save to legacy_scores.json, then:
loaded = load_results(path)  # succeeds
has_complete_provenance(loaded)  # False
resolve_report_settings(loaded)[2].construction  # 'optimized'
parse_args(["--mode", "diagnose", "--results", str(path)]).preparation.construction
# 'optimized'
```

Apply the analytical fallback whenever an existing dataset omits the setting, including legacy datasets; keep optimized as the default for a new report with no dataset. Add the legacy reproducer alongside the current regression that tests only a modern signature with construction removed. Evidence is saved as `legacy_scores.json`; `probe_results.json` also confirms modern omission resolves analytic while legacy omission resolves optimized.

## [P2] Propagate the exported construction policy to the bonus entry point

Location: `/Users/valentine/github/hackathons/DuQuantum-2026/claude/dicke_prep.py:890`.

`create_dicke_state_adaptive` creates a fresh `PrepConfig(use_dynamical_decoupling=False, search_time_s=10.0)` and therefore always uses the optimized constructor. The standalone exporter correctly embeds the requested `CONFIG`, but this entry point ignores its `construction`. Selecting analytic consequently exports two entry points with different construction policies, contrary to the chosen policy and the promise that analytic preserves the previous constructor.

Concrete reproducer:

```python
path = build_submission(
    tmp / "submission_analytic.py",
    configuration=dp.PrepConfig(construction="analytic"),
)
# Load that exported module as submission.
submission.CONFIG.construction  # 'analytic'
main, _ = submission.create_dicke_state(4, 2, *calibration)
bonus, _ = submission.create_dicke_state_adaptive(4, 2)
count_cz(main)   # 12, previous constructor
count_cz(bonus)  # 5, new square constructor
```

Inherit `CONFIG.construction` when building the bonus configuration, while retaining the intended bonus-specific DD/search settings. Add an export regression that checks both entry points under analytic and optimized configurations. The exact executed export is `submission_analytic.py`; measurements are in `probe_results.json`.

## Independent closure verification

`after_fix_results.json` records the narrow final recheck:

- A supported legacy dataset resolves analytic through both `resolve_report_settings` and CLI parsing.
- A modern recorded dataset missing the field resolves analytic; explicit optimized remains optimized; no dataset defaults to optimized.
- Standalone exports configured analytic use 12 CZ for D(4,2) in both main and bonus entry points; optimized uses 5 CZ in both.
- Both exports retain configured beam width 17. A requested 1-second bonus search remains 1 second; 20 seconds is capped at the original 10 seconds. DD stays disabled for the bonus path.
- All four exported main circuits and four bonus circuits pass exact preparation validation.

The remaining independent probes found no additional actionable issues:

- `probe_results.json`: 152 cases N=1–16 preserve the previous logical sequence and byte-equivalent analytic native operation lists; 304 construction/case edge-count checks agree with emitted gates. For all N=1–9, k=0–N, 216 native/off/dense/sparse state checks have worst amplitude residual 5.78e-15 after removing only common global phase.
- `square_cost_checks.json`: 12 random calibrated 4×4 graphs match the independently computed global square cost, including every orientation's repeated edge.
- `fallback_checks.json`: 5-CZ square is exact under DD off/dense/sparse; survives an intentionally failed/expired path search with routing disabled; a missing square edge selects the exact 9-CZ line fallback; a connected star without a full path remains exactly routable under both analytic (19 CZ) and optimized (16 CZ) policies.

Scope: repository/reference/Git/Downloads files were read only by this reviewer; all evidence and test exports were confined to this private directory. No hardware, remote write, noisy benchmark, notebook execution or full test suite was run by this reviewer; the parent owns those broader gates.
