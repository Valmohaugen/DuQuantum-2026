"""Experimental Z-output-sensitive W placement; bounded pilot domain N<=12.

Rank a small shortlist by estimated Z penalty from first-order output
probabilities. X penalty, detuning, and nonlinear E[score] are absent.
"""
import collections
import time

from .w_cost_selection import baseline
import numpy as np
from .w_state_cost import rate
from .w_z_sensitivity import probabilities


def select(n, cal, shortlist=16):
    tick = time.monotonic()
    reference, reference_qs = baseline.create_dicke_state(n, 1, *cal)
    if not 2 <= n <= 12:
        return reference, reference_qs, reference, reference_qs, {'fallback': 'outside pilot domain'}
    adj, node = baseline.make_chip(*cal, n, 1)
    skew = {q: rate(cal[3][q]) - rate(cal[2][q]) for q in node}
    bias = lambda qs: baseline.readout_bias(qs, n, 1, skew)
    trees = {}
    for root in sorted(node, key=lambda q: (node[q], q)):
        if time.monotonic() - tick > 8:
            break
        for name, builder in [('prim', baseline.prim_tree), ('bfs', baseline.bfs_tree),
                              ('bias', lambda a, nd, r, m: baseline.bias_tree(a, nd, r, m, bias))]:
            parent = builder(adj, node, root, n)
            if parent is None:
                continue
            children = collections.defaultdict(list)
            for c, p in parent.items():
                children[p].append(c)
            children, rounds, _ = baseline.broadcast_order(root, children)
            qs = {root, *parent}
            heuristic = (sum(node[q] for q in qs) + sum(2*adj[c][p] for c, p in parent.items())
                         + baseline.idle_penalty*rounds*n/2 + bias(qs))
            key = (root, tuple(sorted(parent.items())))
            trees[key] = (heuristic, name, root, children, qs)
    def cost(circuit, qs):
        valid, terms = probabilities(circuit, cal)
        fraction = float(valid.sum())
        if min(valid) <= 0 or not 0 < fraction <= 1+1e-10:
            return dict(cost=float('inf'), invalid_expansion=True, moments=len(circuit))
        conditional = valid/fraction
        floor = 1/fraction-float(sum(conditional**2))
        bias_cost = baseline.shots*float(sum((conditional-1/n)**2))
        return dict(cost=floor+bias_cost, Z_floor=floor, Z_bias=bias_cost,
                    valid_fraction=fraction, valid_probabilities=valid.tolist(),
                    terms={k:v.tolist() for k,v in terms.items()}, moments=len(circuit))
    best_c, best_qs = reference, reference_qs
    first = dict(name='baseline', **cost(reference, reference_qs))
    pool = [first]; best = first; circuits = {reference.freeze()}
    for _, name, root, children, qs in sorted(trees.values(), key=lambda x: x[0])[:shortlist]:
        if time.monotonic() - tick > 25:
            break
        circuit = baseline.compile_circuit(baseline.w_ops(root, children), dynamical_decoupling=True, pack=False)
        if circuit.freeze() in circuits:
            continue
        circuits.add(circuit.freeze())
        row = dict(name=name, root=str(root), qubits=[str(q) for q in sorted(qs)], **cost(circuit, qs))
        pool.append(row)
        if row['cost'] < best['cost'] - 1e-8:
            best_c, best_qs, best = circuit, qs, row
    return reference, reference_qs, best_c, best_qs, dict(seconds=time.monotonic()-tick,
                                                        enumerated=len(trees), pool=pool, selected=best)
