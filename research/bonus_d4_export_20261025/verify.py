"""Bounded standalone equivalence, exact-state, and calibration-roundtrip checks."""
import ast
import hashlib
import importlib.util
import json
import math
import time
from pathlib import Path
import cirq
import cirq_google
import numpy as np

ROOT=Path(__file__).parent


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def statecheck(c,qs,n,k,tolerance):
    assert len(qs)==n and c.all_qubits()==set(qs)
    cirq_google.Willow105.validate_circuit(c)
    assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
    state=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=sorted(qs)).final_state_vector
    target=np.array([int(i.bit_count()==k) for i in range(2**n)])/math.sqrt(math.comb(n,k))
    phase=np.vdot(target,state);error=float(np.linalg.norm(state-target*phase/abs(phase)))
    assert error<tolerance
    return error


def main():
    start=time.monotonic();deadline=start+90
    path=ROOT/'d4_hardware_submission.py';source=path.read_text();base=(ROOT/'baseline.py').read_text()
    assert source.startswith(base)
    tree=ast.parse(source);old=ast.parse(base)
    assert all(ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False) for a,b in zip(old.body,tree.body))
    functions=[n.name for n in old.body if isinstance(n,ast.FunctionDef)]
    imports=[n for n in ast.walk(tree) if isinstance(n,(ast.Import,ast.ImportFrom))]
    assert all(not isinstance(n,ast.ImportFrom) or (not n.level and 'research' not in (n.module or '')) for n in imports)
    assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='open' for n in ast.walk(tree))
    assert 'read_json' not in source and 'read_text' not in source
    solver=load('standalone_d4_prototype',path.name);baseline=load('frozen_d4_baseline','baseline.py');bonus=load('verified_bonus','verified_bonus_source.py')
    # Execute the exact reader that was added after the pilot, without running its module.
    implementation=(ROOT/'pilot_implementation.py').read_text();impltree=ast.parse(implementation)
    reader=next(n for n in impltree.body if isinstance(n,ast.FunctionDef) and n.name=='calibration_for')
    namespace=dict(ROOT=ROOT,cirq=cirq,json=json)
    exec(compile(ast.Module(body=[reader],type_ignores=[]),str(ROOT/'pilot_implementation.py'),'exec'),namespace)
    readcal=namespace['calibration_for'];roundtrips=[];rows=[]
    pools={0:cirq.read_json(ROOT/'pilot_circuits.json'),1:cirq.read_json(ROOT/'confirmation_circuits.json')}
    reports={0:json.loads((ROOT/'pilot_results.json').read_text()),1:json.loads((ROOT/'confirmation_results.json').read_text())}
    for seed in range(41,79):
        assert time.monotonic()<deadline
        serialized=json.loads((ROOT/f'calibration_{seed}.json').read_text());cal=readcal(seed)
        encoded=[]
        for index,dictionary in enumerate(cal):
            encoded.append([dict(key=[[q.row,q.col] for q in key] if index==0 else [key.row,key.col],value=list(value)) for key,value in dictionary.items()])
        assert encoded==serialized
        # Independent parser uses the declared map index rather than runtime key type.
        independent=tuple({(tuple(cirq.GridQubit(*q) for q in e['key']) if i==0 else cirq.GridQubit(*e['key'])):tuple(e['value']) for e in entries} for i,entries in enumerate(serialized))
        assert cal==independent
        roundtrips.append(dict(seed=seed,maps=4,entries=sum(map(len,cal)),reader_AST_sha256=hashlib.sha256(ast.dump(reader,include_attributes=False).encode()).hexdigest()))
        cohort=int(seed>=47);selection=next(x for x in reports[cohort]['selections'] if x['seed']==seed)['selected']
        reference=pools[cohort][f'{seed}-{selection}']
        tick=time.monotonic();c,qs=solver.create_dicke_state(4,2,*cal);elapsed=time.monotonic()-tick
        assert elapsed<60 and c==reference and qs==set(reference.all_qubits())
        solver.check_circuit(c,*cal[:2]);error=statecheck(c,qs,4,2,1e-10 if selection=='candidate' else 1e-5)
        rows.append(dict(seed=seed,selection=selection,seconds=elapsed,moments=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),state_l2_error=error))
    fallback=[];cal=readcal(41)
    for n,k,opts in [(4,1,{}),(5,2,{}),(10,5,{}),(4,2,{'dynamical_decoupling':False}),(4,2,{'pack':True}),(4,2,{'use_blocks':False})]:
        assert time.monotonic()<deadline
        tick=time.monotonic();result=solver.create_dicke_state(n,k,*cal,**opts);elapsed=time.monotonic()-tick
        reference=baseline.create_dicke_state(n,k,*cal,**opts)
        assert result==reference and elapsed<60
        c,qs=result;solver.check_circuit(c,*cal[:2]);error=statecheck(c,qs,n,k,1e-5)
        fallback.append(dict(N=n,k=k,options=opts,seconds=elapsed,state_l2_error=error,exact_baseline_match=True))
    bonusrows=[]
    for n in range(2,16):
        for k in range(1,n//2+1):
            assert time.monotonic()<deadline
            tick=time.monotonic();actual=solver.create_dicke_state_adaptive(n,k);elapsed=time.monotonic()-tick
            assert actual==bonus.create_dicke_state_adaptive(n,k)
            c,qs=actual;cirq_google.Willow105.validate_circuit(c)
            assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
            bonusrows.append(dict(N=n,k=k,moments=len(c),seconds=elapsed))
    score=sum(x['N']*x['k']/x['moments'] for x in bonusrows)
    verified=json.loads((ROOT/'verified_bonus_report.json').read_text());assert abs(score-verified['score'])<1e-12
    report=dict(status='Passed; separate unpromoted standalone D4 prototype',candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),baseline_prefix_byte_identical=True,baseline_original_function_ASTs_preserved=functions,selected_matches=len(rows),selected_rows=rows,calibration_reader_roundtrips=roundtrips,fallback_checks=fallback,bonus_exact_matches=len(bonusrows),bonus_score=score,bonus_rows=bonusrows,bonus_state_validation='Reuse independently verified source report after exact56circuit equality; no redundant state simulations.',max_build_seconds=max(x['seconds'] for x in rows+fallback+bonusrows),maximum_selected_state_error=max(x['state_l2_error'] for x in rows),total_seconds=time.monotonic()-start,budget_seconds=90,runtime_dependencies='Single file; standard library plus cirq/cirq_google; constructors read no files or research modules.',limitations='Only N4k2 defaultDD=True,pack=False,use_blocks=True uses evaluated selector. Coherent-error mean remains unresolved; no hardware guarantee, W-selector composition, maintained edit, or promotion.')
    (ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',report['candidate_sha256'],score,report['total_seconds'],report['max_build_seconds'],flush=True)


if __name__=='__main__':main()
