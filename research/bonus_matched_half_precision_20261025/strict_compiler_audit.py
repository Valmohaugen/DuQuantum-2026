"""Trace seven-site coefficient accuracy through default and strict compilation."""
import json
import time
import cirq
import cirq_google
import numpy as np
from . import helpers as h

def main():
    start=time.monotonic();atol=1e-12
    row=json.loads((h.ROOT/'polished_7_3.json').read_text())
    dev=cirq_google.Willow105.metadata;qr={q:(1e-3,0.) for q in dev.qubit_set};pr={tuple(e):(1e-3,0.) for e in dev.qubit_pairs}
    adj,node=h.b.make_chip(pr,qr,qr,qr,15,4);qs=h.b.best_path(adj,node,[1]*6,float('-inf'))
    goal=np.array([h.target(7,r) for r in range(4)]);checks=[]
    def check(name,c):
        sim=cirq.Simulator(dtype=np.complex128)
        states=np.array([sim.simulate(c,initial_state=(1<<r)-1,qubit_order=qs).final_state_vector for r in range(4)])
        phase=np.vdot(goal,states);phase/=abs(phase)
        err=np.linalg.norm(states-phase*goal,axis=1)
        result=dict(stage=name,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),max_column_error=float(max(err)),column_errors=err.tolist(),accepted=bool(max(err)<1e-10))
        checks.append(result);print(result,flush=True);return result
    ops=h.operations(qs,row);c=cirq.Circuit(ops);check('raw',c)
    d=cirq.merge_single_qubit_gates_to_phxz(c);check('default-merge',d)
    d=cirq.Circuit(cirq.drop_negligible_operations(d).all_operations());check('default-drop',d)
    d=h.schedule(h.optimize(d),restarts=3);check('default-optimize-schedule',d)
    def compact(c):
        c=cirq.merge_single_qubit_gates_to_phxz(c,atol=atol)
        return cirq.Circuit(cirq.drop_negligible_operations(c,atol=atol).all_operations())
    c=compact(c);check('strict-compile',c);candidates=[c]
    for i in range(3):
        c=cirq.eject_z(c,atol=atol)
        c=cirq.eject_phased_paulis(c,atol=atol)
        c=compact(c);check(f'strict-eject-{i}',c);candidates.append(c)
    c=cirq.optimize_for_target_gateset(c,gateset=cirq.CZTargetGateset(allow_partial_czs=False,atol=atol),max_num_passes=3)
    c=compact(c);check('strict-gateset',c);candidates.append(c)
    c=h.schedule(min(candidates,key=len),restarts=3)
    final=check('strict-final-schedule',c)
    cirq_google.Willow105.validate_circuit(c)
    assert all(op.gate==cirq.CZ or isinstance(op.gate,cirq.PhasedXZGate) for op in c.all_operations())
    if final['accepted']:cirq.to_json(c,h.ROOT/'strict_decoder_7_r0to3_native.json')
    report=dict(atol=atol,seconds=time.monotonic()-start,checks=checks,final=final,strict_depth_opportunity=final['accepted'] and final['depth']<54,no_refit=True)
    (h.ROOT/'strict_compiler_results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
