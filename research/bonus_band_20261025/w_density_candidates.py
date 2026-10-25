"""PORT023 candidate exposure copy of frozen PORT016 selector.

Rank by uniform J=0,25,50,100 kHz and four fixed signed fields at100kHz,
requiring nominal surrogate cost no worse than baseline. This is a heuristic;
X penalty, detuning, mixed noise terms and nonlinear E[score] are absent.
"""
import collections
import math
import time

from .w_cost_selection import baseline
import numpy as np
from .w_state_cost import rate
from .w_z_sensitivity import probabilities
from .w_zz_sensitivity import coefficients as uniform_coefficients
from .w_edge_sensitivity import coefficients, signs


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
        expansion = uniform_coefficients(circuit, cal[0])
        values = {}
        for hz in (0.,25000.,50000.,100000.):
            scale=hz/expansion['reference_hz']
            predicted=valid+scale*expansion['linear']+scale**2*expansion['quadratic']
            fraction=float(predicted.sum())
            if min(predicted)<=0 or not 0<fraction<=1+1e-10:
                values[str(int(hz))]=dict(penalty=float('inf'),invalid_expansion=True)
                continue
            conditional=predicted/fraction
            floor=1/fraction-float(sum(conditional**2))
            bias_cost=baseline.shots*float(sum((conditional-1/n)**2))
            values[str(int(hz))]=dict(penalty=floor+bias_cost,Z_floor=floor,Z_bias=bias_cost,valid_fraction=fraction)
        # Fixed physical fields are independent of calibration/evaluation seeds.
        # Evaluate both signs; no second propagation is needed for the negative.
        for pattern in range(4):
            field = coefficients(circuit, signs(cal[0], pattern))
            for orientation in (-1, 1):
                predicted = valid + orientation*field['linear'] + field['quadratic']
                fraction = float(predicted.sum())
                key = f'physical_pattern_{pattern}_sign_{orientation}'
                if min(predicted)<=0 or not 0<fraction<=1+1e-10:
                    values[key] = dict(penalty=float('inf'), invalid_expansion=True)
                    continue
                conditional = predicted/fraction
                floor = 1/fraction-float(sum(conditional**2))
                bias_cost = baseline.shots*float(sum((conditional-1/n)**2))
                values[key] = dict(penalty=floor+bias_cost, Z_floor=floor,
                                   Z_bias=bias_cost, valid_fraction=fraction)
        return dict(cost=max(v['penalty'] for v in values.values()),nominal_cost=values['0']['penalty'],
                    coupling_models=values,moments=len(circuit))
    best_c, best_qs = reference, reference_qs
    first = dict(name='baseline', **cost(reference, reference_qs))
    pool = [first]; best = first; circuits = {reference.freeze()}
    native_candidates = [(reference, reference_qs, first)]
    if not math.isfinite(first['cost']):
        return reference, reference_qs, reference, reference_qs, dict(seconds=time.monotonic()-tick, fallback='invalid baseline expansion', selected=first, pool=[first], enumerated=len(trees))
    for _, name, root, children, qs in sorted(trees.values(), key=lambda x: x[0])[:shortlist]:
        if time.monotonic() - tick > 25:
            break
        circuit = baseline.compile_circuit(baseline.w_ops(root, children), dynamical_decoupling=True, pack=False)
        if circuit.freeze() in circuits:
            continue
        circuits.add(circuit.freeze())
        row = dict(name=name, root=str(root), qubits=[str(q) for q in sorted(qs)], **cost(circuit, qs))
        pool.append(row)
        row['nominal_eligible']=row['nominal_cost']<=first['nominal_cost']+1e-8
        if row['nominal_eligible'] and math.isfinite(row['cost']):
            native_candidates.append((circuit, qs, row))
        if row['nominal_eligible'] and row['cost'] < best['cost'] - 1e-8:
            best_c, best_qs, best = circuit, qs, row
    return reference, reference_qs, best_c, best_qs, dict(seconds=time.monotonic()-tick,
                                                        enumerated=len(trees), pool=pool, selected=best, native_candidates=native_candidates)
