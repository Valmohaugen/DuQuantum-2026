"""Refresh only the bonus cache of the independently validated D4 prototype."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).parent
PRIOR=ROOT.parent/'bonus_d4_export_20261025'


def split_table(source):
    tree=ast.parse(source)
    nodes=[n for n in tree.body if isinstance(n,ast.Assign)
           and any(isinstance(t,ast.Name) and t.id=='_BONUS_NATIVE' for t in n.targets)]
    assert len(nodes)==1
    node=nodes[0]
    tree.body.remove(node)
    return ast.dump(tree,include_attributes=False),node


def main():
    old=PRIOR/'d4_hardware_submission.py'
    prior=json.loads((PRIOR/'validation.json').read_text())
    assert hashlib.sha256(old.read_bytes()).hexdigest()==prior['candidate_sha256']
    verified=json.loads((ROOT/'native_submission_verified.json').read_text())
    native=ROOT/'native_submission.py'
    assert verified['cases']==56 and hashlib.sha256(native.read_bytes()).hexdigest()==verified['source_sha256']
    before,node=split_table(old.read_text())
    _,new_node=split_table(native.read_text())
    lines=old.read_text().splitlines(keepends=True)
    replacement=ast.get_source_segment(native.read_text(),new_node)+'\n'
    lines[node.lineno-1:node.end_lineno]=[replacement]
    text=''.join(lines)
    assert split_table(text)[0]==before
    readers=[n.name for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)
             and any(isinstance(x,ast.Name) and x.id=='_BONUS_NATIVE' for x in ast.walk(n))]
    assert readers==['create_dicke_state_adaptive']
    destination=ROOT/'d4_hardware_submission.py'
    destination.write_text(text)
    modules=[]
    for name,path in [('new_d4_bonus',destination),('reference_bonus',native)]:
        spec=importlib.util.spec_from_file_location(name,path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        modules.append(module)
    count=0
    for n in range(2,16):
        for k in range(1,n//2+1):
            assert modules[0].create_dicke_state_adaptive(n,k)==modules[1].create_dicke_state_adaptive(n,k)
            count+=1
    result=dict(status='Bonus-only refresh passed; guarded primary semantics unchanged',
                candidate_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                prior_candidate=str(old),prior_candidate_sha256=prior['candidate_sha256'],
                prior_validation=str(PRIOR/'validation.json'),
                prior_validation_sha256=hashlib.sha256((PRIOR/'validation.json').read_bytes()).hexdigest(),
                AST_identical_except_bonus_cache=True,bonus_cache_readers=readers,
                bonus_exact_matches=count,bonus_score=verified['score'],
                independent_bonus_source_sha256=verified['source_sha256'],
                reused_main_validation='38selectionmatches,38calibrationroundtrips,6fallbackmatches; original main AST and globals unchanged except the cache read only by adaptivewrapper.',
                limitations='Separate prototype, no maintained promotion or W-selector composition. Hardware modeled uncertainty remains reported in frozen pilot/confirmation and coupled-score summaries.')
    (ROOT/'d4_bonus_refresh_verified.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMPLETE',result['candidate_sha256'],result['bonus_score'],flush=True)


if __name__=='__main__':
    main()
