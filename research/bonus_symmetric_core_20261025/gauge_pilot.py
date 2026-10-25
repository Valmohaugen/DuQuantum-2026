"""Matched tiny real-isometry fits, with and without eliminating input signs."""
import json
import math
import os
import time

import numpy as np
from scipy.optimize import minimize, least_squares
from . import peer_synth_snapshot as synth
from .column_gauge import real_column_loss
from .pilot import ROOT, Deadline


def forward(n, edges, theta, inputs):
    psi = synth._start(n, theta[None], inputs)
    index = 0
    for kind, wires in synth.gate_list(n, edges):
        if kind == 'ry':
            psi = synth._ry(psi, wires, np.array([math.cos(theta[index]/2)]), np.array([math.sin(theta[index]/2)]))
            index += 1
        else:
            psi = synth._cz(psi, *wires)
    return psi.reshape(len(inputs), -1)


def main():
    assert os.environ.get('SYNTH_KERNEL') == '0' and synth._kernel is None
    start = time.monotonic()
    inputs = np.eye(8)[[0, 1, 3, 7]]
    targets = np.array([synth.dicke(3, r) for r in range(4)])
    rows = []
    for count in (4, 6):
        edges = [(i % 2, i % 2+1) for i in range(count)]
        for seed in range(6):
            x0 = np.random.default_rng([90256, count, seed]).uniform(-math.pi, math.pi, synth.n_params(3, edges))
            for mode in ('common', 'independent_signs'):
                tick = time.monotonic()
                stop = min(start+120, tick+4)
                best = [float('inf'), x0.copy()]
                evaluations = [0]

                def objective(x):
                    if time.monotonic() > stop:
                        raise Deadline()
                    evaluations[0] += 1
                    if mode == 'common':
                        f, g = synth.fid_grad(3, edges, x[None], (inputs, targets))
                        value, gradient = 1-f[0]**2, -2*f[0]*g[0]
                    else:
                        f, g, _ = real_column_loss(synth.fid_grad, 3, edges, x[None], inputs, targets)
                        value, gradient = f[0], g[0]
                    if value < best[0]:
                        best[:] = [value, x.copy()]
                    return value, gradient

                termination = 'optimizer returned'
                try:
                    result = minimize(objective, x0, jac=True, method='L-BFGS-B',
                        options=dict(maxiter=500, gtol=1e-12, ftol=1e-15, maxls=30))
                    termination = str(result.message)
                except Deadline:
                    termination = 'trial deadline'
                x = best[1]
                output = forward(3, edges, x, inputs)
                overlaps = (output*targets).sum(axis=1)
                signs = np.where(overlaps < 0, -1., 1.) if mode != 'common' else np.full(4, 1. if overlaps.sum() >= 0 else -1.)
                if best[0] < 1e-8 and time.monotonic()+.2 < stop:
                    def residual(x):
                        if time.monotonic() > stop:
                            raise Deadline()
                        return (forward(3, edges, x, inputs)-targets*signs[:, None]).ravel()
                    try:
                        polished = least_squares(residual, x, max_nfev=50, gtol=1e-13, xtol=1e-13, ftol=1e-13)
                        x = polished.x
                        termination += '; polished'
                    except Deadline:
                        termination += '; polish deadline'
                output = forward(3, edges, x, inputs)
                errors = np.linalg.norm(output-targets*signs[:, None], axis=1)
                row = dict(n=3, CZ=count, edges=edges, seed=seed, mode=mode, angles=x.tolist(),
                           signs=signs.tolist(), errors=errors.tolist(), max_column_error=float(max(errors)),
                           evaluations=evaluations[0], seconds=time.monotonic()-tick, termination=termination)
                rows.append(row)
                (ROOT/'gauge_pilot_results.json').write_text(json.dumps(dict(status='running', rows=rows), indent=2)+'\n')
                print(count, seed, mode, row['max_column_error'], round(row['seconds'], 3), flush=True)
    report = dict(status='complete matched tiny pilot; native certificate required for any acceptance',
                  rows=rows, elapsed_seconds=time.monotonic()-start,
                  comparison='Identical topologies, starts, iteration cap and4s per-trial cap. Independent-sign reference gradient has extra backend calls; walltime is reported, not assumed equal work.')
    (ROOT/'gauge_pilot_results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
