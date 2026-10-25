"""Depth diagnostic after the frozen shallow pilot; no reuse of its outputs."""
import json
import math
import time

import numpy as np
from scipy.optimize import minimize, least_squares
from .pilot import Core, Deadline, ROOT


def main():
    start = time.monotonic()
    rows = []
    for n, cycles in [(3, 3), (3, 4), (5, 4), (5, 5)]:
        for seed in (2, 3):
            core = Core(n, cycles, 'each')
            tick = time.monotonic()
            stop = min(start+120, tick+15)
            x = np.random.default_rng([90253, n, cycles, seed]).uniform(-math.pi, math.pi, core.count)
            best = [float('inf'), x.copy()]

            def objective(x):
                if time.monotonic() > stop:
                    raise Deadline()
                value, gradient = core.value_gradient(x)
                if value < best[0]:
                    best[:] = [value, x.copy()]
                return value, gradient

            termination = 'optimizer returned'
            try:
                result = minimize(objective, x, jac=True, method='L-BFGS-B',
                    options=dict(maxiter=1200, gtol=1e-12, ftol=1e-15, maxls=30))
                termination = str(result.message)
            except Deadline:
                termination = 'trial deadline'
            x = best[1]
            if best[0] < 1e-8 and time.monotonic()+.5 < stop:
                output = core.forward(x)[-1]
                z = np.r_[x, np.angle((core.target.conj()*output).sum(axis=0))]
                cache = [None, None]

                def both(z):
                    if time.monotonic() > stop:
                        raise Deadline()
                    if cache[0] is None or not np.array_equal(cache[0], z):
                        cache[:] = [z.copy(), core.residual_jacobian(z)]
                    return cache[1]

                try:
                    result = least_squares(lambda z: both(z)[0], z, jac=lambda z: both(z)[1],
                        max_nfev=30, gtol=1e-13, xtol=1e-13, ftol=1e-13)
                    x = result.x[:core.count]
                    termination += '; polished'
                except Deadline:
                    termination += '; polish deadline'
            output = core.forward(x)[-1]
            overlap = (core.target.conj()*output).sum(axis=0)
            errors = np.linalg.norm(output-core.target*overlap/abs(overlap), axis=0)
            row = dict(n=n, cycles=cycles, seed=seed, angles=x.tolist(),
                       column_phases=np.angle(overlap).tolist(), column_errors=errors.tolist(),
                       max_phase_aligned_error=float(max(errors)), seconds=time.monotonic()-tick,
                       termination=termination, gates=core.specification(),
                       core_CZ=sum(g['kind'] == 'CZ' or len(g['qubits']) == 2 and g['kind'] == 'X' for g in core.gates))
            rows.append(row)
            report = dict(status='running depth diagnostic', rows=rows)
            (ROOT/'continuation_results.json').write_text(json.dumps(report, indent=2)+'\n')
            print(n, cycles, seed, row['max_phase_aligned_error'], round(row['seconds'], 3), flush=True)
    report.update(status='depth diagnostic complete', elapsed_seconds=time.monotonic()-start)
    (ROOT/'continuation_results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
