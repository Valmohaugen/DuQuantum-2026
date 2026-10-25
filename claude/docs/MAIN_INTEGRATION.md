# Main branch integration — October 24, 2026

Development continues on `main`. This checkpoint combines upstream main `4225b90`
with the reviewed solution workflow previously at `d72fb65`. Existing teammate commits
remain in main's history; the reviewed changes are integrated as one source commit.

The canonical constructor is `claude/dicke_prep.py`, with the thin `solution.py` /
`solution.ipynb` entry points, full default workflow, focused CLI flags, persistent
figures, exported-entry-point coverage and the minimal-reference routing repair.
The current `ryon/` and `toby/` reference files are preserved from upstream main.
The new `toby/ladder_sol.py` teammate addition arrived during validation and is included.
The already-validated default comparison sources are unchanged by that additive commit.
They share the existing exclusion from maintained-code lint/format checks.

The public assistance-credit document and its links are omitted from this checkpoint.
Commit author and committer use the configured researcher identity, without added
credit trailers. The original challenge notebook remains byte-identical. A verified
private Git bundle preserves the previous branches and history before integration.

## Verification and handoff

| Phase | Completed checks | Remaining publication work |
| --- | --- | --- |
| Source integration | Latest teammate tree preserved; reviewed canonical sources retained; active branch is main | None |
| Preservation | Verified pre-integration Git bundle; all 2,486 saved artifacts and original notebook match the pre-integration ledger | None |
| Reference compatibility | All 168 circuits across 28 cases and six variants pass exact-state and native-device checks; zero reference errors | None |
| Notebook execution | Solution: 6 code cells; tutorial: 19 code cells; temporary output destinations | None |
| Static checks | Ruff lint/format and protected/generated artifact checks pass | Full installed commit hook gates creation of the source checkpoint |
| Public credit audit | Credit document and obsolete links removed; new commit uses the configured researcher identity | User publishes main and deletes the old remote branch |

The complete installed pre-commit gate, including the full offline suite, runs before
Git creates this checkpoint. Its captured log and final Git status are retained locally
under benchmark_outputs/main_integration/20261025T025922Z-main-integration/.
The old local work branch is removed after the source checkpoint exists; a verified
private Git bundle retains its history for recovery.

Updated reference evidence:
[comparison report](../../benchmark_outputs/main_integration/20261025T025922Z-main-integration/comparisons/20261025T025922Z-5abdf926cc50-a62033/report.md).

## Publication

Remote publication and remote branch deletion are performed manually under the global
repository standards. From the verified local `main`, push main successfully before
deleting the old remote branch. Figures and recorded run data remain saved locally in
their Git-ignored folders. Historical verification documents retain their original
checkpoint context; this file and Git's active branch describe current development.
