"""Exact balanced-state objective from two small core simulations.

The cores may be arbitrary real Ry/CZ circuits. No global-X constraint or
individual unary-to-Dicke column mapping is imposed. This is not a fit.
"""
import json
import math
import os
from pathlib import Path

import numpy as np
from . import peer_synth_snapshot as synth


class PairedCore:
    def __init__(self, half_size, left_edges, right_edges):
        if half_size % 2 != 1:
            raise ValueError('This folded encoding currently covers odd half sizes')
        self.n = half_size
        self.left_edges, self.right_edges = left_edges, right_edges
        self.columns = half_size+1
        self.left_count = synth.n_params(half_size, left_edges)
        self.right_count = synth.n_params(half_size, right_edges)
        self.targets = np.array([synth.dicke(half_size, r) for r in range(self.columns)])
        basis, weights = [], []
        norm = math.sqrt(math.comb(2*half_size, half_size))
        for s in range(half_size//2+1):
            for branch in (0, 1):
                basis.append(((1 << s)-1) ^ (((1 << half_size)-1) if branch else 0))
                weights.append(math.comb(half_size, s)/norm)
        self.inputs = np.eye(1 << half_size)[basis]
        self.weights = np.array(weights)
        self.target_weights = np.array([math.comb(half_size, r)/norm for r in range(self.columns)])
        self.partner = np.arange(self.columns) ^ 1

    def outputs(self, x):
        left = synth.run(self.n, self.left_edges, x[None, :self.left_count], self.inputs)[0]
        right = synth.run(self.n, self.right_edges, x[None, self.left_count:], self.inputs)[0]
        return left, right

    def overlap_gradient(self, x):
        left, right = self.outputs(x)
        a, b = self.targets@left.T, self.targets@right.T
        weights = self.target_weights[:, None]*self.weights[None, :]
        left_coefficients = weights*b[::-1, self.partner]
        right_coefficients = weights*a[::-1, self.partner]
        overlap = float(np.sum(a*left_coefficients))
        # fid_grad returns a mean over columns, so compensate by R. Target
        # vectors may be unnormalized: the overlap backend is linear in them.
        left_targets = self.columns*(left_coefficients.T@self.targets)
        right_targets = self.columns*(right_coefficients.T@self.targets)
        fl, gl = synth.fid_grad(self.n, self.left_edges, x[None, :self.left_count], (self.inputs, left_targets))
        fr, gr = synth.fid_grad(self.n, self.right_edges, x[None, self.left_count:], (self.inputs, right_targets))
        assert abs(fl[0]-overlap) < 1e-11 and abs(fr[0]-overlap) < 1e-11
        return overlap, np.r_[gl[0], gr[0]]

    def loss_gradient(self, x):
        overlap, derivative = self.overlap_gradient(x)
        return 1-overlap**2, -2*overlap*derivative


def check():
    assert os.environ.get('SYNTH_KERNEL') == '0' and synth._kernel is None
    rows = []
    for n in (3, 5, 7):
        edges = [(i, i+1) for i in range(n-1)]*2
        objective = PairedCore(n, edges, list(reversed(edges)))
        rng = np.random.default_rng([90257, n])
        x = rng.normal(size=objective.left_count+objective.right_count)
        overlap, gradient = objective.overlap_gradient(x)
        left, right = objective.outputs(x)
        full = sum((w*np.kron(left[j], right[objective.partner[j]])
                    for j, w in enumerate(objective.weights)), start=np.zeros(1 << (2*n)))
        target = synth.dicke(2*n, n)
        direct = float(np.dot(target, full))
        norm_error = abs(float(np.linalg.norm(full))-1)
        overlap_error = abs(overlap-direct)
        direction = rng.normal(size=len(x))
        epsilon = 1e-6
        finite = (objective.overlap_gradient(x+epsilon*direction)[0]
                  -objective.overlap_gradient(x-epsilon*direction)[0])/(2*epsilon)
        derivative_error = abs(finite-float(np.dot(gradient, direction)))
        assert norm_error < 1e-12 and overlap_error < 1e-12 and derivative_error < 1e-7
        rows.append(dict(half_size=n, total_qubits=2*n, norm_error=norm_error,
                         direct_state_overlap_error=overlap_error,
                         derivative_direction_error=derivative_error))
    result = dict(status='compressed paired-core objective and gradient verified; no fit performed', checks=rows,
        target='Balanced D(2m,m), odd half size m; folded root with complementary branch partners.',
        advantage='Each core is simulated on m qubits with m+1 input columns. The overlap equals the full2m-qubit target overlap, including leakage; no inverse-mean or fidelity proxy is used.',
        freedom='The cores need not commute with globalX or map each label to an individual Dicke state. The joint objective retains correlated phases and rotations within degenerate Schmidt pairs.',
        acceptance='Any fit must still pass an independent full-state native/device check after composing the routed root and both cores. This helper alone provides no preparation circuit or score.',
        next_action='Construct an exact folded-input warm start from existing full-count decoders and inverse folds, then compare a bounded joint pruning pilot to strict independent-column fitting. Do not restart the failed symmetric ansatz.')
    Path(__file__).with_name('paired_core_checks.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    check()
