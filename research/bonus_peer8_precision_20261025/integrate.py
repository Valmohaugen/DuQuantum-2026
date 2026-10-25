"""Bounded changed-eight-site integration and frozen ten-site no-fit screen."""
import itertools
import json
import time
import cirq
import cirq_google
from . import helpers as h
from .polish import faithful


def merge(ops):
    def rewrite(op):return cirq.PhasedXZGate.from_matrix(cirq.unitary(op)).on(next(iter(op.qubits)))
    return cirq.Circuit(cirq.merge_k_qubit_unitaries(cirq.Circuit(ops),k=1,rewriter=rewrite).all_operations())


def main():
    accepted=json.loads((h.ROOT/'precision_results.json').read_text())
    assert accepted['integration_eligible'] and accepted['faithful_native']['depth']<=65
    start=time.monotonic();deadline=start+90
    circuits=cirq.read_json(h.ROOT/'baseline_circuits.json');original={key:len(c) for key,c in circuits.items()}
    attempts=[];gains=[];coverage=[]
    def consider(n,k,label,c,strict):
        key=f'{n},{k}';cirq_google.Willow105.validate_circuit(c)
        assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
        row=dict(N=n,k=k,source=label,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),before=len(circuits[key]),accepted=False)
        attempts.append(row)
        if len(c)>=len(circuits[key]) and strict:return
        err=h.verify(c,n,k);row['state_l2_error']=err
        if len(c)<len(circuits[key]) and (not strict or err<1e-10):
            row['accepted']=True;circuits[key]=c;gains.append(row.copy())
            cirq.to_json(circuits,h.ROOT/'harvest_circuits.json');print('ACCEPT',row,flush=True)
    # Frozen peer whole-state screen is independent of terminal certification.
    fresh=json.loads((h.ROOT/'fresh_line_10_5.json').read_text())
    qs=[cirq.GridQubit(i,7) for i in range(10)];ops=h.operations(qs,fresh)
    default=h.schedule(h.optimize(h.compile_ops(ops)),restarts=3)
    consider(10,5,'fresh-line-484dc11-default',default,False)
    consider(10,5,'fresh-line-484dc11-faithful',faithful(ops),False)
    h.compile_ops=merge;h.optimize=lambda c:c
    h.b.halves={key:value for key,value in h.b.halves.items() if key[0]<=4}
    library=h.load_decoders()
    for name in ('polished_6_3','polished_7_3','polished_8_3'):
        row=json.loads((h.ROOT/f'{name}.json').read_text())
        library.append((name,row));h.b.halves[row['n'],row['k'],0]=(row['edges'],row['angles'],row.get('zset',[]))
    new=json.loads((h.ROOT/'polished_8_3.json').read_text())
    dev=cirq_google.Willow105.metadata;qr={q:(1e-3,0.) for q in dev.qubit_set};pr={tuple(e):(1e-3,0.) for e in dev.qubit_pairs}
    adj,node=h.b.make_chip(pr,qr,qr,qr,15,4)
    def options(qs,k,blocks):
        opts=h.half_options(qs,k,blocks,library)
        if len(qs)>=8:
            prefix,_=h.b.line_plan(len(qs),k,blocks,0)
            ops=h.b.line_ops(qs,k,[s for s in prefix if s[1]>8],False)+h.operations(qs[:8],new)
            opts=[(name,ops0) for name,ops0 in opts if name!='polished_8_3']+ [('polished_8_3',ops)]
        return opts
    groups=[]
    for n in (15,14,13,12,11,10):
        for k in (3,2):
            order=list(dict.fromkeys([(n+1)//2-1,(n+1)//2,(n+1)//2+1]+list(range(k,n-k+1))))
            groups += [(n,k,a) for a in order if k<=a<=n-k and max(a,n-a)>=8]
    for n,k,a in groups:
        item=dict(N=n,k=k,left_size=a,status='not-started',blocks=[]);coverage.append(item)
        if time.monotonic()>=deadline:continue
        item['status']='partial'
        for blocks in (True,False):
            if time.monotonic()>=deadline:break
            group=dict(blocks=blocks,status='partial',attempted=0);item['blocks'].append(group)
            ladder=h.b.best_ladder(adj,node,n,k,blocks,lambda qs:0.,float('-inf'),a)
            if ladder is None:group['status']='no-placement';continue
            left,right,_,_=ladder;root=h.b.split_ops(left,right,k)
            choices=[x for x in itertools.product(options(left,k,blocks),options(right,k,blocks)) if any(v[0]=='polished_8_3' for v in x)]
            group['planned']=len(choices)
            for (ln,lo),(rn,ro) in choices:
                if time.monotonic()>=deadline:break
                consider(n,k,f'new8-split-{a}-{blocks}-{ln}-{rn}',faithful(root+lo+ro),True);group['attempted']+=1
            if group['attempted']==group['planned']:group['status']='complete'
        if len(item['blocks'])==2 and all(g['status'] in ('complete','no-placement') for g in item['blocks']):item['status']='complete'
    search_seconds=time.monotonic()-start
    rows=[]
    for key,c in circuits.items():
        n,k=map(int,key.split(','));assert len(c)<=original[key]
        rows.append(dict(N=n,k=k,before=original[key],depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),state_l2_error=h.verify(c,n,k)))
    assert len(rows)==56
    cirq.to_json(circuits,h.ROOT/'harvest_circuits.json')
    result=dict(status='All56 retained native/device/state checks passed',cases=len(rows),search_budget_seconds=90,search_seconds=search_seconds,total_seconds=time.monotonic()-start,baseline_score=sum(int(key.split(',')[0])*int(key.split(',')[1])/d for key,d in original.items()),score=sum(r['N']*r['k']/r['depth'] for r in rows),improvements=gains,attempts=attempts,coverage=coverage,rows=rows,scope='Only combinations explicitly containing newly certified eight-site terminal; frozen whole-state10,5 screened separately. No topology search.',new_terminal_tolerance=1e-10,whole_state_tolerance=1e-5)
    (h.ROOT/'harvest_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMPLETE',result['score'],result['total_seconds'],flush=True)


if __name__=='__main__':main()
