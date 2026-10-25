"""No-fit90s fresh-payload screen; preserve all56retained native cases."""
import itertools
import json
import time
import cirq
import cirq_google
import numpy as np
from . import helpers as h

ROOT=h.ROOT

def faithful(ops):
    def rewrite(op):
        q=next(iter(op.qubits))
        return cirq.PhasedXZGate.from_matrix(cirq.unitary(op)).on(q)
    return cirq.Circuit(cirq.merge_k_qubit_unitaries(cirq.Circuit(ops),k=1,rewriter=rewrite).all_operations())

def columns(row,c,qs):
    sim=cirq.Simulator(dtype=np.complex128)
    states=np.array([sim.simulate(c,initial_state=(1<<r)-1,qubit_order=qs).final_state_vector for r in range(row['k']+1)])
    goal=np.array([h.target(row['n'],r) for r in range(row['k']+1)])
    phase=np.vdot(goal,states);phase/=abs(phase)
    errors=np.linalg.norm(states-phase*goal,axis=1)
    return dict(max_column_error=float(max(errors)),column_errors=errors.tolist(),accepted=bool(max(errors)<1e-10))

def main():
    start=time.monotonic();deadline=start+90
    circuits=cirq.read_json(ROOT/'baseline_circuits.json');original={key:len(c) for key,c in circuits.items()}
    entries=json.loads((ROOT/'candidate_inputs.json').read_text())
    dev=cirq_google.Willow105.metadata;qr={q:(1e-3,0.) for q in dev.qubit_set};pr={tuple(e):(1e-3,0.) for e in dev.qubit_pairs}
    adj,node=h.b.make_chip(pr,qr,qr,qr,15,4)
    attempts=[];gains=[];half_checks=[];certified=[];coverage=[]
    def retain(n,k,label,c,strict=False):
        cirq_google.Willow105.validate_circuit(c)
        error=h.verify(c,n,k);key=f'{n},{k}'
        row=dict(N=n,k=k,source=label,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),state_l2_error=error,before=len(circuits[key]),accepted=False)
        attempts.append(row)
        if len(c)<len(circuits[key]) and (not strict or error<1e-10):
            row['accepted']=True;circuits[key]=c;gains.append(row.copy())
            cirq.to_json(circuits,ROOT/'refresh_circuits.json');print('ACCEPT',row,flush=True)
        return row
    # Whole-state inputs first; each payload is new relative to frozen0dc1b2c.
    for entry in [e for e in entries if e['table']!='halves']:
        item=dict(name=entry['name'],status='not-started');coverage.append(item)
        if time.monotonic()>=deadline:continue
        row=json.loads((ROOT/entry['name']).read_text());n,k=row['n'],row['k']
        if entry['table']=='patches':
            cells=row['cells'];r0=min(q[0] for q in cells);c0=min(q[1] for q in cells)
            qs=h.b.best_patch(adj,node,[(r-r0,c-c0) for r,c in cells],row['edges'])
        else:qs=[cirq.GridQubit(i,7) for i in range(n)]
        assert qs is not None
        ops=h.operations(qs,row)
        c=h.schedule(h.optimize(h.compile_ops(ops)),restarts=3)
        retain(n,k,entry['name']+':default',c)
        c=h.schedule(faithful(ops),restarts=3)
        retain(n,k,entry['name']+':faithful',c)
        item['status']='complete'
    for entry in [e for e in entries if e['table']=='halves']:
        item=dict(name=entry['name'],status='not-started');coverage.append(item)
        if time.monotonic()>=deadline:continue
        row=json.loads((ROOT/entry['name']).read_text());n,k=row['n'],row['k'];assert row.get('lmin',0)==0
        qs=[cirq.GridQubit(i,7) for i in range(n)];ops=h.operations(qs,row)
        raw=columns(row,cirq.Circuit(ops),qs)
        variants=[]
        for label,c in [('default',h.schedule(h.optimize(h.compile_ops(ops)),restarts=3)),('faithful',h.schedule(faithful(ops),restarts=3))]:
            cirq_google.Willow105.validate_circuit(c)
            check=dict(name=entry['name'],pipeline=label,n=n,k=k,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),**columns(row,c,qs))
            variants.append(check)
            if label=='faithful' and check['accepted']:certified.append((entry['name'],row,check))
        result=dict(name=entry['name'],n=n,k=k,raw=raw,variants=variants)
        if (n,k)==(7,3):result['same_range_incumbent_depth']=len(cirq.read_json(ROOT/'incumbent_7_r0to3_native.json'))
        if (n,k)==(6,4):result['certified_superset_incumbent_depth']=len(cirq.read_json(ROOT/'incumbent_6_allcounts_native.json'))
        half_checks.append(result);item['status']='complete';print('HALF',result,flush=True)
    (ROOT/'half_checks.json').write_text(json.dumps(half_checks,indent=2)+'\n')
    # Reuse only strict faithful certificates. No fitting or tolerance changes.
    if certified and time.monotonic()<deadline:
        h.compile_ops=faithful;h.optimize=lambda c:c
        h.b.halves={key:value for key,value in h.b.halves.items() if key[0]<=4}
        library=h.load_decoders()
        for name in ('polished_6_3','polished_7_3'):
            row=json.loads((ROOT/f'{name}.json').read_text());library.append((name,row));h.b.halves[row['n'],row['k'],0]=(row['edges'],row['angles'],row.get('zset',[]))
        for name,row,check in certified:
            library.append(('fresh-'+name,row));h.b.halves[row['n'],row['k'],0]=(row['edges'],row['angles'],row.get('zset',[]))
        fresh={(row['n'],row['k']) for _,row,_ in certified}
        for n,k in [(n,k) for k in (3,4) for n in (13,14,15,12,11,10)]:
            for a in dict.fromkeys([(n+1)//2,(n+1)//2-1,(n+1)//2+1,10]):
                if not k<=a<=n-k:continue
                if not any(size<=max(a,n-a) and limit>=k for size,limit in fresh):continue
                item=dict(N=n,k=k,left_size=a,status='not-started',attempted=0);coverage.append(item)
                if time.monotonic()>=deadline:continue
                item['status']='partial'
                for blocks in (True,False):
                    if time.monotonic()>=deadline:break
                    lad=h.b.best_ladder(adj,node,n,k,blocks,lambda qs:0.,float('-inf'),a)
                    if lad is None:continue
                    left,right,_,_=lad;root=h.b.split_ops(left,right,k)
                    choices=itertools.product(h.half_options(left,k,blocks,library),h.half_options(right,k,blocks,library))
                    for l,r in choices:
                        if time.monotonic()>=deadline:break
                        if not any(name.startswith('fresh-') or (name=='standard' and (size,k) in fresh) for (name,_),size in zip((l,r),(len(left),len(right)))):continue
                        c=h.schedule(faithful(root+l[1]+r[1]),restarts=3)
                        retain(n,k,f'fresh-half:{a}:{blocks}:{l[0]}:{r[0]}',c,strict=True);item['attempted']+=1
                if time.monotonic()<deadline:item['status']='complete'
    search_seconds=time.monotonic()-start;rows=[]
    for key,c in circuits.items():
        n,k=map(int,key.split(','));assert len(c)<=original[key]
        rows.append(dict(N=n,k=k,before=original[key],depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),state_l2_error=h.verify(c,n,k)))
    cirq.to_json(circuits,ROOT/'refresh_circuits.json')
    report=dict(status='All56retained native/device/state checks passed',cases=len(rows),search_budget_seconds=90,search_seconds=search_seconds,total_seconds=time.monotonic()-start,
        baseline_score=sum(int(key.split(',')[0])*int(key.split(',')[1])/d for key,d in original.items()),score=sum(r['N']*r['k']/r['depth'] for r in rows),
        improvements=gains,attempts=attempts,half_checks=half_checks,certified_fresh_halves=[name for name,_,_ in certified],coverage=coverage,rows=rows,
        no_fit=True,half_common_phase_tolerance=1e-10,whole_state_tolerance=1e-5)
    (ROOT/'refresh_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',report['score'],report['total_seconds'],flush=True)

if __name__=='__main__':main()
