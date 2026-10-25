"""Exact Boolean/Pauli screen; stdlib only, no matrices or synthesis."""
from collections import deque
from fractions import Fraction
from pathlib import Path
import hashlib
import itertools
import json
import math

ROOT=Path(__file__).parent

def closure(n,edges,xx=False):
    generators=[(1<<i,0) for i in range(n)]
    generators += [(0,(1<<a)|(1<<b)) for a,b in edges]
    if xx:
        a,b=edges[0];generators.append(((1<<a)|(1<<b),0))
    found=set(generators);queue=deque(generators)
    while queue:
        x,z=queue.popleft()
        for a,b in generators:
            if ((x&b).bit_count()+(z&a).bit_count())%2:
                result=(x^a,z^b)
                if result not in found:found.add(result);queue.append(result)
    assert all(z.bit_count()%2==0 for x,z in found)
    assert (0,0) not in found and ((1<<n)-1,0) not in found
    return dict(dimension=len(found),full_parity_traceless_target=2**(2*n-1)-2,
                reaches_target=len(found)==2**(2*n-1)-2,
                pauli_set_sha256=hashlib.sha256(json.dumps(sorted(found)).encode()).hexdigest())

def bipartition(n,edges):
    adj=[[] for _ in range(n)]
    for a,b in edges:adj[a].append(b);adj[b].append(a)
    color={0:0};queue=deque([0])
    while queue:
        a=queue.popleft()
        for b in adj[a]:
            if b not in color:color[b]=1-color[a];queue.append(b)
            assert color[b]!=color[a]
    assert len(color)==n
    parts=[[i for i in range(n) if color[i]==c] for c in (0,1)]
    return min(parts,key=len)

def main():
    source=json.loads((ROOT/'symmetry_decoder_research.json').read_text())
    pool=json.loads((ROOT/'physical_patch_circuits.json').read_text())
    physical=set()
    for moment in pool['14,7']['moments']:
        for op in moment['operations']:
            if len(op['qubits'])==2:
                physical.add(frozenset((q['row'],q['col']) for q in op['qubits']))
    boolean=[];graphs=[];costs=[]
    for n in (3,5,7):
        m=n//2
        def x(bits):return tuple(1-b for b in bits)
        def v(bits):return bits[::-1] if bits[m] else bits
        def unary(r):return (0,)*(n-r)+(1,)*r
        for bits in itertools.product((0,1),repeat=n):
            assert v(v(bits))==bits
            assert v(x(v(bits)[::-1]))==x(bits)
        for r in range(n+1):assert v(unary(r))==(unary(r) if r<=m else x(unary(n-r)))
        # Explicit Fredkin decomposition: CX(b,a), CCX(c,a,b), CX(b,a).
        for c,a,b in itertools.product((0,1),repeat=3):
            aa=a^b;bb=b^(c&aa);aa^=bb
            assert (aa,bb)==((b,a) if c else (a,b))
        boolean.append(dict(n=n,basis_inputs=2**n,unary_columns=n+1,all_identities_exact=True))
        cases=[('path',[(i,7) for i in range(n)],[(i,i+1) for i in range(n-1)])]
        if n==5:cases.append(('branched',[(2,7),(3,7),(4,7),(3,8),(4,8)],[(0,1),(1,2),(1,3),(3,4)]))
        if n==7:cases.append(('branched',[(1,7),(2,7),(3,7),(4,7),(5,7),(3,8),(4,8)],[(0,1),(1,2),(2,3),(3,4),(2,5),(5,6)]))
        for label,cells,edges in cases:
            assert all(frozenset((cells[a],cells[b])) in physical for a,b in edges)
            small=bipartition(n,edges);a=len(small);assert 1<=a<=m
            # T=P K, P=Y_A Z_B. Every real Xi/edgeZZ anticommutes with P.
            px=sum(1<<i for i in small);pz=(1<<n)-1
            generators=[(1<<i,0) for i in range(n)]+[(0,(1<<i)|(1<<j)) for i,j in edges]
            assert all(((px&z).bit_count()+(pz&x).bit_count())%2==1 for x,z in generators)
            # Any XX commutes with P, so its generic evolution breaks T invariance.
            i,j=edges[0];assert (pz&((1<<i)|(1<<j))).bit_count()%2==0
            input_overlap_sq=int(set(small)==set(range(n-a,n)))
            output_overlap_sq=Fraction(1,math.comb(n,a));assert 0<output_overlap_sq<1
            graphs.append(dict(n=n,graph=label,cells=cells,edges=edges,smaller_color=small,
                antiunitary_input_overlap_squared=input_overlap_sq,antiunitary_output_overlap_squared=str(output_overlap_sq),
                exact_obstruction=True,rx_zz=closure(n,edges),rx_zz_plus_first_edge_xx=closure(n,edges,True)))
        # Unrouted Fredkin: six-CNOT Toffoli plus two CNOT, nine H/T gates.
        routed=sum(72*d-40 for d in range(1,m+1))
        costs.append(dict(n=n,controlled_swaps=m,unrouted_CZ=8*m,
            unrouted_serial_native_moment_upper_bound=33*m,
            path_swap_restore_CZ_upper_bound=routed,path_serial_native_moment_upper_bound=3*routed+9*m))
    report=dict(status='Rx/ZZ-only family obstructed; enlarged algebra screened without fitting',
        exact_boolean_checks=boolean,pauli_closures=graphs,controlled_reversal_costs=costs,
        proof='For T=(Y_A Z_B)K, T H T^-1=-H for real Xi and bipartite edgeZZ. Antiunitarity also flips i, hence T commutes with every generated evolution U. But |<ua|T u0>| is 0 or1, whereas |<Da|T D0>|=1/sqrt(C(n,a)); a is smaller color size. Required two columns contradict overlap preservation, even with independent phases. V leaves these low columns unchanged.',
        scope='Odd n; connected bipartite graph; no extra ancillas; exact low columns including r=0,a. No no-go claim for general native decoders.',
        enlarged_algebra_scope='Closure under adjoints of original Pauli generators spans the generated Lie algebra by Jacobi. Dimensions reaching 2^(2n-1)-2 certify continuous-control algebra su(2^(n-1)) plus su(2^(n-1)), excluding central globalX and identity. They provide no finite CZ-depth or fixed-layer ansatz guarantee.',
        generic_rotation_primitives=dict(ZZ='H(target), CZ, Rx(target,theta), CZ, H(target)',XX='H(control), CZ, Rx(target,theta), CZ, H(control)',CZ_per_rotation=2,single_qubit_gates_per_rotation=3,serial_native_moments=5,scope='Exact conjugation constructions for exp(-i theta PP/2), adjacent pair; special angles can simplify. Counts are explicit upper bounds, not lower bounds.'),
        cost_caveat='Controlled-reversal counts are explicit decomposition upper bounds, not lower bounds. SWAP/restore routes each CNOT separately. Arbitrary ZZ/XX rotations generally require2CZ; special Clifford angles may be cheaper. Routing, cancellation and finite depth remain unoptimized.',
        odd_scope='Even n has a self-complementary middle-count complication; paired-column construction is not asserted there.',
        literature=source['sources'],
        permutation_obstruction=source['original_analysis']['obstruction'])
    (ROOT/'audit_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps([(r['n'],r['graph'],r['rx_zz']['dimension'],r['rx_zz_plus_first_edge_xx']['dimension']) for r in graphs]))

if __name__=='__main__':main()
