"""Bounded unit-pivot GF2 subspace encoder elimination; stdlib only, no beam."""
from collections import deque,Counter
from fractions import Fraction
from pathlib import Path
import itertools
import json
import math
import time

ROOT=Path(__file__).parent

def path(adj,start,end,allowed):
    queue=deque([(start,[start])]);seen={start}
    while queue:
        q,p=queue.popleft()
        if q==end:return p
        for other in sorted(adj[q]&allowed):
            if other not in seen:seen.add(other);queue.append((other,p+[other]))
    return None

def connected(adj,active):
    if not active:return True
    start=min(active);seen={start};queue=[start]
    for q in queue:
        for other in adj[q]&active:
            if other not in seen:seen.add(other);queue.append(other)
    return seen==active

def eliminate(adj,rows,active,pivot,column):
    assert rows[pivot]==1<<column
    parent={pivot:None};breadth=[pivot]
    for q in breadth:
        for other in sorted(adj[q]&active):
            if other not in parent:parent[other]=q;breadth.append(other)
    assert len(parent)==len(active)
    keep={pivot}
    for q in reversed(breadth):
        if rows[q]&(1<<column) or q in keep:
            keep.add(q)
            if parent[q] is not None:keep.add(parent[q])
    state=rows.copy();gates=[]
    # Fill missing parent entries postorder, leaving unit root untouched.
    for q in reversed(breadth[1:]):
        if q not in keep:continue
        p=parent[q]
        if state[q]&(1<<column) and not state[p]&(1<<column):
            state[p]^=state[q];gates.append((q,p))
    for q in reversed(breadth[1:]):
        if q not in keep:continue
        p=parent[q]
        if state[q]&(1<<column):
            assert state[p]&(1<<column)
            state[q]^=state[p];gates.append((p,q))
    assert state[pivot]==1<<column
    assert all(not state[q]&(1<<column) for q in active if q!=pivot)
    return state,gates

def native_depth(gates,n):
    clocks=[-1]*n
    for gate in gates:
        if gate[0]=='CX':parts=[('H',gate[2]),('CZ',gate[1],gate[2]),('H',gate[2])]
        else:parts=[gate]
        for part in parts:
            qs=part[1:3] if part[0]=='CZ' else (part[1],)
            moment=max(clocks[q] for q in qs)+1
            for q in qs:clocks[q]=moment
    return max(clocks)+1

def main():
    started=time.monotonic();deadline=started+30
    baseline=json.loads((ROOT/'baseline_plan.json').read_text())
    device=json.loads((ROOT/'willow105_connectivity.json').read_text())
    cells=[tuple(q) for q in baseline['physical_qubit_order']];n=len(cells);index={q:i for i,q in enumerate(cells)}
    edges={frozenset(tuple(q) for q in e) for e in device['edges']}
    adj={i:{j for j in range(n) if frozenset((cells[i],cells[j])) in edges} for i in range(n)}
    left=[index[tuple(q)] for q in baseline['left_logical_order']]
    right=[index[tuple(q)] for q in baseline['right_logical_order']]
    desired=[1]*n
    for j in range(3):desired[left[6-j]]=desired[right[6-j]]=1|(1<<(j+1))
    candidates=[];coverage=[];counts=Counter();best_plans=[]
    weights=[Fraction(math.comb(7,s)**2,1716) for s in range(4)]
    tails=[sum(weights[s:]) for s in range(5)]

    def seed_and_operations(pivots,reverse_gates):
        # t0 is the last unary bit, then t1, then t2. Every unprepared site0.
        ops=[('RY',pivots[1],2*math.asin(math.sqrt(float(tails[1]))))]
        prepared={pivots[1]};routes=[]
        for j in (1,2):
            control=pivots[j];target=pivots[j+1]
            route=path(adj,control,target,set(range(n))-(prepared-{control}))
            if route is None:return None
            theta=2*math.asin(math.sqrt(float(tails[j+1]/tails[j])))
            ops.append(('RY',target,-theta/2))
            chain=[('CX',a,b) for a,b in zip(route[:-2],route[1:-1])]
            ops+=chain+[('CZ',route[-2],target)]+list(reversed(chain))
            ops.append(('RY',target,theta/2));prepared.add(target);routes.append(route)
        ops.append(('H',pivots[0]))
        ops += [('CX',a,b) for a,b in reversed(reverse_gates)]
        ops += [('X',q) for q in right]
        return ops,routes

    def finish(rows,pivots,reverse_gates,order):
        assert sum(value!=0 for value in rows)==4
        assert all(rows[pivots[j]]==1<<j for j in range(4))
        restored=rows.copy()
        for a,b in reversed(reverse_gates):restored[b]^=restored[a]
        assert restored==desired
        # Every16assignment is checked exactly; the ten zero rows remain part
        # of the isometry, not arbitrary dirty-input columns.
        for seed in range(16):
            actual=[(row&seed).bit_count()%2 for row in rows]
            for a,b in reversed(reverse_gates):actual[b]^=actual[a]
            assert actual==[(row&seed).bit_count()%2 for row in desired]
        data=seed_and_operations(pivots,reverse_gates)
        if data is None:counts['unroutable-clean-seed']+=1;return
        ops,routes=data;cz=sum(g[0] in ('CX','CZ') for g in ops);depth=native_depth(ops,n)
        row=dict(order=order,pivots=pivots,encoder_CZ=len(reverse_gates),seed_CZ=cz-len(reverse_gates),total_CZ=cz,unfused_native_moments=depth,seed_paths=routes)
        candidates.append(row)
        plan=dict(baseline,operations=[(g[0],cells[g[1]],cells[g[2]]) if g[0] in ('CX','CZ') else (g[0],cells[g[1]],*g[2:]) for g in ops])
        for stale in ('logical_CNOT_encoder','routed_encoder','encoder_CZ_by_stage','boolean_checks','exact_GF2_routing_matrix_check','comparison'):
            plan.pop(stale,None)
        plan.update(status='New zero-ancilla-subspace GF2 encoder; native certification pending',
            seed_order=[cells[pivots[j]] for j in (3,2,1)],branch_qubit=cells[pivots[0]],
            total_CZ=cz,seed_preparation_CZ=row['seed_CZ'],affine_search=row,
            reverse_elimination_CNOT=[(cells[a],cells[b]) for a,b in reverse_gates],
            desired_rows_4bit=desired,unit_pivot_rows_4bit=rows,exact_all16_seed_checks=True,
            comparison='Frozen baseline68CZ/96moments remains unchanged; this new subspace encoder needs independent native verification.',
            scope='Prepares the same weighted folded root on14sites; assumes ten initial zeros and four prepared information bits, not a full14x14 dirty-input encoder.')
        # Retain a small diverse Pareto set for independent native checks.
        best_plans.append((cz,depth,tuple(pivots),plan))

    def visit(rows,active,pivots,gates,order,stage):
        if time.monotonic()>=deadline:return False
        counts[f'stage-{stage}-states']+=1
        if stage==4:finish(rows,pivots,gates,order);return True
        col=order[stage]
        legal=[q for q in sorted(active) if rows[q]==1<<col and connected(adj,active-{q})]
        counts[f'stage-{stage}-legal-pivots']+=len(legal)
        if not legal:counts['dead-end-no-legal-unit-pivot']+=1
        for pivot in legal:
            if time.monotonic()>=deadline:return False
            state,step=eliminate(adj,rows,active,pivot,col)
            newp=pivots.copy();newp[col]=pivot
            if not visit(state,active-{pivot},newp,gates+step,order,stage+1):return False
        return True

    for perm in itertools.permutations((1,2,3)):
        order=(0,)+perm;before=len(candidates)
        complete=visit(desired.copy(),set(range(n)),[-1]*4,[],order,0)
        coverage.append(dict(order=order,status='complete' if complete else 'deadline-truncated',completed_candidates=len(candidates)-before))
        if not complete:break
    for perm in itertools.permutations((1,2,3)):
        order=(0,)+perm
        if not any(tuple(r['order'])==order for r in coverage):coverage.append(dict(order=order,status='not-started',completed_candidates=0))
    search_seconds=time.monotonic()-started
    best_plans.sort(key=lambda x:(x[0],x[1],x[2]))
    chosen=[];seen=set()
    # MinimumCZ candidate plus depth/CZ Pareto alternatives, at most three.
    for item in best_plans:
        cz,depth,pivots,plan=item
        if pivots in seen:continue
        if not chosen or depth<min(x[1] for x in chosen):chosen.append(item);seen.add(pivots)
    chosen=sorted(chosen,key=lambda x:(x[1],x[0]))[:3]
    chosen.sort(key=lambda x:(x[0],x[1]))
    files=[]
    for i,(cz,depth,pivots,plan) in enumerate(chosen):
        name=f'candidate_{i:02d}_plan.json';(ROOT/name).write_text(json.dumps(plan,indent=2)+'\n')
        files.append(dict(file=name,CZ=cz,unfused_native_moments=depth,pivots=pivots))
    result=dict(search_budget_seconds=30,search_seconds=search_seconds,coverage=coverage,counts=dict(counts),
        completed_candidates=len(candidates),candidates=candidates,selected=files,
        baseline_CZ=68,baseline_native_moments=96,
        scope='Six t-column orders, all legal unit pivots under deterministic sorted-BFS spanning trees; no search over alternate trees, beam, coefficient fit or optimality proof.',
        exact_input_subspace_checks='Four-bit row identities and every16seed assignment passed for all completed candidates.',
        native_validation='Selected plans require independent full14qubit native state/device checks.')
    (ROOT/'search_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('search_seconds','coverage','counts','completed_candidates','selected')},indent=2),flush=True)

if __name__=='__main__':main()
