"""Independent14-qubit native state/device verification of the folded root."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import time

import cirq
import cirq_google
import numpy as np

ROOT=Path(__file__).parent

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--candidate',required=True);args=parser.parse_args()
    prefix=args.candidate
    plan_path=ROOT/f'{prefix}_plan.json'
    start=time.monotonic();plan=json.loads(plan_path.read_text())
    qs=[cirq.GridQubit(*q) for q in plan['physical_qubit_order']]
    expected=np.zeros(1<<14,dtype=np.complex128)
    for row in plan['target_rows']:expected[row['basis']]=row['amplitude_numerator']/math.sqrt(row['amplitude_denominator_sqrt'])
    # Reconstruct target independently from logical s/branch bits and physical
    # orders, rather than trusting the serialized integer basis labels alone.
    other=np.zeros_like(expected)
    left=[tuple(q) for q in plan['left_logical_order']];right=[tuple(q) for q in plan['right_logical_order']]
    for s in range(4):
        low=[0]*(7-s)+[1]*s
        for branch in (0,1):
            lv=[b^branch for b in low];rv=[b^1 for b in lv]
            bits=dict(zip(left,lv));bits.update(zip(right,rv))
            index=sum(bits[(q.row,q.col)]<<(13-i) for i,q in enumerate(qs))
            other[index]=math.comb(7,s)/math.sqrt(math.comb(14,7))
    assert np.array_equal(expected,other)
    assert abs(np.linalg.norm(expected)-1)<1e-14
    assert all(i.bit_count()==7 for i in np.flatnonzero(expected))
    raw=[];native=[]
    def one(g,q):return cirq.PhasedXZGate.from_matrix(cirq.unitary(g)).on(q)
    for gate in plan['operations']:
        name=gate[0];a=cirq.GridQubit(*gate[1])
        if name in ('CX','CZ'):
            b=cirq.GridQubit(*gate[2])
            raw.append(cirq.CNOT(a,b) if name=='CX' else cirq.CZ(a,b))
            native.extend([one(cirq.H,b),cirq.CZ(a,b),one(cirq.H,b)] if name=='CX' else [cirq.CZ(a,b)])
        else:
            g=cirq.ry(gate[2]) if name=='RY' else cirq.H if name=='H' else cirq.X
            raw.append(g.on(a))
            # Preserve Ry angles directly; no tolerance-based canonicalization.
            native.append(cirq.PhasedXZGate(axis_phase_exponent=.5,x_exponent=gate[2]/np.pi,z_exponent=0).on(a) if name=='RY' else one(g,a))
    checks=[];matrix_errors=[]
    def check(name,circuit,is_native):
        assert circuit.all_qubits()==set(qs)
        if is_native:
            assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in circuit.all_operations())
            cirq_google.Willow105.validate_circuit(circuit)
        t=time.monotonic();state=cirq.Simulator(dtype=np.complex128).simulate(circuit,qubit_order=qs).final_state_vector
        overlap=np.vdot(expected,state);phase=overlap/abs(overlap)
        err=float(np.linalg.norm(state-phase*expected));assert err<1e-10,(name,err)
        support=np.flatnonzero(expected)
        outside=float(np.sum(abs(state[expected==0])**2))
        result=dict(stage=name,moments=len(circuit),CZ=sum(op.gate==cirq.CZ for op in circuit.all_operations()),
            max_common_phase_l2_error=err,common_phase=[float(phase.real),float(phase.imag)],
            off_target_support_probability=outside,seconds=time.monotonic()-t,native_device_check=is_native,
            branch_amplitude_errors=[dict(basis=int(i),error=float(abs(state[i]-phase*expected[i]))) for i in support])
        checks.append(result);print(result,flush=True)
        return result
    check('logical-CNOT-reference',cirq.Circuit(raw),False)
    c=cirq.Circuit(native);check('unfused-native',c,True)
    def rewrite(op):
        matrix=cirq.unitary(op);q=next(iter(op.qubits));gate=cirq.PhasedXZGate.from_matrix(matrix)
        actual=cirq.unitary(gate);phase=np.vdot(matrix,actual);phase/=abs(phase)
        matrix_errors.append(float(np.linalg.norm(actual-phase*matrix)))
        return gate.on(q)
    merged=cirq.Circuit(cirq.merge_k_qubit_unitaries(c,k=1,rewriter=rewrite).all_operations())
    check('faithful-local-merge',merged,True);assert max(matrix_errors)<1e-12
    cirq.to_json(merged,ROOT/f'{prefix}_native.json')
    report=dict(status='Verified native folded-root state, NOT a Dicke state/full decoder',cirq=cirq.__version__,
        source_sha256=hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        native_sha256=hashlib.sha256((ROOT/f'{prefix}_native.json').read_bytes()).hexdigest(),
        physical_qubit_order=plan['physical_qubit_order'],left_logical_order=plan['left_logical_order'],right_logical_order=plan['right_logical_order'],
        target='sum_s C(7,s)/sqrt3432 * (|u_s>_L|X u_s>_R + |X u_s>_L|u_s>_R), s=0..3 in the recorded three-arm orders',
        independent_target_indexing_check=True,physical_qubits=14,extra_qubits=0,measurements=0,checks=checks,
        maximum_local_matrix_error=max(matrix_errors),total_seconds=time.monotonic()-start,
        optimization='Only faithful local matrix fusion; no eject/drop-negligible/target-gateset passes.',
        limitations=['Selected affine folded root only. Both finite-cost symmetric cores and final Dicke-state verification remain absent.','No portfolio integration, score improvement, hardware experiment, or maintained-source change claimed.'])
    (ROOT/f'{prefix}_verified.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
