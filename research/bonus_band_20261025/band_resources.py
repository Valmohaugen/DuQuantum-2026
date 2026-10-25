"""Native-gate costs of an explicit clean-ancilla weight-band oracle.

Connectivity is deliberately unrestricted for this preliminary rejection test.
These are NOT scored Willow circuits. Arithmetic remains a classical reversible
permutation, allowing relative-phase Toffolis inside compute/phase/uncompute.
"""
import json
import math
from pathlib import Path

import cirq
import numpy as np

from .probe import optimize


def relative_ccx(a,b,t):
    return [cirq.H(t),cirq.T(t),cirq.CNOT(b,t),cirq.T(t)**-1,
            cirq.CNOT(a,t),cirq.T(t),cirq.CNOT(b,t),cirq.T(t)**-1,cirq.H(t)]


class Builder:
    def __init__(self,n):
        self.next=n
        self.data=list(cirq.LineQubit.range(n-1))
        self.output=cirq.LineQubit(n-1)
        self.temporary=[]

    def fresh(self):
        q=cirq.LineQubit(self.next);self.next+=1
        return q

    def add(self,a,b,ops,maxsum):
        out=[];carry=None
        for i in range(max(len(a),len(b))):
            bits=([a[i]] if i<len(a) else [])+([b[i]] if i<len(b) else [])
            if carry is not None:bits.append(carry)
            if len(bits)==1:
                out.append(bits[0]);carry=None;continue
            s=self.fresh();carry=self.fresh() if i+1<maxsum.bit_length() else None
            ops.extend(cirq.CNOT(q,s) for q in bits)
            x,y=bits[:2]
            if carry is not None:
                ops.append(cirq.CCX(x,y,carry))
                if len(bits)==3:
                    ops.extend([cirq.CNOT(x,y),cirq.CCX(y,bits[2],carry),cirq.CNOT(x,y)])
            out.append(s)
        if carry is not None:out.append(carry)
        return out

    def popcount(self):
        registers=[([q],1) for q in self.data];ops=[]
        while len(registers)>1:
            result=[]
            for i in range(0,len(registers),2):
                if i+1==len(registers):result.append(registers[i]);continue
                a,an=registers[i];b,bn=registers[i+1]
                result.append((self.add(a,b,ops,an+bn),an+bn))
            registers=result
        return registers[0][0],ops

    def phase_pattern(self,bits,value,phi):
        while len(self.temporary)<len(bits)-1:self.temporary.append(self.fresh())
        flips=[cirq.X(q) for i,q in enumerate(bits) if not (value>>i)&1]
        level=list(bits);compute=[];index=0
        while len(level)>1:
            nxt=[]
            for i in range(0,len(level),2):
                if i+1==len(level):nxt.append(level[i]);continue
                t=self.temporary[index];index+=1
                compute.append(cirq.CCX(level[i],level[i+1],t));nxt.append(t)
            level=nxt
        return flips+compute+[cirq.Z(level[0])**(phi/math.pi)]+list(cirq.inverse(compute))+flips


def native(ops):
    # Each compute network must be inverted AFTER relative-phase substitution.
    return [g for op in ops for g in (relative_ccx(*op.qubits) if op.gate==cirq.CCX else [op])]


def build(n,k):
    phi=math.acos(1-2**(n-2)/math.comb(n,k))
    b=Builder(n);count,arithmetic=b.popcount()
    compute=native(arithmetic)
    # A phase pattern contains paired CCXs. Replacing inverse CCX by a fresh
    # forward relative CCX would be wrong, so construct each pair explicitly.
    def phase(bits,value):
        ideal=b.phase_pattern(bits,value,phi)
        middle=next(i for i,op in enumerate(ideal) if isinstance(op.gate,cirq.ZPowGate))
        forward=native(ideal[:middle])
        return forward+[ideal[middle]]+list(cirq.inverse(forward))
    h=[cirq.H(q) for q in b.data]
    # Two adjacent count strings form an affine line. XOR their differing bits
    # with the low bit, then ignore that low bit: one smaller predicate suffices.
    differing=(k-1)^k
    transform=[cirq.CNOT(count[0],count[i]) for i in range(1,len(count)) if (differing>>i)&1]
    representative=k
    if k&1:representative^=differing&~1
    ops=h+compute+transform+phase(count[1:],representative>>1)+list(cirq.inverse(transform))+list(cirq.inverse(compute))
    ops+=h+phase(b.data,0)+h
    if k%2:ops.append(cirq.X(b.output))
    # Reversible reduction tree computes parity without a serial fan-in.
    level=list(b.data);parity=[]
    while len(level)>1:
        nxt=[]
        for i in range(0,len(level),2):
            if i+1==len(level):nxt.append(level[i]);continue
            parity.append(cirq.CNOT(level[i],level[i+1]));nxt.append(level[i+1])
        level=nxt
    ops+=parity+[cirq.CNOT(level[0],b.output)]+list(cirq.inverse(parity))
    circuit=cirq.optimize_for_target_gateset(cirq.Circuit(ops),gateset=cirq.CZTargetGateset(allow_partial_czs=False))
    circuit=optimize(circuit)
    return circuit,b,count,arithmetic


def verify_arithmetic(n,b,count,ops):
    inputs=np.arange(2**(n-1),dtype=np.int64)
    bits={cirq.LineQubit(i):np.zeros(len(inputs),dtype=np.uint8) for i in range(b.next)}
    for i,q in enumerate(b.data):bits[q]=((inputs>>i)&1).astype(np.uint8)
    def apply(op):
        if op.gate==cirq.CNOT:
            a,t=op.qubits;bits[t]^=bits[a]
        elif op.gate==cirq.CCX:
            a,c,t=op.qubits;bits[t]^=bits[a]&bits[c]
        else:raise AssertionError(op)
    for op in ops:apply(op)
    actual=sum(bits[q].astype(np.int64)*(2**i) for i,q in enumerate(count))
    expected=np.array([int(x).bit_count() for x in inputs])
    assert np.array_equal(actual,expected)
    for op in reversed(ops):apply(op)
    assert all(not bits[cirq.LineQubit(i)].any() for i in range(n,b.next))


def main():
    qs=cirq.LineQubit.range(3)
    u=cirq.unitary(cirq.Circuit(relative_ccx(*qs)))
    assert np.allclose(abs(u),abs(cirq.unitary(cirq.CCX)),atol=1e-14)
    rows=[]
    for n,k in [(4,2),(8,4),(12,6),(15,7)]:
        c,b,count,arithmetic=build(n,k)
        verify_arithmetic(n,b,count,arithmetic)
        error=None
        if b.next<=20:
            state=cirq.Simulator(dtype=np.complex128).simulate(c,qubit_order=cirq.LineQubit.range(b.next)).final_state_vector
            target=np.zeros(2**b.next,dtype=complex)
            for x in range(2**n):
                if x.bit_count()==k:target[x<<(b.next-n)]=1/math.sqrt(math.comb(n,k))
            overlap=np.vdot(target,state);error=float(np.linalg.norm(state-target*overlap/abs(overlap)))
            assert error<1e-10,error
        row=dict(N=n,k=k,qubits=b.next,depth_unrestricted_connectivity=len(c),CZ=sum(op.gate==cirq.CZ for op in c.all_operations()),arithmetic_basis_cases=2**(n-1),small_full_state_error=error)
        rows.append(row);print(row,flush=True)
    Path(__file__).with_name('band_resources.json').write_text(json.dumps(dict(status='Resource estimate only; no Willow routing; not a scored candidate',rows=rows),indent=2))


if __name__=='__main__':main()
