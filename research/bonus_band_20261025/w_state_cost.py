"""Leading-order state infidelity for native depolarization and Markovian decay.

For pure |psi>, depolarization on d-dimensional subsystem A loses
4^k p/(4^k-1) * (1 - Tr(rho_A^2)/d) fidelity. Amplitude damping loses
gamma * (<n> - |<sigma_->|^2), and phase damping loses gamma * Var(n).
These follow directly by expanding the channel Kraus operators. Errors add to
first order under subsequent ideal unitary evolution. Quasistatic detuning and
the nonlinear finite-shot score are deliberately absent from this surrogate.
"""
import math

import cirq
import numpy as np

T1=68e-6
T2=89e-6
DUR_CZ=42e-9
DUR_1Q=25e-9


def rate(value):
    try:return float(value[0])
    except (TypeError,IndexError):return float(value)


def infidelity_cost(circuit,cal,details=False):
    cz,sq,_,_=cal
    edges={frozenset(qs):rate(v) for qs,v in cz.items()}
    qs=sorted(circuit.all_qubits());n=len(qs);index={q:i for i,q in enumerate(qs)}
    state=np.zeros((2,)*n,dtype=np.complex128);state[(0,)*n]=1
    terms=dict(single_qubit=0.,two_qubit=0.,relaxation=0.,dephasing=0.)
    tphi=1/(1/T2-1/(2*T1));unitaries={}
    def reduced(positions):
        matrix=np.moveaxis(state,positions,range(len(positions))).reshape(2**len(positions),-1)
        return matrix@matrix.conj().T
    for moment in circuit:
        duration=DUR_CZ if any(len(op.qubits)==2 for op in moment) else DUR_1Q
        for op in moment:
            positions=[index[q] for q in op.qubits]
            if op.gate==cirq.CZ:
                sl=[slice(None)]*n
                for i in positions:sl[i]=1
                state[tuple(sl)]*=-1
            else:
                assert len(positions)==1
                if op.gate not in unitaries:unitaries[op.gate]=cirq.unitary(op)
                i=positions[0];state=np.moveaxis(np.tensordot(unitaries[op.gate],state,axes=([1],[i])),0,i)
        locals_=[reduced([i]) for i in range(n)]
        for op in moment:
            if len(op.qubits)==1:
                rho=locals_[index[op.qubits[0]]]
                terms['single_qubit']+=4/3*rate(sq[op.qubits[0]])*(1-np.sum(abs(rho)**2).real/2)
            else:
                rho=reduced([index[q] for q in op.qubits])
                terms['two_qubit']+=16/15*edges[frozenset(op.qubits)]*(1-np.sum(abs(rho)**2).real/4)
        for rho in locals_:
            p1=float(rho[1,1].real)
            terms['relaxation']+=duration/T1*(p1-abs(rho[0,1])**2)
            terms['dephasing']+=2*duration/tphi*p1*(1-p1)
    result=float(sum(terms.values()))
    return (result,{key:float(value) for key,value in terms.items()}) if details else result


if __name__=='__main__':
    import json,sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'ryon'))
    import fast_eval
    q=cirq.LineQubit.range(4)
    circuit=cirq.Circuit(cirq.H.on_each(*q),cirq.CZ(q[0],q[1]),cirq.ry(.7)(q[2]),cirq.CZ(q[1],q[2]),cirq.ry(-.4)(q[1]),cirq.CZ(q[2],q[3]))
    cal=({(q[i],q[i+1]):(.004+i*.001,0.) for i in range(3)},{x:(.001+.0001*i,0.) for i,x in enumerate(q)},{x:(0.,0.) for x in q},{x:(0.,0.) for x in q})
    predicted,parts=infidelity_cost(circuit,cal,True)
    psi=cirq.Simulator(dtype=np.complex128).simulate(circuit,qubit_order=q).final_state_vector
    old1,old2=fast_eval.T1,fast_eval.T2;checks=[]
    try:
        for epsilon in (1e-2,1e-3,1e-4):
            fast_eval.T1=T1/epsilon;fast_eval.T2=T2/epsilon
            scaled=[{key:(value[0]*epsilon,0.) for key,value in d.items()} for d in cal[:2]]
            rho=fast_eval.Rho(4);fast_eval.run_noisy(rho,list(circuit),{x:i for i,x in enumerate(q)},*scaled,{x:0. for x in q})
            actual=(1-float(np.vdot(psi,rho.t.reshape(16,16)@psi).real))/epsilon
            checks.append(dict(epsilon=epsilon,predicted=predicted,measured_derivative=actual,error=abs(actual-predicted)))
        assert checks[-1]['error']<2e-7,checks
        assert checks[-1]['error']<checks[0]['error']/50,checks
    finally:fast_eval.T1,fast_eval.T2=old1,old2
    Path(__file__).with_name('w_state_cost_checks.json').write_text(json.dumps(dict(terms=parts,checks=checks),indent=2))
    print(checks,flush=True)
