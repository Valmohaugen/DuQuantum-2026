"""Bounded small-size feasibility fit for global-X-symmetric decoder cores.

No maintained solver changes. Fit phases may differ; only a separately
corrected, all-column native certificate can make a reusable decoder.
"""
import json
import math
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize, least_squares

ROOT = Path(__file__).parent


class Core:
    def __init__(self, n, cycles, insertions):
        self.n = n
        self.d = 1 << n
        self.columns = n//2+1
        # Each list is a matching; matchings are traversed in sequence.
        self.matchings = [[(0, 1)], [(1, 2)]] if n == 3 else [[(0, 1), (3, 4)], [(1, 2)], [(1, 3)]]
        self.gates = []
        self.count = 0
        self.target = np.zeros((self.d, self.columns), complex)
        self.initial = self.target.copy()
        for r in range(self.columns):
            self.initial[(1 << r)-1, r] = 1
            for b in range(self.d):
                if b.bit_count() == r:
                    self.target[b, r] = 1/math.sqrt(math.comb(n, r))
        for cycle in range(cycles):
            for matching in self.matchings:
                for axis in ('X', None, 'Y', None, 'X'):
                    for a, b in matching:
                        if axis is None:
                            self.add_cz(a, b)
                        else:
                            self.add_rotation(axis, (a,))
                            self.add_rotation(axis, (b,))
            if insertions == 'each' or cycle == cycles//2:
                a, b = self.matchings[cycle % len(self.matchings)][0]
                self.add_rotation('X', (a, b), fixed=math.pi/2)

    def add_cz(self, a, b):
        indices = np.arange(self.d)
        am, bm = 1 << (self.n-1-a), 1 << (self.n-1-b)
        phase = 1.-2*((indices & am != 0) & (indices & bm != 0))
        self.gates.append(dict(kind='CZ', qubits=[a, b], phase=phase))

    def add_rotation(self, axis, qubits, fixed=None):
        indices = np.arange(self.d)
        mask = sum(1 << (self.n-1-q) for q in qubits)
        perm = indices ^ mask
        phase = np.ones(self.d, complex)
        if axis == 'Y':
            assert len(qubits) == 1
            phase = 1j*(1.-2*((indices & mask) != 0))
        parameter = None
        if fixed is None:
            parameter = self.count
            self.count += 1
        self.gates.append(dict(kind=axis, qubits=list(qubits), perm=perm,
                               phase=phase, parameter=parameter, fixed=fixed))

    @staticmethod
    def pauli(gate, state):
        perm = gate['perm']
        return gate['phase'][perm, None]*state[perm]

    def apply(self, gate, state, x, inverse=False):
        if gate['kind'] == 'CZ':
            return gate['phase'][:, None]*state
        angle = gate['fixed'] if gate['parameter'] is None else x[gate['parameter']]
        if inverse:
            angle = -angle
        return math.cos(angle/2)*state-1j*math.sin(angle/2)*self.pauli(gate, state)

    def forward(self, x):
        history = [self.initial]
        for gate in self.gates:
            history.append(self.apply(gate, history[-1], x))
        return history

    def value_gradient(self, x):
        history = self.forward(x)
        overlap = (self.target.conj()*history[-1]).sum(axis=0)
        phases = overlap/np.maximum(abs(overlap), 1e-30)
        residual = history[-1]-self.target*phases
        loss = float(np.vdot(residual, residual).real)
        adjoint = residual
        gradient = np.zeros(self.count)
        for index in range(len(self.gates)-1, -1, -1):
            gate = self.gates[index]
            if gate['kind'] != 'CZ' and gate['parameter'] is not None:
                deriv = -.5j*self.pauli(gate, history[index+1])
                gradient[gate['parameter']] = 2*np.vdot(adjoint, deriv).real
            adjoint = self.apply(gate, adjoint, x, inverse=True)
        return loss, gradient

    def residual_jacobian(self, z):
        x, phases = z[:self.count], z[self.count:]
        history = self.forward(x)
        residual = history[-1]-self.target*np.exp(1j*phases)
        jac = np.zeros((self.d*self.columns, len(z)), complex)
        suffix = np.eye(self.d, dtype=complex)
        for index in range(len(self.gates)-1, -1, -1):
            gate = self.gates[index]
            if gate['kind'] == 'CZ':
                suffix *= gate['phase'][None, :]
                continue
            if gate['parameter'] is not None:
                deriv = suffix@(-.5j*self.pauli(gate, history[index+1]))
                jac[:, gate['parameter']] = deriv.ravel()
            angle = gate['fixed'] if gate['parameter'] is None else x[gate['parameter']]
            suffix = (math.cos(angle/2)*suffix
                      -1j*math.sin(angle/2)*suffix[:, gate['perm']]*gate['phase'][None, :])
        for r in range(self.columns):
            col = np.zeros_like(self.target)
            col[:, r] = -1j*self.target[:, r]*np.exp(1j*phases[r])
            jac[:, self.count+r] = col.ravel()
        return np.r_[residual.real.ravel(), residual.imag.ravel()], np.vstack([jac.real, jac.imag])

    def specification(self):
        return [{k: v for k, v in g.items() if k not in ('perm', 'phase')} for g in self.gates]


def check():
    rows = []
    rng = np.random.default_rng(90251)
    for n in (3, 5):
        core = Core(n, 1, 'each')
        x = rng.normal(size=core.count)
        loss, gradient = core.value_gradient(x)
        epsilon = 1e-6
        finite = []
        for j in range(core.count):
            shift = np.zeros(core.count)
            shift[j] = epsilon
            finite.append((core.value_gradient(x+shift)[0]-core.value_gradient(x-shift)[0])/(2*epsilon))
        grad_error = float(np.max(abs(gradient-finite)))
        z = np.r_[x, rng.normal(size=core.columns)]
        residual, jac = core.residual_jacobian(z)
        direction = rng.normal(size=len(z))
        finite_jac = (core.residual_jacobian(z+epsilon*direction)[0]-core.residual_jacobian(z-epsilon*direction)[0])/(2*epsilon)
        jac_error = float(np.max(abs(jac@direction-finite_jac)))
        # Compare full circuit matrix and F-conjugate, not just the targets.
        unitary = np.eye(core.d, dtype=complex)
        for gate in core.gates:
            unitary = core.apply(gate, unitary, x)
        symmetry_error = float(np.max(abs(unitary-unitary[::-1, ::-1])))
        assert max(grad_error, jac_error) < 1e-7
        assert symmetry_error < 1e-13
        rows.append(dict(n=n, gradient_error=grad_error, jacobian_direction_error=jac_error,
                         global_X_commutator_error=symmetry_error))
    (ROOT/'derivative_checks.json').write_text(json.dumps(rows, indent=2)+'\n')
    return rows


class Deadline(Exception):
    pass


def main():
    checks = check()
    start = time.monotonic()
    report = dict(status='running bounded feasibility pilot', derivative_checks=checks, trials=[])
    configurations = [(3, 1, 'each'), (3, 2, 'each'), (5, 2, 'each'), (5, 3, 'each')]
    for n, cycles, insertions in configurations:
        for seed in (0, 1):
            if time.monotonic()-start > 180:
                break
            core = Core(n, cycles, insertions)
            tick = time.monotonic()
            stop = min(start+180, tick+20)
            x = np.random.default_rng([90252, n, cycles, seed]).uniform(-math.pi, math.pi, core.count)
            best = [float('inf'), x.copy()]
            evaluations = [0]

            def objective(x):
                if time.monotonic() > stop:
                    raise Deadline()
                loss, gradient = core.value_gradient(x)
                evaluations[0] += 1
                if loss < best[0]:
                    best[:] = [loss, x.copy()]
                return loss, gradient

            termination = 'optimizer returned'
            try:
                result = minimize(objective, x, jac=True, method='L-BFGS-B',
                                  options=dict(maxiter=600, gtol=1e-12, ftol=1e-15, maxls=30))
                termination = str(result.message)
            except Deadline:
                termination = 'trial deadline'
            x = best[1]
            if best[0] < 1e-8 and time.monotonic()+1 < stop:
                output = core.forward(x)[-1]
                phases = np.angle((core.target.conj()*output).sum(axis=0))
                cached = [None, None]

                def both(z):
                    if time.monotonic() > stop:
                        raise Deadline()
                    if cached[0] is None or not np.array_equal(cached[0], z):
                        cached[:] = [z.copy(), core.residual_jacobian(z)]
                    return cached[1]

                try:
                    polished = least_squares(lambda z: both(z)[0], np.r_[x, phases],
                        jac=lambda z: both(z)[1], gtol=1e-13, xtol=1e-13, ftol=1e-13, max_nfev=30)
                    x = polished.x[:core.count]
                    termination += '; phase-aware least-squares polish'
                except Deadline:
                    termination += '; polish deadline'
            output = core.forward(x)[-1]
            overlap = (core.target.conj()*output).sum(axis=0)
            errors = np.linalg.norm(output-core.target*overlap/abs(overlap), axis=0)
            row = dict(n=n, cycles=cycles, insertions=insertions, seed=seed, angles=x.tolist(),
                       column_phases=np.angle(overlap).tolist(), column_errors=errors.tolist(),
                       max_phase_aligned_error=float(max(errors)), seconds=time.monotonic()-tick,
                       evaluations=evaluations[0], termination=termination,
                       core_CZ=sum(g['kind'] == 'CZ' or len(g['qubits']) == 2 and g['kind'] == 'X' for g in core.gates),
                       gates=core.specification(), status='requires all-column native composition certificate')
            report['trials'].append(row)
            (ROOT/'pilot_results.json').write_text(json.dumps(report, indent=2)+'\n')
            print(n, cycles, seed, row['max_phase_aligned_error'], round(row['seconds'], 3), termination, flush=True)
    report['status'] = 'bounded pilot complete; no native decoder claim'
    report['elapsed_seconds'] = time.monotonic()-start
    (ROOT/'pilot_results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
