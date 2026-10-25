"""Integration of strictly certified fixed-topology refinements and certified comparators.

Prepared only. Run after explicit CPU release. Every new isometry must meet
the existing1e-10 common-phase requirement before it enters a candidate.
"""
import argparse
import itertools
import json
import time

import cirq
import cirq_google
import numpy as np

from . import helpers as h

ROOT = h.ROOT

def faithful_compile(ops):
    def rewrite(op):
        qs=tuple(op.qubits);assert len(qs)==1
        return cirq.PhasedXZGate.from_matrix(cirq.unitary(op)).on(qs[0])
    return cirq.Circuit(cirq.merge_k_qubit_unitaries(cirq.Circuit(ops),k=1,rewriter=rewrite).all_operations())

h.compile_ops=faithful_compile
h.optimize=lambda c:c



def certify(row, name, adj, node):
    n,k = row['n'],row['k']
    assert row.get('lmin',0)==0
    assert all(abs(a-b)==1 for a,b in row['edges'])
    qs = h.b.best_path(adj,node,[1]*(n-1),float('-inf'))
    circuit = h.schedule(h.optimize(h.compile_ops(h.operations(qs,row))),restarts=3)
    cirq_google.Willow105.validate_circuit(circuit)
    simulator = cirq.Simulator(dtype=np.complex128)
    states = np.array([simulator.simulate(circuit,initial_state=(1<<r)-1,qubit_order=qs).final_state_vector
                       for r in range(k+1)])
    goal = np.array([h.target(n,r) for r in range(k+1)])
    overlap = np.vdot(goal,states)
    phase = overlap/abs(overlap) if abs(overlap) else 1.
    errors = np.linalg.norm(states-phase*goal,axis=1)
    check = dict(name=name,n=n,k=k,depth=len(circuit),CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),
                 max_column_error=float(max(errors)),column_errors=errors.tolist(),
                 common_phase=[float(np.real(phase)),float(np.imag(phase))],accepted=bool(max(errors)<1e-10))
    print('COLUMN',check,flush=True)
    return check


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--seconds',type=float,default=90)
    args=parser.parse_args()
    start=time.monotonic()
    circuits=cirq.read_json(ROOT/'baseline_circuits.json')
    original={key:len(c) for key,c in circuits.items()}
    dev=cirq_google.Willow105.metadata
    qr={q:(1e-3,0.) for q in dev.qubit_set}
    pr={tuple(edge):(1e-3,0.) for edge in dev.qubit_pairs}
    adj,node=h.b.make_chip(pr,qr,qr,qr,15,4)
    # Previously frozen exact helpers remain the incumbent library.
    library=h.load_decoders()
    polished=json.loads((ROOT/'five_four.json').read_text())
    h.b.halves[5,4,0]=(polished['edges'],polished['angles'],polished.get('zset',[]))
    # Never implicitly consume an uncertified new peer table through 'standard'.
    for key in [(6,3,0),(7,3,0),(8,3,0)]:
        h.b.halves.pop(key,None)
    peers=json.loads((ROOT/'peer_inputs.json').read_text())
    peers.sort(key=lambda row:(0 if row['k']==5 else 1,row['n'],row['name']))
    checks=[];installed={};certified=[]
    for peer in peers:
        if time.monotonic()-start>=args.seconds:
            checks.append(dict(name=peer['name'],status='not-started; deadline'))
            continue
        row=json.loads((ROOT/peer['frozen']).read_text())
        check=certify(row,peer['name'],adj,node);checks.append(check)
        if not check['accepted']:
            continue
        library.append((peer['name'],row));certified.append(peer['name'])
        key=(row['n'],row['k'],0)
        if key not in installed or check['depth']<installed[key]['depth']:
            installed[key]=check
            h.b.halves[key]=(row['edges'],row['angles'],row.get('zset',[]))
    (ROOT/'peer_column_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
    attempts=[];gains=[];coverage=[]

    def consider(n,k,label,ops):
        key=f'{n},{k}';circuit=h.compile_ops(ops)
        attempt=dict(N=n,k=k,source=label,compiled_depth=len(circuit),status='compile-screen')
        attempts.append(attempt)
        if len(circuit)>len(circuits[key])+12:return
        circuit=h.optimize(circuit);attempt.update(optimized_depth=len(circuit),status='optimize-screen')
        if len(circuit)>=len(circuits[key])+2:return
        circuit=h.schedule(circuit,restarts=3);attempt.update(scheduled_depth=len(circuit),status='no-depth-gain')
        if len(circuit)>=len(circuits[key]):return
        error=h.verify(circuit,n,k)
        if error>=1e-10:
            attempt.update(status='strict-new-state-rejection',state_l2_error=error);return
        gain=dict(N=n,k=k,before=len(circuits[key]),depth=len(circuit),
                  CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),
                  state_l2_error=error,source=label)
        circuits[key]=circuit;gains.append(gain);attempt['status']='accepted'
        cirq.to_json(circuits,ROOT/'harvest_circuits.json')
        print('ACCEPT',gain,flush=True)

    cases=[(n,3) for n in (13,14,15,12,11,10,9,8)]
    cases += [(n,2) for n in (12,13,14,15,11,10,9,8)]
    for offset in (0,-1,1):
        for n,k in cases:
            a=(n+1)//2+offset
            entry=dict(N=n,k=k,offset=offset,left_size=a,status='not-started',blocks=[])
            coverage.append(entry)
            if not k<=a<=n-k:
                entry['status']='infeasible';continue
            eligible=any(row['accepted'] and row['k']>=min(k,row['n'])
                         for row in checks if 'accepted' in row)
            if not eligible:
                entry['status']='no-new-certified-table';continue
            if time.monotonic()-start>=args.seconds:continue
            entry['status']='partial'
            for blocks in (True,False):
                if time.monotonic()-start>=args.seconds:break
                group=dict(blocks=blocks,status='partial',attempted=0);entry['blocks'].append(group)
                ladder=h.b.best_ladder(adj,node,n,k,blocks,lambda qs:0.,float('-inf'),a)
                if ladder is None:group['status']='no-placement';continue
                left,right,_,_=ladder;root=h.b.split_ops(left,right,k)
                choices=list(itertools.product(h.half_options(left,k,blocks,library),h.half_options(right,k,blocks,library)))
                choices=[x for x in choices if any(v[0]=='peer_faithful7' or (v[0]=='standard' and size==7) for v,size in zip(x,(len(left),len(right))))]
                group['planned']=len(choices)
                for (ln,lo),(rn,ro) in choices:
                    if time.monotonic()-start>=args.seconds:break
                    consider(n,k,f'ladder-{a}-{blocks}-{ln}-{rn}',root+lo+ro);group['attempted']+=1
                if group['attempted']==len(choices):group['status']='complete'
            if len(entry['blocks'])==2 and all(x['status'] in ('complete','no-placement') for x in entry['blocks']):entry['status']='complete'
    search_seconds=time.monotonic()-start
    rows=[]
    for key,circuit in circuits.items():
        n,k=map(int,key.split(','));assert len(circuit)<=original[key]
        rows.append(dict(N=n,k=k,before=original[key],depth=len(circuit),
                         CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),
                         state_l2_error=h.verify(circuit,n,k)))
    cirq.to_json(circuits,ROOT/'harvest_circuits.json')
    report=dict(status='All56 retained native states/device circuits verified',cases=len(rows),
                search_budget_seconds=args.seconds,search_seconds=search_seconds,total_seconds=time.monotonic()-start,
                certified_peer_names=certified,column_checks=checks,coverage=coverage,attempts=attempts,improvements=gains,
                baseline_score=sum(int(key.split(',')[0])*int(key.split(',')[1])/d for key,d in original.items()),
                score=sum(row['N']*row['k']/row['depth'] for row in rows),rows=rows)
    (ROOT/'harvest_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',report['score'],'certified',certified,'seconds',report['total_seconds'],flush=True)


if __name__=='__main__':main()
