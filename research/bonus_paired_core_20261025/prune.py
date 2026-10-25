"""Bounded independent single-CZ deletion trials from the exact logical pair."""
import json
import math
import os
import time

import numpy as np
from scipy.optimize import minimize, least_squares
from . import peer_synth_snapshot as synth
from .warmstart import ROOT, objective_for, output_signs


def remove_cz(n, edges, angles, delete):
    result_edges = []
    result_angles = list(angles[:n])
    slots = list(range(n))
    for index, (a, b) in enumerate(edges):
        pair = angles[n+2*index:n+2*index+2]
        if index == delete:
            for q, angle in zip((a, b), pair):
                result_angles[slots[q]] += angle
        else:
            result_edges.append((a, b))
            slots[a], slots[b] = len(result_angles), len(result_angles)+1
            result_angles.extend(pair)
    return result_edges, np.array(result_angles)


def half_jacobian(n, edges, angles, inputs):
    d = 1 << n
    indices = np.arange(d)
    gates, history = [], [inputs.T]
    parameter = 0
    for kind, wires in synth.gate_list(n, edges):
        if kind == 'cz':
            a, b = [1 << (n-1-q) for q in wires]
            phase = 1.-2*((indices & a != 0) & (indices & b != 0))
            history.append(phase[:, None]*history[-1])
            gates.append(('cz', phase))
        else:
            mask = 1 << (n-1-wires)
            perm = indices ^ mask
            phase = 1.-2*((indices & mask) != 0)
            theta = angles[parameter]
            rotated = phase[perm, None]*history[-1][perm]
            history.append(math.cos(theta/2)*history[-1]+math.sin(theta/2)*rotated)
            gates.append(('ry', parameter, perm, phase, theta))
            parameter += 1
    suffix = np.eye(d)
    jac = np.zeros((len(inputs), d, len(angles)))
    for index in range(len(gates)-1, -1, -1):
        gate = gates[index]
        if gate[0] == 'cz':
            suffix *= gate[1][None, :]
        else:
            _, parameter, perm, phase, theta = gate
            jac[:, :, parameter] = (suffix@(.5*phase[perm, None]*history[index+1][perm])).T
            suffix = math.cos(theta/2)*suffix+math.sin(theta/2)*suffix[:, perm]*phase[None, :]
    return history[-1].T, jac


def state_residual_jacobian(objective, x, zset, sign=1.):
    n, cut = objective.n, objective.left_count
    left, jl = half_jacobian(n, objective.left_edges, x[:cut], objective.inputs)
    right, jr = half_jacobian(n, objective.right_edges, x[cut:], objective.inputs)
    weights = objective.weights
    partner = objective.partner
    state = np.einsum('ja,j,jb->ab', left, weights, right[partner])
    dl = np.einsum('jap,j,jb->abp', jl, weights, right[partner])
    dr = np.einsum('ja,j,jbp->abp', left, weights, jr[partner])
    frame = np.outer(output_signs(n, zset), output_signs(n, zset))
    state *= frame
    target = synth.dicke(2*n, n).reshape(state.shape)*sign
    jac = np.concatenate([dl, dr], axis=2)*frame[:, :, None]
    return (state-target).ravel(), jac.reshape(state.size, len(x))


class Deadline(Exception):
    pass


def main():
    assert os.environ.get('SYNTH_KERNEL') == '0' and synth._kernel is None
    warm = json.loads((ROOT/'warmstart.json').read_text())
    n, edges, angles, zset = warm['n'], warm['edges'], np.array(warm['angles']), warm['zset']
    baseline = objective_for(n, edges, edges, zset)
    x = np.r_[angles, angles]
    # Check the new dense residual Jacobian against a finite difference before
    # using it to certify any deletion. All search objectives remain paired.
    probe = x+.02*np.random.default_rng(90258).normal(size=len(x))
    residual, jac = state_residual_jacobian(baseline, probe, zset)
    direction = np.random.default_rng(90259).normal(size=len(x))
    epsilon = 1e-6
    finite = (state_residual_jacobian(baseline, probe+epsilon*direction, zset)[0]
              -state_residual_jacobian(baseline, probe-epsilon*direction, zset)[0])/(2*epsilon)
    jac_error = float(np.max(abs(jac@direction-finite)))
    assert jac_error < 1e-7
    start = time.monotonic()
    rows = []
    for deletion in range(10):
        tick = time.monotonic()
        stop = min(start+60, tick+5)
        left_edges, left_angles = remove_cz(n, edges, angles, deletion)
        objective = objective_for(n, left_edges, edges, zset)
        initial = np.r_[left_angles, angles]
        best = [float('inf'), initial.copy()]

        def loss(x):
            if time.monotonic() > stop:
                raise Deadline()
            value, gradient = objective.loss_gradient(x)
            if value < best[0]:
                best[:] = [value, x.copy()]
            return value, gradient

        termination = 'optimizer returned'
        try:
            result = minimize(loss, initial, jac=True, method='L-BFGS-B',
                options=dict(maxiter=400, gtol=1e-12, ftol=1e-15, maxls=30))
            termination = str(result.message)
        except Deadline:
            termination = 'trial deadline'
        x = best[1]
        sign = 1. if objective.overlap_gradient(x)[0] >= 0 else -1.
        residual, _ = state_residual_jacobian(objective, x, zset, sign)
        if np.linalg.norm(residual) < 1e-4 and time.monotonic()+.2 < stop:
            cache = [None, None]

            def both(x):
                if time.monotonic() > stop:
                    raise Deadline()
                if cache[0] is None or not np.array_equal(cache[0], x):
                    cache[:] = [x.copy(), state_residual_jacobian(objective, x, zset, sign)]
                return cache[1]

            try:
                result = least_squares(lambda x: both(x)[0], x, jac=lambda x: both(x)[1],
                    max_nfev=20, gtol=1e-13, xtol=1e-13, ftol=1e-13)
                x = result.x
                termination += '; polished'
            except Deadline:
                termination += '; polish deadline'
        residual, _ = state_residual_jacobian(objective, x, zset, sign)
        error = float(np.linalg.norm(residual))
        left, right = objective.outputs(x)
        frame = output_signs(n, zset)
        counts = [s if b == 0 else n-s for s in range(n//2+1) for b in (0, 1)]
        targets = np.array([synth.dicke(n, r) for r in counts])
        column_errors = []
        for states in (left*frame, right*frame):
            signs = np.where(np.sum(states*targets, axis=1) < 0, -1., 1.)
            column_errors.append(float(max(np.linalg.norm(states-targets*signs[:, None], axis=1))))
        row = dict(deleted_left_index=deletion, left_edges=left_edges, right_edges=edges,
                   angles=x.tolist(), zset=zset, left_parameter_count=objective.left_count,
                   logical_pair_CZ=len(left_edges)+len(edges), full_state_error=error,
                   strict_logical_state_pass=error < 1e-10, individual_core_column_errors=column_errors,
                   seconds=time.monotonic()-tick, termination=termination)
        rows.append(row)
        (ROOT/'prune_results.json').write_text(json.dumps(dict(status='running', jacobian_check=jac_error, rows=rows), indent=2)+'\n')
        print(deletion, error, round(row['seconds'], 3), termination, flush=True)
    report = dict(status='bounded logical paired deletion pilot complete; no native acceptance',
                  jacobian_direction_error=jac_error, rows=rows, seconds=time.monotonic()-start,
                  scope='Ten independent single deletions among the inverse-fold CZs in the left warm-start core. All starts use the same exact47+47CZ pair. No greedy accumulation, topology expansion, physical routing, or portfolio update.')
    (ROOT/'prune_results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
