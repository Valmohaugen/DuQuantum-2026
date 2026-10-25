"""Revalidate a bonus-only cache change without repeating unchanged main checks."""
import ast
import hashlib
import json
from pathlib import Path

from . import edge_hardware_submission as candidate
from . import native_submission as bonus

ROOT = Path(__file__).parent


def without_bonus_table(source):
    tree = ast.parse(source)
    removed = []
    kept = []
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == '_BONUS_NATIVE'):
            removed.append(node)
        else:
            kept.append(node)
    assert len(removed) == 1
    tree.body = kept
    return ast.dump(tree, include_attributes=False)


def main():
    old = ROOT/'edge_hardware_pre_bonus_refresh.py'
    new = ROOT/'edge_hardware_submission.py'
    prior_path = ROOT/'edge_hardware_pre_bonus_refresh_verified.json'
    prior = json.loads(prior_path.read_text())
    assert hashlib.sha256(old.read_bytes()).hexdigest() == prior['candidate_sha256']
    assert without_bonus_table(old.read_text()) == without_bonus_table(new.read_text())
    # The cache is read solely by the adaptive constructor, never by main.
    readers = [node.name for node in ast.parse(new.read_text()).body
               if isinstance(node, ast.FunctionDef)
               and any(isinstance(x, ast.Name) and x.id == '_BONUS_NATIVE'
                       for x in ast.walk(node))]
    assert readers == ['create_dicke_state_adaptive']
    verified_bonus = json.loads((ROOT/'native_submission_verified.json').read_text())
    assert verified_bonus['cases'] == 56
    assert hashlib.sha256((ROOT/'native_submission.py').read_bytes()).hexdigest() == verified_bonus['source_sha256']
    count = 0
    for n in range(2, 16):
        for k in range(1, n//2+1):
            assert candidate.create_dicke_state_adaptive(n, k) == bonus.create_dicke_state_adaptive(n, k)
            count += 1
    report = dict(prior)
    report.update(candidate_sha256=hashlib.sha256(new.read_bytes()).hexdigest(),
                  preserved_sha256=verified_bonus['source_sha256'],
                  bonus_exact_matches=count, bonus_score=verified_bonus['score'],
                  bonus_refresh=dict(main_semantics_unchanged_except_unread_bonus_table=True,
                                     reused_main_validation=prior_path.name,
                                     reused_main_validation_sha256=hashlib.sha256(prior_path.read_bytes()).hexdigest(),
                                     old_candidate=old.name, new_bonus_validation='native_submission_verified.json',
                                     scope='Main checks reuse identical AST and globals except the cache, which only the adaptive wrapper reads. All56 new bonus circuits exactly match the independently state/native/device-verified export.'))
    (ROOT/'edge_hardware_verified.json').write_text(json.dumps(report, indent=2)+'\n')
    print('COMPLETE', report['candidate_sha256'], report['bonus_score'], flush=True)


if __name__ == '__main__':
    main()
