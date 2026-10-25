"""Isolated depth experiments; leaves maintained entry points untouched."""
import json
import time
from pathlib import Path

import cirq
import numpy as np

from research.bonus_terminal_integration_20261025 import snapshot as b


def compact(c):
    c = cirq.merge_single_qubit_gates_to_phxz(c)
    return cirq.Circuit(cirq.drop_negligible_operations(c).all_operations())


def optimize(c):
    candidates = [c]
    for _ in range(3):
        c = cirq.eject_z(c)
        c = cirq.eject_phased_paulis(c)
        c = compact(c)
        candidates.append(c)
    c = cirq.optimize_for_target_gateset(c, gateset=cirq.CZTargetGateset(allow_partial_czs=False), max_num_passes=3)
    candidates.append(compact(c))
    return min(candidates, key=len)


def main():
    out = Path('research/bonus_band_20261025/probe_results.json')
    rows = []
    for n, k in [(6, 3), (8, 4), (10, 5), (12, 6), (15, 7)]:
        start = time.monotonic()
        c, qs = b.create_dicke_state_adaptive(n, k)
        built = time.monotonic() - start
        d = optimize(c)
        state = cirq.Simulator(dtype=np.complex128).simulate(d, qubit_order=sorted(qs)).final_state_vector
        target = np.array([int(i.bit_count() == k) for i in range(2**n)], dtype=float)
        target /= np.linalg.norm(target)
        row = dict(N=n, k=k, before=len(c), after=len(d), fidelity=float(abs(np.vdot(target,state))**2), build=built, seconds=time.monotonic()-start)
        rows.append(row)
        print(row, flush=True)
        out.write_text(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
