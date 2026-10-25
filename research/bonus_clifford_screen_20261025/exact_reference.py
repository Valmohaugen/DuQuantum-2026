"""Exact symbolic PORT014 screen: no fitting or floating state simulation.

Fractions represent Q(w), w=exp(i*pi/4), w**4=-1. The small exact phase
check certifies the chosen six-CNOT Toffoli decomposition on eight basis inputs.
"""
from fractions import Fraction as F
from pathlib import Path
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
ZERO = (F(0),)*4
ONE = (F(1),F(0),F(0),F(0))
OMEGA = (F(0),F(1),F(0),F(0))
OMEGA_INV = (F(0),F(0),F(0),F(-1))
INV_SQRT2 = (F(0),F(1,2),F(0),F(-1,2))


def add(a,b):
    return tuple(x+y for x,y in zip(a,b))


def neg(a):
    return tuple(-x for x in a)


def mul(a,b):
    result = [F(0)]*4
    for i,x in enumerate(a):
        for j,y in enumerate(b):
            result[(i+j)%4] += x*y*(-1 if i+j>=4 else 1)
    return tuple(result)


def ccx_decomposition(a,b,t):
    return [('H',t),('CX',b,t),('TDG',t),('CX',a,t),('T',t),
            ('CX',b,t),('TDG',t),('CX',a,t),('T',b),('T',t),
            ('H',t),('CX',a,b),('T',a),('TDG',b),('CX',a,b)]


def exact_toffoli_check():
    results = []
    for basis in range(8):
        state = [ZERO]*8
        state[basis] = ONE
        for gate in ccx_decomposition(0,1,2):
            if gate[0]=='CX':
                a,b = gate[1:]
                updated = [ZERO]*8
                for i,value in enumerate(state):
                    j = i ^ ((1<<(2-b)) if i&(1<<(2-a)) else 0)
                    updated[j] = value
                state = updated
            elif gate[0] in ('T','TDG'):
                q = gate[1]
                factor = OMEGA if gate[0]=='T' else OMEGA_INV
                state = [mul(value,factor) if i&(1<<(2-q)) else value
                         for i,value in enumerate(state)]
            else:
                q = gate[1]
                updated = state.copy()
                for i in range(8):
                    if i&(1<<(2-q)):
                        continue
                    j = i^(1<<(2-q))
                    updated[i] = mul(add(state[i],state[j]),INV_SQRT2)
                    updated[j] = mul(add(state[i],neg(state[j])),INV_SQRT2)
                state = updated
        expected = basis ^ (1 if (basis&6)==6 else 0)
        assert state == [ONE if i==expected else ZERO for i in range(8)]
        results.append(dict(input=basis,output=expected,exact_nonzero_amplitude='+1'))
    return results


# Input (a,b,c) represents4a+2b+c at q3,q5,q6, all other output sites start0.
# Final q0..q6 is0^(7-r)1^r. Every listed gate is an exact reversible permutation.
CONVERTER = [('CCX',3,5,1),('CCX',1,6,0),('CX',1,2),('CCX',3,6,2),
             ('CX',0,2),('CX',3,4),('CCX',5,6,4),('CX',0,4),
             ('CX',5,6),('CX',2,6),('CX',4,6),('CX',0,6),
             ('CX',3,5),('CX',1,5)]


def main():
    toffoli_check = exact_toffoli_check()
    truth = []
    for r in range(8):
        bits = [0,0,0,(r>>2)&1,0,(r>>1)&1,r&1]
        initial = bits.copy()
        for gate in CONVERTER:
            if gate[0]=='CX':
                _,a,b = gate
                bits[b] ^= bits[a]
            else:
                _,a,b,t = gate
                bits[t] ^= bits[a]&bits[b]
        assert bits == [0]*(7-r)+[1]*r
        truth.append(dict(count=r,input=initial,output=bits,coherent_phase='+1'))
    elementary = []
    for gate in CONVERTER:
        elementary.extend(ccx_decomposition(*gate[1:]) if gate[0]=='CCX' else [gate])
    logical_cx = sum(g[0]=='CX' for g in elementary)
    single = sum(g[0]!='CX' for g in elementary)
    assert logical_cx==34 and single==36
    # A deliberately simple, fully reversible routing upper bound: move the
    # control along the path, apply adjacentCX, restore everySWAP in reverse.
    adjacent_cx = 0
    route_rows = []
    for gate in elementary:
        if gate[0]!='CX':
            continue
        _,a,b = gate
        distance = abs(a-b)
        cost = 6*(distance-1)+1
        adjacent_cx += cost
        route_rows.append(dict(control=a,target=b,distance=distance,adjacent_CX=cost))
    pool_path = REPO/'research/bonus_half_precision_20261025/comparison_circuits.json'
    pool = json.loads(pool_path.read_text())
    edges = {tuple(sorted((tuple((q['row'],q['col'])) for q in op['qubits'])))
             for m in pool['14,7']['moments'] for op in m['operations'] if len(op['qubits'])==2}
    path = [(r,7) for r in range(7)]
    assert all(tuple(sorted((path[i],path[i+1]))) in edges for i in range(6))
    assert sum(math.comb(7,i)**2 for i in range(8))==math.comb(14,7)
    audit = dict(
        status='Exact symbolic converter and phase verification complete; finite cost screen only',
        inherited_work='PORT014 follows BR103; no random decoder fit or topology search was run.',
        sources=[dict(title='On the CNOT-cost of TOFFOLI gates',authors='Vivek V. Shende and Igor L. Markov',
                      url='https://arxiv.org/abs/0803.2316',finding='An exact Toffoli admits six CNOTs and single-qubit gates. This audit verifies one concrete decomposition exactly.'),
                 dict(path=str(pool_path.relative_to(REPO)),sha256=hashlib.sha256(pool_path.read_bytes()).hexdigest()),
                 dict(path='research/bonus_band_20261025/compressed_splitter_research.json')],
        encoding=dict(qubits=7,external_ancillas=0,binary_input_sites=[3,5,6],output='q0..q6 = 0^(7-r)1^r',supported_counts=list(range(8))),
        converter_gates=CONVERTER,converter_truth_table=truth,
        exact_phase_check=dict(field='Q(w), w^4=-1; H factor=(w-w^3)/2; T=w; Tdag=-w^3',
                               arithmetic='Python Fraction exact rational arithmetic; no tolerance',
                               Toffoli_decomposition=ccx_decomposition(0,1,2),eight_basis_checks=toffoli_check,
                               conclusion='Each implemented Toffoli and CNOT has exact +1 computational-basis amplitude, hence the converter preserves a common +1 phase across all eight labels.'),
        logical_resources=dict(Toffoli=4,CNOT=10,CZ_after_standard_decomposition=logical_cx,
                               additional_one_qubit_HT_gates=single,
                               serial_native_moment_upper_bound=3*logical_cx+single,
                               native_rule='CNOT=H(target) CZ H(target); H,T,Tdag are allowed single-qubit gates up to a common scalar.'),
        conservative_path_route=dict(physical_sites=path,edge_evidence='Every path edge occurs in the independently verified frozen D14,7 circuit.',
                                     method='For each logical CNOT at distance d, use d-1 SWAPs, one adjacent CNOT, and reverse the SWAPs; each SWAP is3CNOTs.',
                                     adjacent_CZ=adjacent_cx,serial_native_moment_upper_bound=3*adjacent_cx+single,
                                     routed_CNOTs=route_rows,
                                     caveat='Deliberately unoptimized upper bound, not the minimum routed cost. No compiled candidate or native-depth improvement is claimed.'),
        compressed_root=dict(case=[14,7],amplitudes='C(7,i)/sqrt(C(14,7))',
                             copy='Three parallel boundary CNOTs and bitwise complement realize |i>|7-i>. Root state-preparation/routing costs are additional.',
                             coherence='With both converters and common-phase unary decoders, each final weight7 basis string has amplitude1/sqrt(C(14,7)); phases remain common.',
                             normalization_identity='sum_i C(7,i)^2=C(14,7), checked in exact integer arithmetic.'),
        comparison=dict(current_native_depth=108,current_CZ=175,current_root_builder_CZ=13,
                        added_converter_CZ_two_halves=68,compressed_root_cross_CZ=3,
                        optimistic_module_CZ_overhead=58,
                        overhead_assumptions='34+34+3-13=58, even assigning zero cost to compressed-root state preparation. This compares unchanged terminal modules before routing and cross-module cancellation; it is not a general lower bound or a native-depth proof.',
                        recommendation='Do not fit this naive converter-plus-existing-unary-decoder construction. A fused coherent seven-site binary decoder or exact boundary cancellation is needed to establish a different finite-depth mechanism.'),
        limitations=['The converter uses all7 sites as outputs; no ancilla cleanup remains outside the data.',
                     'The parent high-weight terminal decoders still need independent r0..7 common-phase evidence when assembled; existing six-site certificates do not alone certify seven-site binary decoding.',
                     'No floating state simulation, compiler benchmark, hardware change, or synthesis was run.',
                     'Hardware promotion is outside this audit; the separate candidate has a reported signed-ZZ regression and remains unpromoted.'])
    (ROOT/'converter_audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps(dict(truth_rows=len(truth),phase_checks=len(toffoli_check),logical_CZ=logical_cx,
                          routed_CZ_upper_bound=adjacent_cx,routed_serial_moments=3*adjacent_cx+single),indent=2))


if __name__=='__main__':
    main()
