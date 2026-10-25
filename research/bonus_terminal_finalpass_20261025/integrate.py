"""Bounded reuse of existing native decoders; no synthesis or coefficient fitting."""
import argparse
import itertools
import json
import math
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np

from . import snapshot as b
from .probe import optimize
from .commuting_schedule import schedule

ROOT=Path(__file__).parent


def target(n,k):
    return np.array([int(i.bit_count()==k) for i in range(2**n)],dtype=float)/math.sqrt(math.comb(n,k))


def operations(qs,row):
    if not row.get('complex',False):
        return b.patch_ops(qs,row['edges'],row['angles'],row.get('zset',[]))
    x=row['angles'];edges=row['edges'];p=0;ops=[]
    input_z=len(x)==3*len(qs)+4*len(edges)
    for q in qs:
        if input_z:ops.append(cirq.rz(x[p]).on(q));p+=1
        ops.extend([cirq.ry(x[p]).on(q),cirq.rz(x[p+1]).on(q)]);p+=2
    for a,d in edges:
        ops.append(cirq.CZ(qs[a],qs[d]))
        for i in (a,d):
            ops.extend([cirq.ry(x[p]).on(qs[i]),cirq.rz(x[p+1]).on(qs[i])]);p+=2
    assert p==len(x)
    return ops+[cirq.Z(qs[i]) for i in row.get('zset',[])]


def compile_ops(ops):
    return b.compile_circuit(ops,dynamical_decoupling=False,pack=True)


def certify(name,row):
    n=row['n'];limit=row['k'];qs=[cirq.GridQubit(2,4+i) for i in range(n)]
    assert all(abs(a-d)==1 for a,d in row['edges'])
    c=schedule(optimize(compile_ops(operations(qs,row))),restarts=3)
    cirq_google.Willow105.validate_circuit(c)
    actual=cirq.unitary(c)[:,[(1<<r)-1 for r in range(limit+1)]].T
    goal=np.array([target(n,r) for r in range(limit+1)])
    overlap=np.vdot(goal,actual);phase=overlap/abs(overlap)
    errors=np.linalg.norm(actual-phase*goal,axis=1)
    check=dict(name=name,n=n,k=limit,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),max_column_error=float(max(errors)),column_errors=errors.tolist(),common_phase=[float(phase.real),float(phase.imag)],accepted=bool(max(errors)<1e-10))
    print('COLUMN',check,flush=True)
    return check


def load_decoders():
    # Exact Clifford refinements are copied, never recomputed in this pass.
    blocks=json.loads((ROOT/'clean_clifford_tables.json').read_text())['blocks']
    for key,row in blocks.items():b.block_angles[tuple(map(int,key.split(',')))]=row['angles']
    for key,row in json.loads((ROOT/'refined_halves.json').read_text()).items():
        b.halves[tuple(map(int,key.split(',')))]=(row['edges'],row['angles'],row['zset'])
    library=[];checks=[]
    for name in ['five_real','five_complex','six_real','five_four']:
        row=json.loads((ROOT/f'{name}.json').read_text())
        if name=='five_four':row.update(n=row['a'],complex=False,zset=[])
        check=certify(name,row);checks.append(check)
        if check['accepted']:library.append((name,row))
        elif name=='five_four':b.halves.pop((5,4,0),None)
    # Keep the already certified smaller terminal alternatives too.
    for key,data in b.halves.items():
        n,k,lo=key
        if lo or n>4:continue
        library.append((f'old-{n}-{k}',dict(n=n,k=k,edges=data[0],angles=data[1],zset=data[2] if len(data)>2 else [])))
    (ROOT/'decoder_checks.json').write_text(json.dumps(checks,indent=2))
    return library


def half_options(qs,k,blocks,library):
    n=len(qs);steps,_=b.half_plan(n,k,blocks,0)
    options=[('standard',b.half_ops(qs,k,steps))]
    prefix,_=b.line_plan(n,k,blocks,0)
    for name,row in library:
        size=row['n']
        if size>n or row['k']<min(k,size):continue
        ops=b.line_ops(qs,k,[s for s in prefix if s[1]>size],False)
        options.append((name,ops+operations(qs[:size],row)))
    ranked=[]
    for name,ops in options:
        c=compile_ops(ops)
        ranked.append((len(c),sum(op.gate==cirq.CZ for op in c.all_operations()),name,ops))
    # Retain short alternatives; the final comparison includes the common root.
    return [(name,ops) for _,_,name,ops in sorted(ranked,key=lambda x:(x[0],x[1]))[:3]]


def verify(c,n,k):
    qs=sorted(c.all_qubits());assert len(qs)==n
    assert 0<len(c)<=1750
    assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
    cirq_google.Willow105.validate_circuit(c)
    state=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=qs).final_state_vector
    goal=target(n,k);overlap=np.vdot(goal,state)
    error=float(np.linalg.norm(state-goal*overlap/abs(overlap)))
    assert error<1e-5,(n,k,error)
    return error


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=90);args=parser.parse_args()
    start=time.monotonic();library=load_decoders()
    circuits=cirq.read_json(ROOT/'baseline_circuits.json')
    original={key:len(c) for key,c in circuits.items()};records=[];trials=0;coverage=[];attempts=[]
    dev=cirq_google.Willow105.metadata
    qrate={q:(1e-3,0.) for q in dev.qubit_set};prate={tuple(p):(1e-3,0.) for p in dev.qubit_pairs}
    adj,node=b.make_chip(prate,qrate,qrate,qrate,15,4)
    def consider(n,k,name,ops):
        nonlocal trials
        key=f'{n},{k}';c=compile_ops(ops);trials+=1
        attempt=dict(N=n,k=k,source=name,compiled_depth=len(c),best_depth=len(circuits[key]),status='compile-screen');attempts.append(attempt)
        # Most compiler gains are only a few moments; use an explicit bounded screen.
        if len(c)>len(circuits[key])+12:return
        c=optimize(c);attempt.update(optimized_depth=len(c),status='optimize-screen')
        if len(c)>=len(circuits[key])+2:return
        c=schedule(c,restarts=3);attempt.update(scheduled_depth=len(c),status='no-depth-gain')
        if len(c)>=len(circuits[key]):return
        error=verify(c,n,k);before=len(circuits[key]);circuits[key]=c
        row=dict(N=n,k=k,before=before,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),state_l2_error=error,source=name,trials=trials,seconds=time.monotonic()-start)
        attempt['status']='accepted';records.append(row);print('ACCEPT',row,flush=True)
        cirq.to_json(circuits,ROOT/'integration_circuits.json')
        (ROOT/'progress.json').write_text(json.dumps(dict(improvements=records,trials=trials,seconds=time.monotonic()-start),indent=2))
    # Resume exact unfinished groups, prioritizing the unvisited N13,k6 mirror.
    previous=json.loads((ROOT/'previous_coverage.json').read_text())
    pending=[x for x in previous['groups'] if x['status'] in ('partial','not-started')]
    pending.sort(key=lambda x:0 if (x['N'],x['k'],x['offset'])==(13,6,-1) else 1)
    previous_groups={(x['N'],x['k'],x['offset']):x for x in previous['groups']}
    previous_attempts={(x['N'],x['k'],x['source']) for x in previous['attempts']}
    work=[(x['N'],x['k'],x['offset']) for x in pending]
    for n,k,offset in work:
        a=(n+1)//2+offset
        item=dict(N=n,k=k,offset=offset,left_size=a,status='not-started',blocks=[])
        coverage.append(item)
        if not k<=a<=n-k:
            item['status']='infeasible-split';continue
        if time.monotonic()-start>=args.seconds:continue
        item['status']='partial';item['first_trial']=trials
        for blocks in (True,False):
            if time.monotonic()-start>=args.seconds:break
            entry=dict(blocks=blocks,status='placement-started',attempted=0,previously_attempted=0);item['blocks'].append(entry)
            prior=next((e for e in previous_groups[n,k,offset]['blocks'] if e['blocks']==blocks),None)
            if prior and prior['status'] in ('complete','no-placement'):
                entry.update(status=prior['status'],completed_in_previous_pass=True);continue
            lad=b.best_ladder(adj,node,n,k,blocks,lambda qs:0.,float('-inf'),a)
            if lad is None:entry['status']='no-placement';continue
            left,right,_,_=lad;root=b.split_ops(left,right,k)
            choices=list(itertools.product(half_options(left,k,blocks,library),half_options(right,k,blocks,library)))
            entry['planned']=len(choices)
            for (ln,lo),(rn,ro) in choices:
                if time.monotonic()-start>=args.seconds:break
                name=f'ladder-{a}-{blocks}-{ln}-{rn}'
                if (n,k,name) in previous_attempts:
                    entry['previously_attempted']+=1;continue
                consider(n,k,name,root+lo+ro)
                entry['attempted']+=1
            entry['status']='complete' if entry['attempted']+entry['previously_attempted']==len(choices) else 'partial'
        item['last_trial']=trials
        if len(item['blocks'])==2 and all(e['status'] in ('complete','no-placement') for e in item['blocks']):item['status']='complete'
        print('COVERAGE',item,flush=True)
    search_seconds=time.monotonic()-start
    (ROOT/'coverage.json').write_text(json.dumps(dict(search_budget_seconds=args.seconds,search_seconds=search_seconds,groups=coverage,attempts=attempts),indent=2))
    # Every retained circuit, including unchanged cases, is independently rechecked.
    validation=[];score=0.
    for key,c in circuits.items():
        n,k=map(int,key.split(','));tick=time.monotonic();copy=c.copy();qs=set(copy.all_qubits());build=time.monotonic()-tick
        assert build<60
        error=verify(copy,n,k);score+=n*k/len(copy)
        validation.append(dict(N=n,k=k,before=original[key],depth=len(copy),CZ=sum(op.gate==cirq.CZ for op in copy.all_operations()),state_l2_error=error,build_seconds=build))
    cirq.to_json(circuits,ROOT/'integration_circuits.json')
    report=dict(search_budget_seconds=args.seconds,search_seconds=search_seconds,coverage_file='coverage.json',status='56 retained explicit native circuits validated',cases=len(validation),baseline_score=sum(int(key.split(',')[0])*int(key.split(',')[1])/depth for key,depth in original.items()),score=score,trials=trials,seconds=time.monotonic()-start,improvements=records,rows=validation,constructor_note='Cached explicit circuit copy; final standalone export belongs to the parent publication pass')
    (ROOT/'integration_results.json').write_text(json.dumps(report,indent=2))
    print('COMPLETE',score,'trials',trials,'seconds',report['seconds'],flush=True)


if __name__=='__main__':main()
