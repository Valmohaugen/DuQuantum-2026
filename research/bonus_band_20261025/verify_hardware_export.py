"""Validate the standalone guarded W export against its evaluated implementation."""
import ast
import hashlib
import importlib.util
import json
import math
import time
from pathlib import Path

import cirq
import numpy as np

from . import native_submission as preserved
from . import hardware_primary_snapshot as current_main
from .w_hardware_probe import judge
from .w_zz_selection import select

ROOT = Path(__file__).parent


def main():
    path = ROOT / 'hardware_submission.py'
    source = path.read_text()
    assert source.startswith((ROOT / 'hardware_primary_snapshot.py').read_text())
    assert not any(isinstance(node, ast.ImportFrom) and node.level
                   for node in ast.walk(ast.parse(source)))
    spec = importlib.util.spec_from_file_location('standalone_hardware_candidate', path)
    solver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(solver)
    rows = []
    for n in (8, 10):
        for seed in (0, 1, 2, 6, 7, 8, 12, 13, 14):
            cal = judge.fake_calibration(seed)
            _, _, reference, rqs, selection = select(n, cal)
            tick = time.monotonic()
            circuit, qs = solver.create_dicke_state(n, 1, *cal)
            elapsed = time.monotonic() - tick
            assert elapsed < 60
            assert circuit == reference and qs == set(rqs), (n, seed)
            solver.check_circuit(circuit, *cal[:2])
            judge.get_device().validate_circuit(circuit)
            assert all(isinstance(op.gate, cirq.PhasedXZGate) or op.gate == cirq.CZ
                       for op in circuit.all_operations())
            state = cirq.Simulator(dtype=np.complex128).simulate(
                circuit, qubit_order=sorted(qs)).final_state_vector
            target = np.array([int(i.bit_count() == 1) for i in range(2**n)]) / math.sqrt(n)
            overlap = np.vdot(target, state)
            error = float(np.linalg.norm(state - target * overlap / abs(overlap)))
            assert error < 1e-10
            rows.append(dict(N=n, seed=seed, moments=len(circuit),
                             CZ=sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                             seconds=elapsed, state_l2_error=error,
                             selected=selection['selected']['name']))
            print(n, seed, round(elapsed, 3), len(circuit), flush=True)
    fallback = []
    cal = judge.fake_calibration(0)
    cases = [(6, 1, {}), (8, 7, {}), (4, 2, {}), (8, 0, {}),
             (8, 1, {'dynamical_decoupling': False}), (8, 1, {'pack': True})]
    for n, k, options in cases:
        result = solver.create_dicke_state(n, k, *cal, **options)
        reference = current_main.create_dicke_state(n, k, *cal, **options)
        assert result == reference, (n, k, options)
        fallback.append(dict(N=n, k=k, options=options))
    # use_blocks has no effect on W construction in the preserved API.
    a = solver.create_dicke_state(8, 1, *cal, use_blocks=False)
    b = solver.create_dicke_state(8, 1, *cal)
    assert a == b
    bonus = []
    for n in range(2, 16):
        for k in range(1, n // 2 + 1):
            c, qs = solver.create_dicke_state_adaptive(n, k)
            assert (c, qs) == preserved.create_dicke_state_adaptive(n, k)
            bonus.append(dict(N=n, k=k, moments=len(c)))
    report = dict(status='passed; separate standalone candidate',
                  candidate_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  preserved_sha256=hashlib.sha256((ROOT/'native_submission.py').read_bytes()).hexdigest(),
                  current_main_sha256=hashlib.sha256((ROOT/'hardware_primary_snapshot.py').read_bytes()).hexdigest(),
                  exact_reference_matches=len(rows), rows=rows, fallback_checks=fallback,
                  bonus_exact_matches=len(bonus), bonus_score=sum(r['N']*r['k']/r['moments'] for r in bonus),
                  max_build_seconds=max(r['seconds'] for r in rows),
                  max_state_l2_error=max(r['state_l2_error'] for r in rows),
                  scope='N8/N10 k1 default-DD unpacked calls use evaluated robust selector; other main paths preserve the current maintained-solver snapshot. Noise-model gains are not hardware guarantees.')
    (ROOT/'hardware_submission_verified.json').write_text(json.dumps(report, indent=2)+'\n')
    print('COMPLETE', report['candidate_sha256'], report['max_build_seconds'], flush=True)


if __name__ == '__main__':
    main()
