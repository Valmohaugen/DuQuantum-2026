"""PORT024: exact discrete-Clifford algebra and explicit native-cost screen.

Stdlib, bit masks, and rational cyclotomic arithmetic only. No fitting, dense
numerical matrices, routing beam, maintained-source edits, or package changes.
"""
from collections import deque
from pathlib import Path
import hashlib
import importlib.util
import itertools
import json

ROOT=Path(__file__).parent
spec=importlib.util.spec_from_file_location('exact_reference',ROOT/'exact_reference.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)

def anticommutes(p,q):
    x,z=p;a,b=q
    return ((x&b).bit_count()+(z&a).bit_count())%2

def conjugate(p,q):
    # exp(-i*pi*Q/4) P exp(+i*pi*Q/4) = +/- i QP if {P,Q}=0.
    return (p[0]^q[0],p[1]^q[1]) if anticommutes(p,q) else p

def closure(n,edges,xx,commutators):
    continuous=[(1<<q,0) for q in range(n)]
    discrete=[(0,(1<<a)|(1<<b)) for a,b in edges]
    if xx:
        a,b=edges[0];discrete.append(((1<<a)|(1<<b),0))
    found=set(continuous);queue=deque(continuous)
    while queue:
        p=queue.popleft()
        for q in discrete+(continuous if commutators else []):
            if not anticommutes(p,q):continue
            new=(p[0]^q[0],p[1]^q[1])
            if new not in found:found.add(new);queue.append(new)
    assert all(z.bit_count()%2==0 for x,z in found)
    assert (0,0) not in found and ((1<<n)-1,0) not in found
    return found

def matrix_multiply(a,b):
    return tuple(tuple(sum_field([e.mul(a[i][k],b[k][j]) for k in range(len(b))])
                       for j in range(len(b[0]))) for i in range(len(a)))

def sum_field(values):
    result=e.ZERO
    for value in values:result=e.add(result,value)
    return result

I=((e.ONE,e.ZERO),(e.ZERO,e.ONE))
H=((e.INV_SQRT2,e.INV_SQRT2),(e.INV_SQRT2,e.neg(e.INV_SQRT2)))
T=((e.ONE,e.ZERO),(e.ZERO,e.OMEGA))
TDG=((e.ONE,e.ZERO),(e.ZERO,e.OMEGA_INV))
S=((e.ONE,e.ZERO),(e.ZERO,e.mul(e.OMEGA,e.OMEGA)))

def kron(a,b):
    return tuple(tuple(e.mul(a[i//len(b)][j//len(b[0])],b[i%len(b)][j%len(b[0])])
                       for j in range(len(a[0])*len(b[0]))) for i in range(len(a)*len(b)))

def clifford_identity_checks():
    cz=tuple(tuple((e.neg(e.ONE) if i==3 else e.ONE) if i==j else e.ZERO for j in range(4)) for i in range(4))
    zz=matrix_multiply(cz,kron(S,S))
    expected_zz=tuple(tuple(([e.ONE,e.mul(e.OMEGA,e.OMEGA),e.mul(e.OMEGA,e.OMEGA),e.ONE][i]) if i==j else e.ZERO for j in range(4)) for i in range(4))
    assert zz==expected_zz
    hh=kron(H,H);xx=matrix_multiply(hh,matrix_multiply(zz,hh))
    diagonal=e.mul(e.OMEGA,e.INV_SQRT2)
    offdiagonal=e.mul(e.OMEGA,e.mul(e.neg(e.mul(e.OMEGA,e.OMEGA)),e.INV_SQRT2))
    expected_xx=tuple(tuple(diagonal if i==j else offdiagonal if i==(j^3) else e.ZERO for j in range(4)) for i in range(4))
    assert xx==expected_xx
    global_x=tuple(tuple(e.ONE if i==(j^3) else e.ZERO for j in range(4)) for i in range(4))
    assert matrix_multiply(zz,global_x)==matrix_multiply(global_x,zz)
    assert matrix_multiply(xx,global_x)==matrix_multiply(global_x,xx)
    return dict(field='Q(exp(i*pi/4)) with exact rational coefficients',
        ZZ_identity='CZ(S tensor S) = exp(i*pi/4) exp(-i*pi*ZZ/4)',
        XX_identity='(H tensor H) CZ(S tensor S) (H tensor H) = exp(i*pi/4) exp(-i*pi*XX/4)',
        matrix_identities_exact=True,global_X_commutation_exact=True,
        antiunitary='For T=Y_A Z_B K, T C_ZZ T^-1=C_ZZ while T C_XX T^-1=C_XX^dagger for the exponential representatives. C_XX^dagger C_XX^-1=iXX is not a scalar, so the old antiunitary symmetry is broken even projectively.',
        inverse='The physical fixed blocks have fourth powerI. Their inverse is available by three repetitions; allowing signed local Cliffords can implement the inverse with oneCZ. Algebra results do not assume inverse gates are free.')

def logical_reversal(n):
    gates=[];c=n//2
    for a in range(n//2):
        b=n-1-a
        gates += [('CX',b,a)]+e.ccx_decomposition(c,a,b)+[('CX',b,a)]
    return gates

def route(n,gates):
    # One fixed constructive route, not a search or a lower bound. Move the
    # control toward its target and keep the changed placement until completion.
    placement=list(range(n));native=[];swaps=[]
    def cx(a,b):native.extend([('H',b),('CZ',a,b),('H',b)])
    def swap(a,b):
        assert abs(a-b)==1
        cx(a,b);cx(b,a);cx(a,b)
        placement[a],placement[b]=placement[b],placement[a];swaps.append((a,b))
    for gate in gates:
        if gate[0]!='CX':native.append((gate[0],placement.index(gate[1])));continue
        _,a,b=gate;pa,pb=placement.index(a),placement.index(b)
        while abs(pa-pb)>1:
            nxt=pa+(1 if pb>pa else -1);swap(pa,nxt);pa=nxt
        assert placement[pa]==a and placement[pb]==b
        cx(pa,pb)
    for dest in range(n):
        pos=placement.index(dest)
        while pos>dest:swap(pos,pos-1);pos-=1
    assert placement==list(range(n))
    assert all(abs(g[1]-g[2])==1 for g in native if g[0]=='CZ')
    return native,swaps

def native_unrouted(gates):
    native=[]
    for gate in gates:
        if gate[0]=='CX':native += [('H',gate[2]),('CZ',gate[1],gate[2]),('H',gate[2])]
        else:native.append(gate)
    return native

def compile_symbolic(native,n):
    # Fuse only consecutive local gates on each wire, keeping exact matrices.
    # A nonidentity local unitary is one allowed PhasedXZ gate up to global phase.
    pending=[I for _ in range(n)];words=[[] for _ in range(n)];out=[]
    def flush(q):
        mat=pending[q]
        scalar_identity=mat[0][1]==mat[1][0]==e.ZERO and mat[0][0]==mat[1][1]
        if words[q] and not scalar_identity:out.append(('1Q',q,tuple(words[q])))
        pending[q]=I;words[q]=[]
    for gate in native:
        if gate[0]=='CZ':
            flush(gate[1]);flush(gate[2]);out.append(gate)
        else:
            name,q=gate;pending[q]=matrix_multiply({'H':H,'T':T,'TDG':TDG}[name],pending[q]);words[q].append(name)
    for q in range(n):flush(q)
    clocks=[-1]*n;schedule=[]
    for gate in out:
        qs=gate[1:3] if gate[0]=='CZ' else (gate[1],)
        moment=max(clocks[q] for q in qs)+1
        for q in qs:clocks[q]=moment
        schedule.append(dict(moment=moment,gate=gate))
    return dict(native_moments=max(clocks)+1,CZ=sum(g[0]=='CZ' for g in out),
                one_qubit_gates=sum(g[0]=='1Q' for g in out),schedule=schedule)

def main():
    prior=json.loads((ROOT/'prior_spinflip_audit.json').read_text())
    device=json.loads((ROOT/'willow105_connectivity.json').read_text())
    device_edges={frozenset(tuple(q) for q in edge) for edge in device['edges']}
    for graph in prior['pauli_closures']:
        assert all(q in device['cells'] for q in graph['cells'])
        assert all(frozenset((tuple(graph['cells'][a]),tuple(graph['cells'][b]))) in device_edges for a,b in graph['edges'])
    exact=clifford_identity_checks();toffoli=e.exact_toffoli_check()
    algebra=[]
    for row in prior['pauli_closures']:
        n,edges=row['n'],row['edges'];target=2**(2*n-1)-2
        base=closure(n,edges,False,True);enlarged=closure(n,edges,True,True)
        a,b=edges[0];xx=((1<<a)|(1<<b),0)
        conjugated={conjugate(p,xx) for p in base}
        algebra.append(dict(n=n,graph=row['graph'],cells=row['cells'],edges=edges,
            fixed_ZZ_only_orbit_size=len(closure(n,edges,False,False)),fixed_ZZ_XX_orbit_size=len(closure(n,edges,True,False)),
            fixed_ZZ_continuous_Rx_dimension=len(base),fixed_ZZ_XX_continuous_Rx_dimension=len(enlarged),target_dimension=target,
            repeated_block_full_algebra=len(enlarged)==target,
            one_XX_product_family_dimension=len(base|conjugated),one_XX_intersection_dimension=len(base&conjugated),
            closure_sha256=hashlib.sha256(json.dumps(sorted(enlarged)).encode()).hexdigest()))
    costs=[]
    for n in (3,5,7):
        # Fredkin identities plus an exact common-phase Toffoli certificate prove
        # the decomposition compositionally; no floating state simulator used.
        for c,a,b in itertools.product((0,1),repeat=3):
            aa=a^b;bb=b^(c&aa);aa^=bb
            assert (aa,bb)==((b,a) if c else (a,b))
        gates=logical_reversal(n);native,swaps=route(n,gates)
        uncompiled=compile_symbolic(native_unrouted(gates),n)
        compiled=compile_symbolic(native,n)
        (ROOT/f'controlled_reversal_{n}_native_schedule.json').write_text(json.dumps(compiled,indent=2)+'\n')
        costs.append(dict(n=n,Fredkin=n//2,logical_CX=sum(g[0]=='CX' for g in gates),
            fully_connected_native_CZ=uncompiled['CZ'],fully_connected_native_moments=uncompiled['native_moments'],
            fixed_path_swaps=len(swaps),fixed_path_native_CZ=compiled['CZ'],fixed_path_native_moments=compiled['native_moments'],
            fixed_path_single_qubit_gates=compiled['one_qubit_gates'],
            physical_path_cells=[(r,7) for r in range(n)],physical_edges_checked=True,
            serialization='Abstract exact local matrices are stored as H/T/Tdag words and counted as one allowed1q gate. No Cirq PhasedXZ conversion, native circuit export or device gate validation was performed; physical cells/edges were checked against frozen Willow105 metadata.',
            scope='One explicit nonoptimized routing and exact local-fusion schedule; constructive upper bounds only, not lower bounds or optimal depth. Unary ordering remains0..n-1 along the physical path.'))
    peer=json.loads((ROOT/'peer_full7.json').read_text())
    six=json.loads((ROOT/'certified_full6_native.json').read_text())
    six_cz=sum(op['gate'].get('cirq_type')=='CZPowGate' for moment in six['moments'] for op in moment['operations'])
    report=dict(status='Repeated fixed-Clifford algebra passes; explicit full-reversal route losesCZscreen; no finite-depth fit justified by this construction',
        exact_block_checks=exact,exact_toffoli_phase_checks=len(toffoli),algebra=algebra,controlled_reversal_costs=costs,
        primitive_costs=dict(fixed_ZZ_CZ=1,fixed_ZZ_native_moments=2,fixed_XX_CZ=1,fixed_XX_native_moments=3,
            fixed_XX_note='Two local H conjugations; H followed by S is merged into one allowed local gate. Boundary merging with core may reduce moments.',
            arbitrary_angle_ZZ_XX_CZ=2),
        closure_proof='The identity-component Lie algebra is invariant under conjugation by every available discrete Clifford and under commutation with each continuous Xi. BFS closes those operations on Pauli masks. Jacobi and Ad_C ad_X Ad_C^-1=ad_(Ad_C X) establish sufficiency. Independent Paulis give exact dimension; full target is su(2^(n-1)) direct-sum su(2^(n-1)), excluding central globalX and identity.',
        single_insertion_scope='For one fixedXX between arbitrary identity-component base circuits, tangent space after translation is g + Ad_C(g), so the Pauli union dimension is the product-family dimension. Its failure to fill the full group does NOT prove the specific coherent decoder unreachable.',
        finite_depth_caveat='Arbitrary repeated blocks and continuous controls can generate the full algebra in tested sizes, but no finite layer count, fixed sequence, CZ budget, decoder coefficients or exact shallow isometry is supplied.',
        comparison=dict(peer_full7_CZ=len(peer['edges']),peer_full7_supported_counts=list(range(8)),peer_full7_status='Supplied coefficient table; no strict common-phase certification or compiled moment comparison in this screen. Queue reports noisy A/B unhelpful; not installed.',
            existing_r0to3_native_moments=53,restricted_range_warning='The53moment decoder supports onlyr0..3 and is not an all-count comparison.',
            certified_full6_native_moments=len(six['moments']),certified_full6_CZ=six_cz,
            analytic_full7_prefix_CZ=27,analytic_full7_plus_full6_CZ=27+six_cz,
            analytic_composition_status='One all-count seven-site flagged SCS step (one2CZ Givens +five5CZ flagged Givens) then the certified six-site terminal; cost reference only, not separately compiled/certified here.',
            route_only_disadvantage='The explicit108CZ path V already exceeds83CZ supplied full7 and81CZ analytic composition before adding the decoder core. This rules out a CZ-count advantage for THIS module composition, not an optimal native-depth or general-routing lower bound.',
            unrouted_optimistic_core_CZ_budget_vs81=81-24-1,
            optimistic_budget_scope='To beat81 totalCZ with24CZ unrouted V, core must use<=56CZ before routing/cancellation; no lower bound or feasible core claim.'),
        next_action='PORT025 subspace_results.json supplies a distinct unary-only transform, avoiding the full-V requirement. First cost its interface to a concrete splitter and export/certify its24CZ three-arm schedule; only then assess a finite core skeleton. A routing beam on fullV is deferred and was not run.',
        ownership='PORT024 symbolic-only isolated screen; no overlap with ryon coefficient/topology synthesis. Root PORT023 owns heavy CPU. No routing beam or fit run.',
        peer_needs=['Queue issue11 requests better k>=4 half starts; raw7,4/5/6/7 tables are available but not installed after mixed/noisy A/B.','PORT022 previous combinations are complete and were not repeated.','High-count coherent7-site native decoding remains the relevant integration bottleneck.'])
    assert six_cz==54
    (ROOT/'screen_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(algebra=[(r['n'],r['graph'],r['fixed_ZZ_XX_continuous_Rx_dimension'],r['one_XX_product_family_dimension']) for r in algebra],costs=costs),indent=2))

if __name__=='__main__':main()
