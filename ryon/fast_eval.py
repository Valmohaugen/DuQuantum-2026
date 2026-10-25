"""Fast noisy evaluation: the same noise model as test_dicke.py, simulated with a plain numpy
density matrix instead of cirq.DensityMatrixSimulator (much faster, so many seeds fit).

Scores with test_dicke.expected_score (the shot-noise-free E[score]); also prints the revised
judging metric, 1 / mean(Z + X) over the cases. The detuning draws are
seeded per (seed, N, n), so two variants of a solution see the same noise realisations.

Usage:
  python fast_eval.py                         # toby_sol, N=2..8, seeds 0..2
  python fast_eval.py --solution toby_sol --nmax 10 --seeds 0 1 2 3 4
"""
import argparse
import importlib
import math
import time

import cirq
import numpy as np

import judge
from test_dicke import DUR_1Q, DUR_CZ, T1, T2, _err, expected_score

_H = cirq.unitary(cirq.H)


class Rho:
    """Density matrix as a tensor with axes (row_0..row_{n-1}, col_0..col_{n-1})."""

    def __init__(self, n):
        self.n = n
        self.t = np.zeros((2,) * (2 * n), dtype=np.complex128)
        self.t[(0,) * (2 * n)] = 1

    def _ix(self, fixed):
        ix = [slice(None)] * (2 * self.n)
        for ax, v in fixed.items():
            ix[ax] = v
        return tuple(ix)

    def unitary1(self, i, u):
        t = np.moveaxis(np.tensordot(u, self.t, axes=([1], [i])), 0, i)
        self.t = np.moveaxis(np.tensordot(u.conj(), t, axes=([1], [self.n + i])), 0, self.n + i)

    def cz(self, i, j):
        for a, b in ((i, j), (self.n + i, self.n + j)):
            self.t[self._ix({a: 1, b: 1})] *= -1

    def depol(self, qs, p):
        #(1 - 4^k p / (4^k - 1)) rho + (4^k p / (4^k - 1)) I/2^k (x) tr_qs(rho)
        d = 4 ** len(qs)
        lam = d * p / (d - 1)
        diag = [dict(zip([*qs, *(self.n + q for q in qs)], bits + bits))
                for bits in [tuple(int(b) for b in format(x, f"0{len(qs)}b")) for x in range(2 ** len(qs))]]
        tr = sum(self.t[self._ix(f)] for f in diag) / 2 ** len(qs)
        self.t *= 1 - lam
        for f in diag:
            self.t[self._ix(f)] += lam * tr

    def idle(self, i, g_ad, g_pd, phi):
        r, c = i, self.n + i
        p11 = self.t[self._ix({r: 1, c: 1})]
        self.t[self._ix({r: 0, c: 0})] += g_ad * p11
        p11 *= 1 - g_ad
        off = math.sqrt((1 - g_ad) * (1 - g_pd))
        self.t[self._ix({r: 0, c: 1})] *= off * np.exp(-1j * phi)
        self.t[self._ix({r: 1, c: 0})] *= off * np.exp(1j * phi)

    def probs(self):
        d = 2 ** self.n
        return np.clip(np.real(np.diag(self.t.reshape(d, d))), 0, None)


def run_noisy(rho, moments, index, cz_err, sq_err, det):
    t_phi = 1 / (1 / T2 - 1 / (2 * T1))
    for moment in moments:
        dur = DUR_CZ if any(len(op.qubits) == 2 for op in moment) else DUR_1Q
        for op in moment:
            if len(op.qubits) == 2:
                rho.cz(index[op.qubits[0]], index[op.qubits[1]])
            else:
                rho.unitary1(index[op.qubits[0]], cirq.unitary(op))
        for op in moment:
            if len(op.qubits) == 2:
                rho.depol([index[q] for q in op.qubits], _err(cz_err, *op.qubits))
            else:
                rho.depol([index[op.qubits[0]]], _err(sq_err, op.qubits[0]))
        g_ad = 1 - math.exp(-dur / T1)
        g_pd = 1 - math.exp(-2 * dur / t_phi)
        for q, i in index.items():
            rho.idle(i, g_ad, g_pd, 2 * math.pi * det[q] * dur)


def readout(p, order, zero_err, one_err):
    n = len(order)
    t = p.reshape([2] * n)
    for i, q in enumerate(order):
        e0, e1 = zero_err[q][0], one_err[q][0]
        m = np.array([[1 - e0, e1], [e0, 1 - e1]])
        t = np.moveaxis(np.tensordot(m, t, axes=([1], [i])), 0, i)
    t = t.reshape(-1)
    return t / t.sum()


def noisy_probs(circuit, qubits, cal, rng, detuning_khz=7.5, realisations=4):
    """(pz, px) after readout error, matching test_dicke.noisy_bitstrings."""
    cz_err, sq_err, zero_err, one_err = cal
    order = sorted(qubits)
    extra = sorted(circuit.all_qubits() - set(qubits))
    full = order + extra
    index = {q: i for i, q in enumerate(full)}
    n = len(order)
    hmoment = [cirq.Moment(cirq.MatrixGate(_H).on(q) for q in order)]
    pz, px = np.zeros(2 ** n), np.zeros(2 ** n)
    reals = realisations if detuning_khz else 1
    for _ in range(reals):
        det = {q: rng.normal(0, detuning_khz * 1e3) for q in full} if detuning_khz else {q: 0.0 for q in full}
        rho = Rho(len(full))
        run_noisy(rho, list(circuit), index, cz_err, sq_err, det)
        p = rho.probs()
        pz += (p.reshape(2 ** n, -1).sum(axis=1) if extra else p) / reals
        run_noisy(rho, hmoment, index, cz_err, sq_err, det)
        p = rho.probs()
        px += (p.reshape(2 ** n, -1).sum(axis=1) if extra else p) / reals
    return readout(pz, order, zero_err, one_err), readout(px, order, zero_err, one_err)


def score_case(build, N, n, cal, seed, shots=10_000, realisations=4, check=True):
    circuit, qubits = build(N, n, cal)
    if check:
        judge.test_circuit(circuit, n, qubits)
    rng = np.random.default_rng([seed, N, n])
    pz, px = noisy_probs(circuit, qubits, cal, rng, realisations=realisations)
    f, zf, zb, x, es = expected_score(pz, px, N, n, N, shots)
    cz = sum(1 for op in circuit.all_operations() if len(op.qubits) == 2)
    return dict(N=N, n=n, cz=cz, moments=len(circuit), f=f, zf=zf, zb=zb, x=x, es=es)


def cases(nmin, nmax):
    return [(N, n) for N in range(nmin, nmax + 1) for n in range(1, N // 2 + 1)]


def evaluate(build, case_list, seeds, verbose=True, **kw):
    """Mean expected score per case over calibration seeds; returns (total, rows)."""
    cals = {s: judge.fake_calibration(s) for s in seeds}
    rows = []
    for N, n in case_list:
        rs = [score_case(build, N, n, cals[s], s, **kw) for s in seeds]
        row = {k: float(np.mean([r[k] for r in rs])) for k in rs[0]}
        rows.append(row)
        if verbose:
            print(f"{N:>3} {n:>2} cz {row['cz']:5.1f} mom {row['moments']:6.1f}  f {row['f']:.4f}"
                  f"  Zf {row['zf']:.3f} Zb {row['zb']:.3f} X {row['x']:.3f}  E[s] {row['es']:.4f}", flush=True)
    total = sum(r["es"] for r in rows)
    if verbose:
        print(f"total {total:.4f}")
        #revised judging: 1 / mean over cases of (Z + X), i.e. the harmonic mean of the per-case scores
        print(f"harmonic 1/mean(Z+X) {1 / np.mean([r['zf'] + r['zb'] + r['x'] for r in rows]):.4f}")
    return total, rows


def module_builder(name, **kwargs):
    mod = importlib.import_module(name)
    return lambda N, n, cal: mod.create_dicke_state(N, n, *cal, **kwargs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", default="toby_sol")
    ap.add_argument("--nmin", type=int, default=2)
    ap.add_argument("--nmax", type=int, default=8)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--realisations", type=int, default=4)
    args = ap.parse_args()
    t = time.time()
    evaluate(module_builder(args.solution), cases(args.nmin, args.nmax), args.seeds,
             realisations=args.realisations)
    print(f"[{time.time() - t:.0f}s]")
