"""Cost-first same-range terminal comparison; no fitting or pool mutation."""
import json
import time
import cirq
import cirq_google
import numpy as np
from . import helpers as h

ROOT=h.ROOT

def faithful(ops):
    def rewrite(op):return cirq.PhasedXZGate.from_matrix(cirq.unitary(op)).on(next(iter(op.qubits)))
    return h.schedule(cirq.Circuit(cirq.merge_k_qubit_unitaries(cirq.Circuit(ops),k=1,rewriter=rewrite).all_operations()),restarts=3)

def main():
    start=time.monotonic();deadline=start+30
    blocks=json.loads((ROOT/'clean_clifford_tables.json').read_text())['blocks']
    for key,row in blocks.items():h.b.block_angles[tuple(map(int,key.split(',')))]=row['angles']
    refined=json.loads((ROOT/'refined_halves.json').read_text())
    library=[]
    for key,row in refined.items():
        n,k,lo=map(int,key.split(','));assert lo==0
        library.append((f'certified-{n}-{k}',dict(row,n=n,k=k)))
    for name in ('certified_5_3','polished_6_3','polished_7_3'):
        row=json.loads((ROOT/f'{name}.json').read_text());library.append((name,row))
    for name,n,k in [('native5_r4',5,4),('native5_all',5,5),('native6_all',6,6)]:
        c=cirq.read_json(ROOT/f'{name}.json');source_qs=[cirq.GridQubit(2,4+i) for i in range(n)]
        assert c.all_qubits()==set(source_qs)
        library.append((name,dict(n=n,k=k,native=c,source_qubits=source_qs)))
    def tail(qs,row):
        if 'native' in row:return list(row['native'].transform_qubits(dict(zip(row['source_qubits'],qs[:row['n']]))).all_operations())
        return h.operations(qs[:row['n']],row)
    checks=[];coverage=[]
    def check(n,k,label,ops,category):
        qs=[cirq.GridQubit(i,7) for i in range(n)]
        c=faithful(ops);cirq_google.Willow105.validate_circuit(c)
        assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
        sim=cirq.Simulator(dtype=np.complex128)
        states=np.array([sim.simulate(c,initial_state=(1<<r)-1,qubit_order=qs).final_state_vector for r in range(k+1)])
        targets=np.array([h.target(n,r) for r in range(k+1)])
        phase=np.vdot(targets,states);phase/=abs(phase)
        errors=np.linalg.norm(states-phase*targets,axis=1)
        result=dict(n=n,k=k,label=label,category=category,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),max_column_error=float(max(errors)),column_errors=errors.tolist(),accepted=bool(max(errors)<1e-10))
        checks.append(result)
        if result['accepted']:cirq.to_json(c,ROOT/f'{n}_{k}_{label}.json')
        print(result,flush=True)
        return result
    for n,k in [(6,4),(8,3)]:
        row=json.loads((ROOT/f'peer_{n}_{k}.json').read_text());qs=[cirq.GridQubit(i,7) for i in range(n)]
        check(n,k,'supplied-peer',h.operations(qs,row),'peer-uncertified')
        for use_blocks in (True,False):
            prefix,_=h.b.line_plan(n,k,use_blocks,0)
            for name,decoder in [('full-line',None)]+library:
                if decoder and (decoder['n']>n or decoder['k']<min(k,decoder['n'])):continue
                label=f'{name}-blocks{int(use_blocks)}';item=dict(n=n,k=k,label=label,status='not-started');coverage.append(item)
                if time.monotonic()>=deadline:continue
                if decoder:
                    ops=h.b.line_ops(qs,k,[step for step in prefix if step[1]>decoder['n']],False)+tail(qs,decoder)
                else:ops=h.b.line_ops(qs,k,prefix,False)
                check(n,k,label,ops,'incumbent-composition');item['status']='complete'
    comparisons=[]
    for n,k in [(6,4),(8,3)]:
        peer=next(r for r in checks if (r['n'],r['k'],r['category'])==(n,k,'peer-uncertified'))
        valid=[r for r in checks if (r['n'],r['k'])==(n,k) and r['category']=='incumbent-composition' and r['accepted']]
        best=min(valid,key=lambda r:(r['depth'],r['CZ']))
        comparisons.append(dict(n=n,k=k,peer=peer,best_certified_same_range=best,strict_depth_opportunity=peer['depth']<best['depth'],
            caveat='Peer depth is measured before coefficient repair; no precision or post-repair depth guarantee.'))
    result=dict(status='Cost-first same-range screen only; no fitting',budget_seconds=30,seconds=time.monotonic()-start,
        pipeline='Faithful PhasedXZ.from_matrix local fusion and fixed commuting_schedule(restarts=3); no default ejection/drop/gateset pass.',
        checks=checks,coverage=coverage,comparisons=comparisons,baseline_score_unchanged=49.111519281511065,
        native_tail_provenance='Frozen5/6native terminals were exported with logical qubit order GridQubit(2,4+i); remapped without reversing input columns. Every composed r0..k column was independently rechecked.',
        scope='Standard flagged/block prefixes plus frozen certified4/5/6/7tails; not an exhaustive topology or compiler search. Shared issue11/13 ownership preserved.')
    (ROOT/'triage_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMPARISONS',json.dumps(comparisons),flush=True)

if __name__=='__main__':main()
