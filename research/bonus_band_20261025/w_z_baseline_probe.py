"""Confirmatory original-seed pilot; selector unchanged from fresh-seed study."""
import hashlib
import json
import math
from pathlib import Path

import cirq
import numpy as np

from .w_hardware_probe import fast_eval, judge, score_samples
from .w_z_selection import select, baseline

ROOT = Path(__file__).parent


def main():
    rows, pairs, pools = [], [], []
    for n in (8, 10):
        for seed in range(6):
            cal = judge.fake_calibration(seed)
            ref, ref_qs, candidate, qs, pool = select(n, cal)
            assert pool['seconds'] < 60
            pools.append(dict(N=n, seed=seed, **pool))
            cache, samples = {}, {}
            for name, circuit, qubits in [('baseline', ref, ref_qs), ('tree', candidate, qs)]:
                baseline.check_circuit(circuit, cal[0], cal[1])
                judge.get_device().validate_circuit(circuit)
                psi = cirq.Simulator(dtype=np.complex128).simulate(circuit, qubit_order=sorted(qubits)).final_state_vector
                target = np.array([int(i.bit_count()==1) for i in range(2**n)])/math.sqrt(n)
                overlap = np.vdot(target, psi)
                error = float(np.linalg.norm(psi-target*overlap/abs(overlap)))
                assert error < 1e-10
                key = circuit.freeze()
                if key not in cache:
                    # Matching streams couple sorted qubit positions across differing layouts.
                    # This preserves each marginal; it is not a shared physical-chip detuning draw.
                    pz, px = fast_eval.noisy_probs(circuit, qubits, cal, np.random.default_rng([seed,n,1]), realisations=4)
                    sample = score_samples(pz, px, n, seed=200000+n*10+seed)
                    cache[key] = pz, px, sample
                pz, px, sample = cache[key]; samples[name] = sample
                scores = {}
                for cutoff, values in sample.items():
                    f, zf, zb, x, proxy = fast_eval.expected_score(pz, px, n, 1, cutoff, 10000)
                    scores[str(cutoff)] = dict(E_score=float(values.mean()), MC_standard_error=float(values.std(ddof=1)/math.sqrt(len(values))),
                                              valid_fraction=float(f), Z_floor=float(zf), Z_bias=float(zb), X_penalty=float(x), penalty_inverse_proxy=float(proxy))
                rows.append(dict(N=n, seed=seed, held_out=False, variant=name, moments=len(circuit),
                                 CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()), state_l2_error=error,
                                 qubits=[str(q) for q in sorted(qubits)], scores=scores))
            for cutoff in (4,n):
                delta = samples['tree'][cutoff]-samples['baseline'][cutoff]
                pairs.append(dict(N=n, seed=seed, held_out=False, cutoff=cutoff,
                                  mean_delta=float(delta.mean()), paired_MC_standard_error=float(delta.std(ddof=1)/math.sqrt(len(delta)))))
            report = dict(status='confirmatory original seeds0..5; no maintained constructor changes',
                          baseline_sha256=hashlib.sha256((ROOT/'w_cost_snapshot.py').read_bytes()).hexdigest(),
                          model='Four detuning realizations, 10000 shots per basis, 32768 score repetitions; paired MC uncertainty excludes calibration and detuning uncertainty.',
                          rows=rows, paired_differences=pairs)
            (ROOT/'w_z_baseline_results.json').write_text(json.dumps(report, indent=2)+'\n')
            (ROOT/'w_z_baseline_pools.json').write_text(json.dumps(pools, indent=2)+'\n')
            print(n, seed, pool['selected']['name'], len(ref), len(candidate), 'delta', pairs[-1]['mean_delta'], 'build', pool['seconds'], flush=True)


if __name__ == '__main__':
    main()
