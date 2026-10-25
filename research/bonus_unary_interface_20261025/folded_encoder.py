"""Construct a direct folded D(14,7) root on14physical sites; no decoder fit."""
from pathlib import Path
from fractions import Fraction
import itertools
import json
import math
from .interface import shortest

ROOT=Path(__file__).parent

def remote_cx(path):
    d=len(path)-1
    if d==1:return [('CX',path[0],path[1])]
    indices=list(range(d))+list(range(d-2,-1,-1))+list(range(1,d))+list(range(d-2,0,-1))
    gates=[('CX',path[i],path[i+1]) for i in indices]
    assert len(gates)==4*d-4
    # Independent exact GF2 check, including arbitrary dirty intermediates.
    rows=[1<<i for i in range(len(path))]
    for i in indices:rows[i+1]^=rows[i]
    expected=[1<<i for i in range(len(path))];expected[-1]^=expected[0]
    assert rows==expected
    return gates

def build():
    old=json.loads((ROOT/'interface_results.json').read_text())
    device=json.loads((ROOT/'willow105_connectivity.json').read_text())
    cells=sorted(tuple(q) for q in old['physical_qubits']);active=set(cells)
    edges={frozenset(tuple(q) for q in e) for e in device['edges']}
    adj={q:{p for p in cells if frozenset((q,p)) in edges} for q in cells}
    ls=old['selected']['left_star'];rs=old['selected']['right_star']
    cl=tuple(ls[0]);cr=tuple(rs[0]);la=[tuple(q) for q in ls[2]];lb=[tuple(q) for q in ls[1]]
    ra=[tuple(q) for q in rs[2]];rb=[tuple(q) for q in rs[1]]
    def distance_cost(a,b):
        d=len(shortest(adj,a,b,active))-1
        return 1 if d==1 else 4*d-4
    # Only3! arm relabelings, chosen by the explicit dirty-CX formula.
    rp=min(itertools.permutations(range(3)),key=lambda p:(sum(distance_cost(lb[i],rb[p[i]]) for i in range(3)),p))
    ra=[ra[i] for i in rp];rb=[rb[i] for i in rp]
    left=la+[cl]+list(reversed(lb));right=ra+[cr]+list(reversed(rb))
    branch_gates=[];reached={cl};todo=set(la+ra+[cr])
    while todo:
        _,a,b=min((distance_cost(a,b),a,b) for a in reached for b in todo)
        branch_gates.append(('CX',a,b));reached.add(b);todo.remove(b)
    mix=[('CX',cl,b) for b in lb]
    copies=[('CX',a,b) for a,b in zip(lb,rb)]
    logical=branch_gates+mix+copies;assert len(logical)==13
    routed=[];route_records=[]
    for index,gate in enumerate(logical):
        path=shortest(adj,gate[1],gate[2],active);expanded=remote_cx(path)
        routed.extend(expanded);route_records.append(dict(logical_CX=gate,path=path,CZ=len(expanded),stage='branch' if index<7 else 'mix' if index<10 else 'copy'))
    index={q:i for i,q in enumerate(cells)}
    def linear_rows(gates):
        rows=[1<<i for i in range(14)]
        for _,a,b in gates:rows[index[b]]^=rows[index[a]]
        return rows
    assert linear_rows(logical)==linear_rows(routed)
    rows=[]
    for branch in (0,1):
        for seed_bits in itertools.product((0,1),repeat=3):
            bits={q:0 for q in cells};bits[cl]=branch
            for q,b in zip(lb,seed_bits):bits[q]=b
            for _,a,b in routed:bits[b]^=bits[a]
            for q in right:bits[q]^=1
            assert all(bits[q]==branch for q in la+[cl])
            assert all(bits[q]==(1^branch) for q in ra+[cr])
            assert all(bits[q]==(b^branch) for q,b in zip(lb,seed_bits))
            assert all(bits[q]==(1^b^branch) for q,b in zip(rb,seed_bits))
            rows.append(dict(branch=branch,seed_bits=seed_bits,exact=True))
    # q_s=2*C(7,s)^2/C(14,7) for s=0..3. Prepare a3-bit unary seed.
    weights=[Fraction(math.comb(7,s)**2,1716) for s in range(4)]
    assert sum(weights)==1
    tails=[sum(weights[s:]) for s in range(5)]
    seed_order=list(reversed(lb)) # logical positions4,5,6
    gates=[('RY',seed_order[-1],2*math.asin(math.sqrt(float(tails[1]))))]
    for j in (1,2):
        control=seed_order[3-j];target=seed_order[2-j]
        theta=2*math.asin(math.sqrt(float(tails[j+1]/tails[j])))
        # center starts0 and is coherently restored: copy control, remoteCZ,
        # uncopy. Each of these three entanglers is on a verified physical edge.
        gates += [('RY',target,-theta/2),('CX',control,cl),('CZ',cl,target),('CX',control,cl),('RY',target,theta/2)]
    gates += [('H',cl)]+routed+[('X',q) for q in right]
    assert all(frozenset((g[1],g[2])) in edges for g in gates if g[0] in ('CX','CZ'))
    target_rows=[]
    for s in range(4):
        for branch in (0,1):
            low=[0]*(7-s)+[1]*s
            lv=[x^branch for x in low];rv=[1^x for x in lv]
            bits=dict(zip(left,lv));bits.update(zip(right,rv))
            basis=sum(bits[q]<<(13-i) for i,q in enumerate(cells))
            target_rows.append(dict(seed_count=s,branch=branch,left_count=s if branch==0 else 7-s,basis=basis,
                amplitude_numerator=math.comb(7,s),amplitude_denominator_sqrt=3432))
    assert len({r['basis'] for r in target_rows})==8
    assert sum(r['amplitude_numerator']**2 for r in target_rows)==3432
    report=dict(status='Explicit routed folded-root encoding; native numerical verification separate',
        physical_qubit_order=cells,left_logical_order=left,right_logical_order=right,
        seed_order=seed_order,branch_qubit=cl,external_ancillas=0,intermediate_measurements=0,
        logical_CNOT_encoder=logical,routed_encoder=route_records,
        encoder_CZ_by_stage={stage:sum(r['CZ'] for r in route_records if r['stage']==stage) for stage in ('branch','mix','copy')},
        seed_preparation_CZ=6,total_CZ=sum(g[0] in ('CX','CZ') for g in gates),
        seed_weights=[str(w) for w in weights],seed_amplitudes='(1,7,21,35)/sqrt1716',
        boolean_checks=rows,exact_GF2_routing_matrix_check=True,target_rows=target_rows,operations=gates,
        identity='For s0..3, p_s=C(7,s)^2/C(14,7)=p_(7-s). Prepare unary s with amplitudeC(7,s)/sqrt1716 and independent branch|+>. The encoder produces (|u_s>|X u_s>+|X u_s>|u_s>)/sqrt2 in the two three-arm logical orders.',
        scope='Only the folded count root is prepared, not a Dicke state or a full decoder. Two independently certified global-X-symmetric cores are still required. No permutation interface or separate unary fold is used in this encoding.',
        comparison='This explicit68CZ folded-root construction replaces the136CZ modular root/permutation/twofold upper construction. It is not an optimality bound, a native-depth result or a portfolio-score gain.')
    assert report['total_CZ']==68
    (ROOT/'folded_encoder_plan.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    r=build();print(json.dumps(dict(CZ=r['total_CZ'],encoder=r['encoder_CZ_by_stage'],seed=r['seed_preparation_CZ'],target_rows=r['target_rows']),indent=2))
