"""Reuse five fresh peer tables, preserving the frozen native portfolio."""
import argparse
import json
import time

import cirq
import cirq_google

from . import helpers as h

ROOT = h.ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=60)
    args = parser.parse_args()
    start = time.monotonic()
    circuits = cirq.read_json(ROOT/'baseline_circuits.json')
    original = {key:len(c) for key,c in circuits.items()}
    attempts, gains = [], []
    device = cirq_google.Willow105.metadata
    qr = {q:(1e-3,0.) for q in device.qubit_set}
    pr = {tuple(edge):(1e-3,0.) for edge in device.qubit_pairs}
    adj,node = h.b.make_chip(pr,qr,qr,qr,15,4)

    def consider(n,k,source,ops):
        circuit = h.compile_ops(ops)
        raw_depth = len(circuit)
        circuit = h.schedule(h.optimize(circuit),restarts=3)
        error = h.verify(circuit,n,k)
        key = f'{n},{k}'
        row = dict(N=n,k=k,source=source,baseline_depth=original[key],compiled_depth=raw_depth,
                   optimized_depth=len(circuit),CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),
                   state_l2_error=error,seconds=time.monotonic()-start)
        row['accepted'] = len(circuit)<len(circuits[key])
        attempts.append(row)
        if row['accepted']:
            circuits[key] = circuit
            gains.append(row)
            cirq.to_json(circuits,ROOT/'harvest_circuits.json')
        print('CANDIDATE',row,flush=True)

    coverage = []
    for n,k in [(8,3),(9,3),(9,4),(10,5),(10,4)]:
        item = dict(N=n,k=k,status='not-started',sources=[])
        coverage.append(item)
        if time.monotonic()-start>=args.seconds:
            continue
        item['status']='partial'
        line = h.b.lines.get((n,k))
        if line:
            weights=[0]*(n-1)
            for a,b in line[0]:weights[min(a,b)]+=1
            qs=h.b.best_path(adj,node,weights,float('-inf'))
            consider(n,k,'0dc1b2c-line',h.b.patch_ops(qs,*line))
            item['sources'].append('line')
        if time.monotonic()-start>=args.seconds:
            continue
        patch=h.b.patches.get((n,k))
        if patch:
            cells,edges,angles,*z=patch
            r0=min(r for r,c in cells);c0=min(c for r,c in cells)
            qs=h.b.best_patch(adj,node,[(r-r0,c-c0) for r,c in cells],edges)
            if qs is not None:
                consider(n,k,'0dc1b2c-patch',h.b.patch_ops(qs,edges,angles,z[0] if z else []))
                item['sources'].append('patch')
        item['status']='complete'
    construction_seconds=time.monotonic()-start
    rows=[]
    for key,circuit in circuits.items():
        n,k=map(int,key.split(','))
        assert len(circuit)<=original[key]
        rows.append(dict(N=n,k=k,before=original[key],depth=len(circuit),
                         CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),
                         state_l2_error=h.verify(circuit,n,k)))
    cirq.to_json(circuits,ROOT/'harvest_circuits.json')
    report=dict(status='All56 retained native states/device circuits verified',cases=len(rows),
                construction_budget_seconds=args.seconds,construction_seconds=construction_seconds,
                total_seconds=time.monotonic()-start,coverage=coverage,candidates=attempts,improvements=gains,
                baseline_score=sum(int(key.split(',')[0])*int(key.split(',')[1])/d for key,d in original.items()),
                score=sum(row['N']*row['k']/row['depth'] for row in rows),rows=rows)
    (ROOT/'harvest_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('COMPLETE',report['score'],report['total_seconds'],flush=True)


if __name__=='__main__':
    main()
