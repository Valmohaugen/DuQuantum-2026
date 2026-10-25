"""Prepared only: bypass near-half-turn snapping in PhasedXZ merge helper.

No coefficients change. Run only after explicit CPU release. Every stage is
checked on four coherent columns; shortest certified native stage is retained.
"""
import json
import time
import cirq
import cirq_google
import numpy as np
from . import helpers as h

def matrix_error(actual,expected):
    overlap=np.vdot(expected,actual)
    return float(np.linalg.norm(actual-expected*overlap/abs(overlap)))

def faithful_merge(c,matrix_errors):
    def rewrite(op):
        qs=tuple(op.qubits)
        assert len(qs)==1
        matrix=cirq.unitary(op)
        gate=cirq.PhasedXZGate.from_matrix(matrix)
        matrix_errors.append(matrix_error(cirq.unitary(gate),matrix))
        return gate.on(qs[0])
    return cirq.Circuit(cirq.merge_k_qubit_unitaries(c,k=1,rewriter=rewrite).all_operations())

def witnesses():
    """Public Cirq APIs only; no copied package implementation or package edits."""
    q=cirq.LineQubit(0);rows=[]
    matrices=[]
    for delta in (-1e-8,-1e-9,-5e-10,-1e-10,0.,1e-10,5e-10,1e-9,1e-8):
        matrix=cirq.unitary(cirq.rz(.37))@cirq.unitary(cirq.ry(np.pi*(1+delta)))@cirq.unitary(cirq.rz(-.29))
        matrices.append((f'near-half-turn-{delta}',matrix))
    rng=np.random.default_rng(20261025)
    for i in range(32):
        matrix,triangular=np.linalg.qr(rng.normal(size=(2,2))+1j*rng.normal(size=(2,2)))
        phase=np.diag(triangular);matrix=matrix@np.diag(phase/abs(phase))
        matrices.append((f'fixed-random-unitary-{i}',matrix))
    for name,matrix in matrices:
        c=cirq.Circuit(cirq.MatrixGate(matrix).on(q))
        default=cirq.merge_single_qubit_gates_to_phxz(c,atol=1e-12)
        gate=cirq.PhasedXZGate.from_matrix(matrix)
        row=dict(name=name,default_merge_error=matrix_error(cirq.unitary(default),matrix),faithful_matrix_error=matrix_error(cirq.unitary(gate),matrix))
        assert row['faithful_matrix_error']<1e-12,row
        rows.append(row)
    return rows

def main():
    start=time.monotonic();row=json.loads((h.ROOT/'polished_7_3.json').read_text())
    witness_rows=witnesses();matrix_errors=[]
    dev=cirq_google.Willow105.metadata;qr={q:(1e-3,0.) for q in dev.qubit_set};pr={tuple(e):(1e-3,0.) for e in dev.qubit_pairs}
    adj,node=h.b.make_chip(pr,qr,qr,qr,15,4);qs=h.b.best_path(adj,node,[1]*6,float('-inf'))
    goal=np.array([h.target(7,r) for r in range(4)]);checks=[];valid=[]
    def check(name,c):
        cirq_google.Willow105.validate_circuit(c)
        assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
        sim=cirq.Simulator(dtype=np.complex128)
        states=np.array([sim.simulate(c,initial_state=(1<<r)-1,qubit_order=qs).final_state_vector for r in range(4)])
        phase=np.vdot(goal,states);phase/=abs(phase);errors=np.linalg.norm(states-phase*goal,axis=1)
        report=dict(stage=name,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),max_column_error=float(max(errors)),accepted=bool(max(errors)<1e-10))
        checks.append(report)
        if report['accepted']:valid.append((report,c))
        print(report,flush=True)
    # Preserve every Ry parameter directly before trying any numerical merger.
    native=[]
    for op in h.operations(qs,row):
        if op.gate==cirq.CZ:native.append(op)
        elif isinstance(op.gate,cirq.YPowGate):
            native.append(cirq.PhasedXZGate(axis_phase_exponent=.5,x_exponent=op.gate.exponent,z_exponent=0).on(*op.qubits))
        elif isinstance(op.gate,cirq.ZPowGate):
            native.append(cirq.PhasedXZGate(axis_phase_exponent=0,x_exponent=0,z_exponent=op.gate.exponent).on(*op.qubits))
        else:raise AssertionError(op)
    direct=cirq.Circuit(native);check('direct-analytic-Ry-Z-conversion',direct)
    check('direct-analytic-schedule',h.schedule(direct,restarts=3))
    c=faithful_merge(cirq.Circuit(h.operations(qs,row)),matrix_errors);check('faithful-merge',c)
    check('faithful-schedule',h.schedule(c,restarts=3))
    for i in range(3):
        c=cirq.eject_z(c,atol=1e-12);c=cirq.eject_phased_paulis(c,atol=1e-12)
        c=faithful_merge(c,matrix_errors);c=cirq.Circuit(cirq.drop_negligible_operations(c,atol=1e-12).all_operations())
        check(f'faithful-eject-{i}',h.schedule(c,restarts=3))
    best,c=min(valid,key=lambda pair:pair[0]['depth']) if valid else (None,None)
    if best:cirq.to_json(c,h.ROOT/'faithful_decoder_7_r0to3_native.json')
    result=dict(seconds=time.monotonic()-start,checks=checks,best=best,strict_depth_opportunity=bool(best and best['depth']<54),no_refit=True,
                witness_rows=witness_rows,max_local_matrix_error=max(matrix_errors),
                implementation='Direct Ry/Z->PhasedXZ parameters and public Cirq PhasedXZGate.from_matrix; no library edits or copied package code.')
    (h.ROOT/'faithful_native_results.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
