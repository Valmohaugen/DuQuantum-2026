"""Fixed 26-CZ coefficient polishing; all five columns share one real sign.

Run only after the coordinator releases the single compute slot. No topology
changes, unsupported r=5 claims, or maintained-solver writes are performed.
"""
import argparse
import hashlib
import json
import math
import time
from pathlib import Path

import cirq
import numpy as np
from scipy.optimize import least_squares

from .helpers import certify, compile_ops, operations
from .probe import optimize
from .commuting_schedule import schedule

ROOT = Path(__file__).parent


class BudgetExpired(Exception):
    pass


def states_and_jacobian(theta, edges):
    """Forward state and tangent propagation, independent of Cirq compilation."""
    n, columns = 5, 5
    all_states = np.zeros((len(theta) + 1, columns, 2**n))
    for r in range(columns):
        all_states[0, r, (1 << r) - 1] = 1
    gates = [('ry', q) for q in range(n)]
    for a, b in edges:
        gates.extend([('cz', (a, b)), ('ry', a), ('ry', b)])
    parameter = 0
    indices = np.arange(2**n)
    for kind, data in gates:
        if kind == 'cz':
            a, b = data
            mask = (1 << (n - 1 - a)) | (1 << (n - 1 - b))
            all_states[:, :, (indices & mask) == mask] *= -1
            continue
        tensor = all_states.reshape((len(theta) + 1, columns) + (2,) * n)
        a, b = np.take(tensor, 0, axis=data + 2), np.take(tensor, 1, axis=data + 2)
        co, si = np.cos(theta[parameter] / 2), np.sin(theta[parameter] / 2)
        tensor = np.stack([co * a - si * b, si * a + co * b], axis=data + 2)
        state = tensor[0]
        a, b = np.take(state, 0, axis=data + 1), np.take(state, 1, axis=data + 1)
        tensor[parameter + 1] = np.stack([-b / 2, a / 2], axis=data + 1)
        all_states = tensor.reshape((len(theta) + 1, columns, 2**n))
        parameter += 1
    assert parameter == len(theta)
    return all_states[0], all_states[1:].reshape(len(theta), -1).T


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=60)
    args = parser.parse_args()
    original_path = ROOT / 'original_five_four.json'
    original = json.loads(original_path.read_text())
    assert (original['a'], original['k'], original['lmin']) == (5, 4, 0)
    edges, initial = original['edges'], np.asarray(original['angles'])
    assert len(edges) == 26 and len(initial) == 57
    goal = np.array([[int(i.bit_count() == r) / math.sqrt(math.comb(5, r))
                      for i in range(32)] for r in range(5)])
    old = dict(original, n=5, complex=False, zset=[])
    original_native = certify('original-five-four', old)
    start = time.monotonic()
    state, jacobian = states_and_jacobian(initial, edges)
    sign = 1. if np.vdot(goal, state).real >= 0 else -1.
    goal *= sign
    derivative_errors = []
    for parameter in (0, 28, 56):
        plus, minus = initial.copy(), initial.copy()
        plus[parameter] += 1e-6
        minus[parameter] -= 1e-6
        finite = (states_and_jacobian(plus, edges)[0] - states_and_jacobian(minus, edges)[0]) / 2e-6
        derivative_errors.append(float(np.max(abs(finite.ravel() - jacobian[:, parameter]))))
    assert max(derivative_errors) < 1e-7, derivative_errors
    cache = {}
    best = {'theta': initial.copy(), 'norm': float('inf'), 'calls': 0}

    def evaluate(theta):
        if time.monotonic() - start > args.seconds:
            raise BudgetExpired()
        if 'theta' not in cache or not np.array_equal(theta, cache['theta']):
            output, derivative = states_and_jacobian(theta, edges)
            residual = (output - goal).ravel()
            cache.update(theta=theta.copy(), residual=residual, jacobian=derivative)
            best['calls'] += 1
            norm = float(np.linalg.norm(residual))
            if norm < best['norm']:
                best.update(theta=theta.copy(), norm=norm)
        return cache

    termination = 'converged'
    try:
        fit = least_squares(lambda x: evaluate(x)['residual'], initial,
                            jac=lambda x: evaluate(x)['jacobian'], method='lm',
                            ftol=1e-14, xtol=1e-14, gtol=1e-14, max_nfev=250)
        evaluate(fit.x)
        termination = str(fit.message)
    except BudgetExpired:
        termination = '60-second numerical deadline reached; best iterate retained'
    numerical_seconds = time.monotonic() - start
    polished = dict(original, n=5, complex=False, zset=[], angles=best['theta'].tolist())
    assert polished['edges'] == original['edges']
    check = certify('polished-five-four', polished)
    report = dict(status='certified' if check['accepted'] else 'not certified',
                  input_sha256=hashlib.sha256(original_path.read_bytes()).hexdigest(),
                  numerical_budget_seconds=args.seconds, numerical_seconds=numerical_seconds,
                  termination=termination, residual_calls=best['calls'],
                  real_common_sign=sign, derivative_max_errors=derivative_errors,
                  original_native=original_native, polished_native=check,
                  fixed_topology_CZ=26, fixed_parameter_count=57, supported_r=list(range(5)),
                  maximum_angle_change=float(np.max(abs(best['theta'] - initial))))
    (ROOT / 'polished_five_four.json').write_text(json.dumps(polished, indent=2) + '\n')
    (ROOT / 'precision_results.json').write_text(json.dumps(report, indent=2) + '\n')
    if check['accepted']:
        qs = [cirq.GridQubit(2, 4+i) for i in range(5)]
        circuit = schedule(optimize(compile_ops(operations(qs, polished))), restarts=3)
        cirq.to_json(circuit, ROOT / 'decoder_5_r0to4_native.json')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
