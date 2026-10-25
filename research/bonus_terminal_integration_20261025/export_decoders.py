"""Emit improved native schedules for existing decoder compositions, without fitting."""
import json
from pathlib import Path

import cirq
import cirq_google
import numpy as np

from .integrate import b,load_decoders,operations,compile_ops,target,optimize,schedule

ROOT=Path(__file__).parent


def main():
    library=load_decoders();row=next(row for name,row in library if name=='five_complex')
    records=[]
    for n in (5,6):
        qs=[cirq.GridQubit(2,4+i) for i in range(n)]
        steps,_=b.line_plan(n,n,True,0)
        ops=b.line_ops(qs,n,[step for step in steps if step[1]>5],False)+operations(qs[:5],row)
        c=schedule(optimize(compile_ops(ops)),restarts=6)
        actual=cirq.unitary(c)[:,[(1<<r)-1 for r in range(n+1)]].T
        goal=np.array([target(n,r) for r in range(n+1)]);overlap=np.vdot(goal,actual);phase=overlap/abs(overlap)
        errors=np.linalg.norm(actual-phase*goal,axis=1)
        assert max(errors)<1e-10;cirq_google.Willow105.validate_circuit(c)
        name=f'decoder_{n}_allcounts_native.json';cirq.to_json(c,ROOT/name)
        record=dict(n=n,k=n,depth=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),max_column_error=float(max(errors)),column_errors=errors.tolist(),common_phase=[float(phase.real),float(phase.imag)],encoding='|0^(n-r)1^r> -> D(n,r), r=0..n, with one common phase',circuit=name,source='Existing complex five-site decoder plus unchanged analytic prefix; native compilation only')
        records.append(record);print(record,flush=True)
    (ROOT/'exported_decoder_checks.json').write_text(json.dumps(records,indent=2))


if __name__=='__main__':main()
