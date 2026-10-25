"""Small deterministic graph/permutation interface audit; no synthesis/beam."""
from collections import deque
from pathlib import Path
import itertools
import json
import time

ROOT=Path(__file__).parent

def shortest(adj,start,end,active):
    queue=deque([(start,[start])]);seen={start}
    while queue:
        q,path=queue.popleft()
        if q==end:return path
        for other in sorted(adj[q]):
            if other in active and other not in seen:
                seen.add(other);queue.append((other,path+[other]))
    raise AssertionError((start,end,active))

def tree_route(adj,tree,desired):
    # Freeze a tree leaf at a time. Shortest paths may use extra physical edges
    # among active vertices, but deleting a tree leaf keeps a connected witness.
    placement={q:q for q in adj};active=set(adj);swaps=[]
    while len(active)>1:
        leaves=[q for q in active if len(tree[q]&active)<=1]
        options=[]
        for leaf in leaves:
            source=next(q for q in active if placement[q]==desired[leaf])
            path=shortest(adj,source,leaf,active)
            options.append((len(path),leaf,path))
        _,leaf,path=min(options)
        for a,b in zip(path,path[1:]):
            placement[a],placement[b]=placement[b],placement[a];swaps.append((a,b))
        assert placement[leaf]==desired[leaf]
        active.remove(leaf)
    assert placement==desired
    return swaps

def order(star,permutation):
    center,bs,aa=star
    return [aa[i] for i in permutation]+[center]+[bs[i] for i in reversed(permutation)]

def schedule_swaps(swaps):
    operations=[]
    for a,b in swaps:
        for c,t in ((a,b),(b,a),(a,b)):
            operations.extend([('H',t),('CZ',c,t),('H',t)])
    clocks={q:-1 for op in operations for q in op[1:]};scheduled=[]
    for op in operations:
        qs=op[1:];moment=max(clocks[q] for q in qs)+1
        for q in qs:clocks[q]=moment
        scheduled.append(dict(moment=moment,operation=op))
    return dict(CZ=3*len(swaps),unfused_abstract_native_moments=max(clocks.values(),default=-1)+1,operations=scheduled)

def main():
    tick=time.monotonic();device=json.loads((ROOT/'willow105_connectivity.json').read_text())
    devcells={tuple(q) for q in device['cells']};edges={frozenset(tuple(q) for q in edge) for edge in device['edges']}
    cells=tuple((r,c) for r in range(7) for c in (7,8));assert set(cells)<=devcells
    adj={q:{p for p in cells if frozenset((q,p)) in edges} for q in cells}
    stars=[]
    for center in cells:
        for bs in itertools.combinations(sorted(adj[center]),3):
            for aa in itertools.product(*[sorted(adj[b]-{center}) for b in bs]):
                if len(set((center,)+bs+aa))==7:stars.append((center,bs,aa))
    pairs=[(a,b) for i,a in enumerate(stars) for b in stars[i+1:]
           if not set((a[0],)+a[1]+a[2])&set((b[0],)+b[1]+b[2])]
    # One fixed spanning tree, not a routing search over trees or swap beams.
    tree={q:set() for q in cells}
    for q in cells:
        for p in adj[q]:
            if q[1]==p[1] or q[0]==p[0]==3:tree[q].add(p)
    assert sum(map(len,tree.values()))==26
    best=None;trials=0
    for first,second in pairs:
        for leftstar,rightstar in ((first,second),(second,first)):
            for reverse in (False,True):
                leftin=[(r,7) for r in range(7)][::(-1 if reverse else 1)]
                rightin=[(r,8) for r in range(7)][::(1 if reverse else -1)]
                assert all(frozenset((leftin[6-i],rightin[i])) in edges for i in range(7))
                for lp in itertools.permutations(range(3)):
                    leftout=order(leftstar,lp)
                    for rp in itertools.permutations(range(3)):
                        rightout=order(rightstar,rp)
                        desired=dict(zip(leftout,leftin));desired.update(zip(rightout,rightin))
                        swaps=tree_route(adj,tree,desired);trials+=1
                        candidate=dict(left_input=leftin,right_input=rightin,left_output=leftout,right_output=rightout,
                            swaps=swaps,left_star=leftstar,right_star=rightstar)
                        key=(len(swaps),str(candidate))
                        if best is None or key<best[0]:best=(key,candidate)
    candidate=best[1];swaps=candidate['swaps'];native=schedule_swaps(swaps)
    truth=[]
    for count in range(8):
        bits={q:0 for q in cells}
        for i,q in enumerate(candidate['left_input']):bits[q]=int(i>=7-count)
        for i,q in enumerate(candidate['right_input']):bits[q]=int(i>=count)
        for a,b in swaps:bits[a],bits[b]=bits[b],bits[a]
        left=[bits[q] for q in candidate['left_output']];right=[bits[q] for q in candidate['right_output']]
        assert left==[0]*(7-count)+[1]*count
        assert right==[0]*count+[1]*(7-count)
        truth.append(dict(left_count=count,right_count=7-count,left_bits=left,right_bits=right,coherent_amplitude='+1'))
    assert all(frozenset((a,b)) in edges for a,b in swaps)
    # The stricter bonus readout checker includes every device qubit, not just
    # the output/register/routing subset. The unitary interface measures none.
    diagonals={}
    for q in sorted(devcells):diagonals.setdefault(sum(q),[]).append(q)
    prior_measured=[(1,7),(5,7),(4,8)]
    touched=sorted({sum(q) for q in prior_measured})
    readout=[dict(diagonal=d,all_device_qubits=diagonals[d],proposed_measured=[q for q in prior_measured if sum(q)==d],
                  missing_device_qubits=[q for q in diagonals[d] if q not in prior_measured]) for d in touched]
    result=dict(status='Explicit standard-splitter interface constructed with no extra sites; no decoder/core score claim',
        physical_qubits=cells,total_physical_qubits=14,returned_data_qubits=14,extra_sites=0,intermediate_measurements=0,
        legal_stars_enumerated=len(stars),disjoint_star_tilings=len(pairs),fixed_assignment_trials=trials,
        method='Enumerate arm labeling/half assignment and root orientation only; each assignment uses one fixed tree-leaf routing algorithm. No beam search, coefficient fitting or variable-depth search.',
        selected=candidate,native_interface=native,unary_pair_truth=truth,
        phase_argument='EachSWAP=threeCNOT and eachCNOT=H-CZ-H has exact+1basis amplitude. The final token permutation matches all14logical wires, so it preserves arbitrary coherence, not only the eight tested count pairs.',
        logical_interface='Standard split_ops uses two straight7-site columns with reversed right ordering and seven direct rungs. The fixed permutation sends those complete registers to the two three-arm logical orders before the certified unary folds.',
        primitive_budget=dict(existing_D14k7_splitter_CZ=13,interface_CZ=native['CZ'],two_unary_folds_CZ=48,
            total_before_symmetric_cores_CZ=13+native['CZ']+48,
            note='Core gates, boundary cancellations, actual native fusion and full composition verification remain additional. CZ totals are explicit modular upper counts, not lower bounds or a native-depth comparison.'),
        readout_rule_correction=dict(source='benchmark_rule_reference.py:check_readout_diagonals',
            rule='Measure every Willow DEVICE qubit on each touched row+col diagonal; used-circuit-only grouping is insufficient.',
            prior_three_arm_adaptive_measurement=readout,
            prior_proposal_compliant_without_extra_measurements=all(not r['missing_device_qubits'] for r in readout),
            unitary_interface_affected=False,
            warning='Adding off-register measurements must be assessed against other registers, total qubit accounting, device rules and classical controls. No such adaptive extension is claimed here.'),
        peer_scope='Issue13 heading is stale open/unassigned; body reports active5-hour Slurm whole-state pruning through~10:00. This interface audit does not fit or touch those searches.',
        limitations=['Native schedule is abstract H/CZ with exact identities; no Cirq PhasedXZ export/device gate validation or full splitter/fold/core statevector check in this CPU-light audit.',
            'The root splitter is still the standard full unary encoder; no claim that this permutation is optimal or that input encoding absorbs V for free.',
            'A CNOT-only half-local map agreeing with all n+1 unary images must equal the corresponding full wire permutation because successive unary differences span the basis. Cheaper support-specific alternatives require nonlinear gates or use the cross-register count relation.',
            'The two symmetric cores must be mapped to these footprints; finite core cost and exact full decoder outputs remain unresolved.'],
        next_action='Export the fixed permutation into PhasedXZ/CZ, compose the standard13CZ splitter and two folded-unary modules, and verify all eight coherent count branches on this exact14-site footprint before adding a separately certified symmetric core.',
        seconds=time.monotonic()-tick)
    (ROOT/'interface_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(trials=trials,swaps=len(swaps),CZ=native['CZ'],abstract_moments=native['unfused_abstract_native_moments'],precore_CZ=result['primitive_budget']['total_before_symmetric_cores_CZ'],seconds=result['seconds'],selected=candidate,readout=readout),indent=2))

if __name__=='__main__':main()
