"""Bounded integration of the certified fixed-topology five-site decoder."""
import argparse
import itertools
import json
import time

import cirq
import cirq_google

from . import helpers as h

ROOT = h.ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=120)
    args = parser.parse_args()
    precision = json.loads((ROOT / 'precision_results.json').read_text())
    assert precision['status'] == 'certified'
    assert precision['polished_native']['max_column_error'] < 1e-10
    polished = json.loads((ROOT / 'polished_five_four.json').read_text())
    (ROOT / 'five_four.json').write_text(json.dumps(polished, indent=2) + '\n')
    start = time.monotonic()
    library = h.load_decoders()
    h.b.halves[5,4,0] = (polished['edges'],polished['angles'],polished.get('zset',[]))
    previous = json.loads((ROOT/'previous_coverage.json').read_text())
    pending_ladders={(x['N'],x['k'],x['offset']) for x in previous['groups'] if x.get('kind')!='line-tail' and x['status'] in ('partial','not-started')}
    pending_lines={(x['N'],x['k']) for x in previous['groups'] if x.get('kind')=='line-tail' and x['status'] in ('partial','not-started')}
    old_attempts={(x['N'],x['k'],x['source']) for x in previous['attempts']}
    circuits = cirq.read_json(ROOT / 'baseline_circuits.json')
    original = {key: len(c) for key, c in circuits.items()}
    attempts, coverage, gains = [], [], []
    dev = cirq_google.Willow105.metadata
    qr = {q: (1e-3, 0.) for q in dev.qubit_set}
    pr = {tuple(e): (1e-3, 0.) for e in dev.qubit_pairs}
    adj, node = h.b.make_chip(pr, qr, qr, qr, 15, 4)

    def consider(n, k, label, ops):
        key = f'{n},{k}'
        circuit = h.compile_ops(ops)
        item = dict(N=n, k=k, source=label, compiled_depth=len(circuit), status='compile-screen')
        attempts.append(item)
        if len(circuit) > len(circuits[key]) + 12:
            return
        circuit = h.optimize(circuit)
        item.update(optimized_depth=len(circuit), status='optimize-screen')
        if len(circuit) >= len(circuits[key]) + 2:
            return
        circuit = h.schedule(circuit, restarts=3)
        item.update(scheduled_depth=len(circuit), status='no-depth-gain')
        if len(circuit) >= len(circuits[key]):
            return
        error = h.verify(circuit, n, k)
        gain = dict(N=n, k=k, before=len(circuits[key]), depth=len(circuit),
                    CZ=sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                    state_l2_error=error, source=label, seconds=time.monotonic()-start)
        item['status'] = 'accepted'
        circuits[key] = circuit
        gains.append(gain)
        cirq.to_json(circuits, ROOT / 'comparison_circuits.json')
        print('ACCEPT', gain, flush=True)

    preferred = [(12, 4, 0), (11, 4, -1), (13, 4, -1), (14, 4, 0), (15, 4, -1), (10, 4, 0)]
    remaining = [(n, k, offset) for k in (4, 3, 2, 1) for offset in (0, -1, 1)
                 for n in range(max(6, 2*k), 16) if (n, k, offset) not in preferred]
    pending=[x for x in preferred+remaining if x in pending_ladders]
    pending.sort(key=lambda x:0 if x==(13,4,0) else 1)
    for n, k, offset in pending:
        a = (n + 1)//2 + offset
        group = dict(N=n, k=k, offset=offset, left_size=a, status='not-started', blocks=[])
        coverage.append(group)
        if not k <= a <= n-k or max(a, n-a) < 5:
            group['status'] = 'infeasible-or-no-five-site-tail'
            continue
        if time.monotonic()-start >= args.seconds:
            continue
        group['status'] = 'partial'
        for blocks in (True, False):
            if time.monotonic()-start >= args.seconds:
                break
            entry = dict(blocks=blocks, status='partial', attempted=0, previous_identical=0)
            group['blocks'].append(entry)
            ladder = h.b.best_ladder(adj, node, n, k, blocks, lambda qs: 0., float('-inf'), a)
            if ladder is None:
                entry['status'] = 'no-placement'
                continue
            left, right, _, _ = ladder
            root = h.b.split_ops(left, right, k)
            choices = list(itertools.product(h.half_options(left, k, blocks, library),
                                            h.half_options(right, k, blocks, library)))
            # The standard lookup is now certified too; its alternatives are new evidence.
            entry['planned'] = len(choices)
            for (ln, lo), (rn, ro) in choices:
                if time.monotonic()-start >= args.seconds:
                    break
                old_label=f'ladder-{a}-{blocks}-{ln}-{rn}'
                if 'standard' not in (ln,rn) and (n,k,old_label) in old_attempts:
                    entry['previous_identical']+=1;continue
                label=old_label.replace('standard','standard-certified')
                consider(n,k,label,root+lo+ro)
                entry['attempted'] += 1
            if entry['attempted']+entry['previous_identical'] == len(choices):
                entry['status'] = 'complete'
        if len(group['blocks']) == 2 and all(x['status'] in ('complete', 'no-placement') for x in group['blocks']):
            group['status'] = 'complete'
        print('COVERAGE', group, flush=True)

    # Line tails are explicitly tracked even if the preferred ladder work consumes the budget.
    for k in (4, 3, 2, 1):
        for n in range(max(5, 2*k), 16):
            if (n,k) not in pending_lines:continue
            group = dict(N=n, k=k, kind='line-tail', status='not-started')
            coverage.append(group)
            if time.monotonic()-start >= args.seconds:
                continue
            steps, weights = h.b.line_plan(n, k, True, 0)
            qubits = h.b.best_path(adj, node, weights, float('-inf'))
            ops = h.b.line_ops(qubits, k, [s for s in steps if s[1] > 5], False)
            consider(n, k, 'line-five_four', ops+h.operations(qubits[:5], polished))
            group['status'] = 'complete'

    search_seconds = time.monotonic()-start
    (ROOT / 'comparison_coverage.json').write_text(json.dumps(dict(groups=coverage, attempts=attempts), indent=2)+'\n')
    rows = []
    for key, circuit in circuits.items():
        n, k = map(int, key.split(','))
        assert len(circuit) <= original[key]
        rows.append(dict(N=n, k=k, before=original[key], depth=len(circuit),
                         CZ=sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                         state_l2_error=h.verify(circuit, n, k)))
    cirq.to_json(circuits, ROOT / 'comparison_circuits.json')
    report = dict(status='All 56 retained native states/device circuits verified', cases=len(rows),
                  numerical_polish_seconds=precision['numerical_seconds'],
                  search_budget_seconds=args.seconds, search_seconds=search_seconds,
                  total_comparison_seconds=time.monotonic()-start, trials=len(attempts),
                  baseline_score=sum(int(key.split(',')[0])*int(key.split(',')[1])/d for key,d in original.items()),
                  score=sum(row['N']*row['k']/row['depth'] for row in rows),
                  improvements=gains, rows=rows)
    (ROOT / 'comparison_results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('COMPLETE', report['score'], report['trials'], report['total_comparison_seconds'], flush=True)


if __name__ == '__main__':
    main()
