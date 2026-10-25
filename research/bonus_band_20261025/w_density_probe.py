"""Frozen PORT023 study: compare baseline, PORT016, and density ranking."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import cirq
import numpy as np

ROOT = Path(__file__).parent
for name in ('judge', 'test_dicke', 'fast_eval'):
    spec = importlib.util.spec_from_file_location(name, ROOT/'w_edge_eval_snapshot'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

from .w_density_selection import select, baseline
from .w_edge_selection import select as edge_select
from .w_edge_probe import probabilities, MODELS
from .w_hardware_probe import score_samples, judge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seeds', nargs='+', type=int, default=[33, 34, 35, 36])
    parser.add_argument('--sizes', nargs='+', type=int, default=[8, 10])
    parser.add_argument('--timing-only', action='store_true')
    parser.add_argument('--output', default='w_density_results.json')
    args = parser.parse_args()
    report = dict(status='running', seeds=args.seeds, sizes=args.sizes, cases=[], rows=[], pairs=[],
                  source_sha256=hashlib.sha256((ROOT/'w_density_selection.py').read_bytes()).hexdigest())
    output = ROOT/args.output
    for n in args.sizes:
        for seed in args.seeds:
            tick = time.monotonic()
            cal = judge.fake_calibration(seed)
            reference, rqs, candidate, cqs, info = select(n, cal)
            _, _, analytic, aqs, old_info = edge_select(n, cal)
            variants = [('baseline', reference, rqs), ('edge', analytic, aqs), ('density', candidate, cqs)]
            checks = []
            for name, circuit, qs in variants:
                baseline.check_circuit(circuit, *cal[:2])
                judge.get_device().validate_circuit(circuit)
                state = cirq.Simulator(dtype=np.complex128).simulate(circuit, qubit_order=sorted(qs)).final_state_vector
                target = np.array([int(x.bit_count() == 1) for x in range(2**n)])/math.sqrt(n)
                overlap = np.vdot(target, state)
                error = float(np.linalg.norm(state-target*overlap/abs(overlap)))
                assert error < 1e-10
                checks.append(dict(variant=name, state_l2_error=error, moments=len(circuit)))
            assert info['seconds'] < 60, info['seconds']
            report['cases'].append(dict(N=n, seed=seed, selection=info, checks=checks,
                                        density_equals_baseline=candidate == reference,
                                        density_equals_edge=candidate == analytic,
                                        edge_build_seconds=old_info['seconds']))
            output.write_text(json.dumps(report, indent=2)+'\n')
            print('constructed', n, seed, round(info['seconds'], 3), 'selected', info.get('selected_index'), 'timeout', info.get('timed_out'), flush=True)
            if args.timing_only:
                continue
            for model in MODELS:
                cache, samples = {}, {}
                for name, circuit, qs in variants:
                    key = circuit.freeze()
                    if key not in cache:
                        pz, px = probabilities(circuit, qs, cal, seed, model)
                        cache[key] = score_samples(pz, px, n, 410000+seed*10+n)
                    samples[name] = cache[key]
                    report['rows'].append(dict(N=n, seed=seed, model=model, variant=name,
                        scores={str(k): dict(mean=float(v.mean()), mc_se=float(v.std(ddof=1)/math.sqrt(len(v)))) for k, v in samples[name].items()}))
                for comparator in ('baseline', 'edge'):
                    for cutoff in (4, n):
                        delta = samples['density'][cutoff]-samples[comparator][cutoff]
                        report['pairs'].append(dict(N=n, seed=seed, model=model, comparator=comparator,
                            cutoff=cutoff, mean_delta=float(delta.mean()), paired_mc_se=float(delta.std(ddof=1)/math.sqrt(len(delta)))))
                output.write_text(json.dumps(report, indent=2)+'\n')
                print('evaluated', n, seed, model, round(time.monotonic()-tick, 2), flush=True)
    report['status'] = 'complete'
    output.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
