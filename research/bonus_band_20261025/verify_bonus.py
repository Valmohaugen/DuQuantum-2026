"""Exhaustive corrected bonus score and independent exact-state/native checks."""
import hashlib
import importlib
import json
import math
import sys
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np


def main():
    module = sys.argv[1] if len(sys.argv)>1 else 'research.bonus_band_20261025.baseline'
    solver = importlib.import_module(module)
    source = Path(solver.__file__)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    output = Path('research/bonus_band_20261025') / (source.stem + '_verified.json')
    device = cirq_google.Willow105
    edges = {frozenset(p) for p in device.metadata.qubit_pairs}
    vertices = set(device.metadata.qubit_set)
    rows = []
    start = time.monotonic()
    score = 0
    for n in range(2,16):
        for k in range(1,n//2+1):
            tick = time.monotonic()
            c, qs = solver.create_dicke_state_adaptive(n,k)
            seconds = time.monotonic()-tick
            assert seconds < 60, (n,k,seconds)
            assert len(qs)==n and qs<=vertices and c.all_qubits()==qs
            assert 0 < len(c) <= 1750
            for op in c.all_operations():
                assert isinstance(op.gate,cirq.PhasedXZGate) or (op.gate==cirq.CZ and frozenset(op.qubits) in edges),op
            device.validate_circuit(c)
            state = cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=sorted(qs)).final_state_vector
            target = np.array([int(i.bit_count()==k) for i in range(2**n)],dtype=float)/math.sqrt(math.comb(n,k))
            overlap = np.vdot(target,state)
            fid = float(abs(overlap)**2)
            error = float(np.linalg.norm(state-target*overlap/abs(overlap)))
            assert error < 1e-5,(n,k,error)
            contribution=n*k/len(c)
            score += contribution
            row=dict(N=n,k=k,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),fidelity=fid,state_l2_error=error,build_seconds=seconds,score=contribution)
            rows.append(row)
            report=dict(module=module,source_sha256=source_hash,cirq=cirq.__version__,range='N=2..15, k=1..floor(N/2)',cases=len(rows),score=score,elapsed_seconds=time.monotonic()-start,rows=rows)
            output.write_text(json.dumps(report,indent=2))
            print(n,k,len(c),round(seconds,3),f'{fid:.12f}',f'sum={score:.6f}',flush=True)
    print('COMPLETE',score,flush=True)


if __name__=='__main__':
    main()
