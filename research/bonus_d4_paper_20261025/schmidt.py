"""Replace the paper's two-CNOT initial pair by exact one-CNOT Schmidt prep."""
import json
import math
import time

import cirq
import cirq_google
import numpy as np
from .search import ROOT, native


def main():
    report = json.loads((ROOT/'search_results.json').read_text())
    old = cirq.read_json(ROOT/'best_native.json')
    a = min(old.all_qubits())
    qs = [a,a+(0,1),a+(1,1),a+(1,0)]
    pair = np.array([[1.,1.],[1.,0.]])/math.sqrt(3)
    u,s,vh = np.linalg.svd(pair)
    assert np.max(abs(u@np.diag(s)@vh-pair))<1e-14
    target = np.array([int(x.bit_count()==2) for x in range(16)])/math.sqrt(6)
    simulator=cirq.Simulator(dtype=np.complex128)
    rows=[];best=None;tick=time.monotonic()
    for source in report['rows']:
        plus=source['plus'];sequence=source['sequence'];flip=source['final_flip']
        ops=[cirq.ry(2*math.atan2(s[1],s[0]))(qs[0]),cirq.ry(math.pi/2)(qs[plus]),
             cirq.CNOT(qs[0],qs[1]),cirq.MatrixGate(u)(qs[0]),cirq.MatrixGate(vh.T)(qs[1])]
        ops += [cirq.CNOT(qs[c],qs[t]) for c,t in sequence]
        ops += [cirq.X(qs[j]) for j in range(4) if flip & (1<<(3-j))]
        circuit=native(ops)
        cirq_google.Willow105.validate_circuit(circuit)
        state=simulator.simulate(circuit,qubit_order=qs).final_state_vector
        overlap=np.vdot(target,state)
        error=float(np.linalg.norm(state-target*overlap/abs(overlap)))
        assert error<1e-10
        row=dict(plus=plus,sequence=sequence,flip=flip,moments=len(circuit),
                 CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),state_error=error)
        rows.append(row)
        if best is None or (row['moments'],row['CZ'])<(best['moments'],best['CZ']):
            best=row
            cirq.to_json(circuit,ROOT/'schmidt_best_native.json')
            print('BEST',row,flush=True)
    result=dict(status='Exact one-entangler prefix and native square suffix validated',best=best,
                rows=rows,seconds=time.monotonic()-tick,baseline_moments=9,baseline_CZ=7,
                logical_pair_state=pair.tolist(),singular_values=s.tolist(),
                derivation='The six equal amplitudes factor into |+> on one qubit and (|00>+|01>+|10>)/sqrt3 on an adjacent pair, with a fourth qubit zero. Real SVD prepares the pair with one CNOT, then the exact affine suffix maps the support to all weight-two strings.',
                scope='All40 previously found shortest square mappings and final flips; no numerical fit or maintained-source change.')
    (ROOT/'schmidt_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('COMPLETE',len(rows),result['seconds'],flush=True)


if __name__=='__main__':
    main()
