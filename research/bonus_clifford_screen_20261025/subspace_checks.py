"""Tiny independent truth/phase checks for PORT025; no coefficient search."""
from pathlib import Path
import itertools
import json
import math

ROOT=Path(__file__).parent

def apply(state,n,gate):
    name=gate[0];out=[0j]*len(state)
    if name in ('CX','CZ'):
        a,b=gate[1:];am=1<<(n-1-a);bm=1<<(n-1-b)
        for i,value in enumerate(state):
            if name=='CX':out[i^bm if i&am else i]+=value
            else:out[i]=(-value if i&am and i&bm else value)
        return out
    q=gate[1];mask=1<<(n-1-q)
    if name=='H':co=si=1/math.sqrt(2);matrix=((co,si),(si,-co))
    elif name=='X':matrix=((0,1),(1,0))
    elif name=='RY':
        co=math.cos(gate[2]/2);si=math.sin(gate[2]/2);matrix=((co,-si),(si,co))
    else:raise ValueError(gate)
    for i in range(len(state)):
        if i&mask:continue
        j=i|mask
        out[i]=matrix[0][0]*state[i]+matrix[0][1]*state[j]
        out[j]=matrix[1][0]*state[i]+matrix[1][1]*state[j]
    return out

def run(n,gates,basis):
    state=[0j]*(1<<n);state[basis]=1.
    for gate in gates:state=apply(state,n,gate)
    return state

def margolus(a,b,t):
    return [('RY',t,math.pi/4),('CX',b,t),('RY',t,math.pi/4),('CX',a,t),
            ('RY',t,-math.pi/4),('CX',b,t),('RY',t,-math.pi/4)]

def expected_unary(n,r):
    value=(1<<r)-1
    return value if r<=n//2 else int(f'{value:0{n}b}'[::-1],2)

def error(state,target,amplitude=1.):
    return math.sqrt(sum(abs(value-(amplitude if i==target else 0))**2 for i,value in enumerate(state)))

def rank(vectors):
    pivots={}
    for value in vectors:
        while value:
            p=value.bit_length()-1
            if p not in pivots:pivots[p]=value;break
            value^=pivots[p]
    return len(pivots)

def measurements(n,basis,outcomes):
    state=[0j]*(1<<n);state[basis]=1.;c=n//2
    for a,m in enumerate(outcomes):
        b=n-1-a
        for gate in [('CX',a,b),('CX',c,b),('H',a)]:state=apply(state,n,gate)
        mask=1<<(n-1-a)
        state=[value if bool(i&mask)==bool(m) else 0j for i,value in enumerate(state)]
        if m:
            state=apply(state,n,('X',a))
            state=apply(state,n,('CZ',c,b))
        state=apply(state,n,('CX',c,a))
    return state

def main():
    margolus_rows=[]
    for basis in range(8):
        target=basis^(1 if basis&6==6 else 0);sign=-1 if basis==5 else 1
        err=error(run(3,margolus(0,1,2),basis),target,sign)
        assert err<1e-14
        margolus_rows.append(dict(input=basis,output=target,amplitude=sign,error=err))
    rows=[]
    for n in (3,5,7):
        c=n//2;gates=[]
        for a in range(c):
            b=n-1-a
            gates += [('CX',a,b)]+margolus(b,c,a)+[('CX',a,b)]
        errors=[];branch_errors=[];branch_prob_errors=[]
        for r in range(n+1):
            target=expected_unary(n,r)
            errors.append(error(run(n,gates,(1<<r)-1),target))
            for outcomes in itertools.product((0,1),repeat=c):
                state=measurements(n,(1<<r)-1,outcomes)
                branch_errors.append(error(state,target,2**(-c/2)))
                branch_prob_errors.append(abs(sum(abs(v)**2 for v in state)-2**(-c)))
        images=[expected_unary(n,r)^expected_unary(n,r-1) for r in range(1,n+1)]
        assert rank(images)==c+1<n
        assert max(errors+branch_errors+branch_prob_errors)<1e-14
        rows.append(dict(n=n,unary_columns=n+1,unitary_logical_CX=5*c,unitary_max_common_phase_error=max(errors),
            measurement_branches_per_column=2**c,measurement_max_branch_amplitude_error=max(branch_errors),
            measurement_max_branch_probability_error=max(branch_prob_errors),
            CNOT_only_required_linear_rank=rank(images),invertibility_required_rank=n))
    # Three arms c--b_i--a_i. Shift the Margolus exception from101 to100
    # with X(target) conjugation so the twice-used control is the local b_i.
    n=7;c=3;pairs=[(a,n-1-a) for a in range(3)]
    pre=[];post=[]
    for a,b in pairs:
        pre.append([('CX',a,b),('X',a),('RY',a,math.pi/4),('CX',b,a),('RY',a,math.pi/4)])
        post.append([('RY',a,-math.pi/4),('CX',b,a),('RY',a,-math.pi/4),('X',a),('CX',a,b)])
    gates=[]
    for stage in range(5):gates.extend(group[stage] for group in pre)
    gates += [('CX',b,a) for a,b in pairs]+[('CX',c,b) for a,b in pairs]
    gates += [('CX',b,a) for a,b in pairs]+[('CX',c,b) for a,b in pairs]
    for stage in range(5):gates.extend(group[stage] for group in post)
    cells=[(1,7),(5,7),(4,8),(3,7),(3,8),(4,7),(2,7)]
    dev=json.loads((ROOT/'willow105_connectivity.json').read_text())
    device_edges={frozenset(tuple(q) for q in edge) for edge in dev['edges']}
    assert all(list(q) in dev['cells'] for q in cells)
    assert all(frozenset((cells[g[1]],cells[g[2]])) in device_edges for g in gates if g[0]=='CX')
    groups={}
    for i,(r,col) in enumerate(cells):groups.setdefault(r+col,[]).append(i)
    measured=set(range(3))
    for diagonal in {sum(cells[i]) for i in measured}:
        assert set(groups[diagonal])<=measured
    errors=[error(run(7,gates,(1<<r)-1),expected_unary(7,r)) for r in range(8)]
    assert max(errors)<1e-14
    # Explicit H-CZ-H conversion, no matrix merger, no optimization.
    native=[]
    for gate in gates:
        native.extend([('H',gate[2]),('CZ',gate[1],gate[2]),('H',gate[2])] if gate[0]=='CX' else [gate])
    clocks=[-1]*7;schedule=[]
    for gate in native:
        qs=gate[1:3] if gate[0]=='CZ' else (gate[1],)
        moment=max(clocks[q] for q in qs)+1
        for q in qs:clocks[q]=moment
        schedule.append(dict(moment=moment,operation=gate))
    native_errors=[error(run(7,native,(1<<r)-1),expected_unary(7,r)) for r in range(8)]
    assert max(native_errors)<1e-14
    report=dict(status='Supported-subspace unitary and adaptive branches verified; no full decoder or bonus gain claimed',
        margolus_exact_mapping_checked=margolus_rows,rows=rows,
        unitary_identity='CX(a,b); Margolus(controls b,c;target a); CX(a,b) agrees with controlled swap on000,001,011,111 in(a,c,b) order, with common+1phase. The transformed(control b,c,target a) support excludes the sole negative-phase pattern101.',
        measurement_identity='After b<-b XOR c XOR a, support has a=c*b. Measuring H(a) yields(-1)^(m c b)/sqrt2; conditionalCZ cancels that phase. Reset a and CX(c,a) give the required image. Every branch has the same positive amplitude2^(-m_pairs/2).',
        measurement_resources_per_pair=dict(CNOT=3,conditional_CZ=1,H=1,measurement=1,conditional_reset_X=1,warning='Unrouted branch counts only; classical latency, reset, physical routing and actual native moments unmeasured.'),
        CNOT_obstruction='Since f(u0)=0, an affine CNOT/X map has zero offset. Required images of basis differences u_r XOR u_(r-1) span onlym+1<n dimensions, so no invertible affine map realizes the requested unary images.',
        three_arm_unitary=dict(logical_qubit_cells=cells,center=c,mirror_pairs=pairs,CZ=sum(g[0]=='CZ' for g in native),
            unfused_abstract_native_moments=max(clocks)+1,gate_sequence_common_phase_error=max(errors),native_decomposition_common_phase_error=max(native_errors),
            physical_edges_checked_against='willow105_connectivity.json',external_ancillas=0,measurements=0,
            construction='X-conjugated Margolus moves its exceptional phase to100, absent from supported inputs. Each remoteCX(c,a) uses CX(b,a),CX(c,b),CX(b,a),CX(c,b), restoring dirty b. Across arms these remote gates share c only as control.',
            interface='Logical unary order a0,a1,a2,c,b2,b1,b0 is NOT a nearest-neighbor path on this footprint. Upstream splitter or an explicit interface permutation/routing must supply it. That cost is not included.',
            readout_groups_all_used_qubits=groups,
            readout_note='This unitary construction has no intermediate measurement. For an adaptive variant on the same7qubits, measuring a0,a1,a2 together touches all used qubits on diagonals8 and12. Sequentially measuring onlya1 or a2 would violate diagonal12 completeness. The dirty-intermediate remoteCX uses only these same7qubits, so no additional routing-qubit diagonals are hidden.',
            serialization='Schedule stores abstract H/Ry/X/CZ operations. H/Ry/X admit exact native PhasedXZ representatives, but this file has not performed Cirq PhasedXZ conversion or device gate validation. Cell/edge membership and explicit H-CZ-H state action were independently checked.',
            schedule=schedule),
        next_action='Freeze the24CZ three-arm supported-subspace transform, then cost and validate its interface to a concrete splitter before any symmetric-core fit. A certified full7 decoder still requires a finite-cost global-X-symmetric core; algebra closure alone is insufficient.',
        adaptive_arm_cost=dict(worst_case_CZ=21,explanation='Per pair two local preprocessingCNOT + one conditionalCZ + final remoteCX implemented with4adjacentCNOT =7CZ. This counts classically conditionedCZ in every branch; H, simultaneous measurement, resetX and classical latency are additional.',readout_diagonals_checked_for_used_qubits=True,compiled_native_depth=None,latency_and_full_rule_validation='Not evaluated; no adaptive circuit export or hardware claim.'),
        limitations=['The unitary transform agrees with V only on unary input support; it is not asserted equal on other basis inputs.','Measurement-adaptive full-rule legality, reset/classical latency and compiled native depth remain unresolved; readout-group membership alone was checked.','No routing beam, coefficient fitting, maintained solver change, native export, or portfolio integration ran.'])
    (ROOT/'subspace_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(rows=rows,arm_CZ=report['three_arm_unitary']['CZ'],arm_abstract_moments=report['three_arm_unitary']['unfused_abstract_native_moments'],max_native_error=max(native_errors)),indent=2))

if __name__=='__main__':main()
