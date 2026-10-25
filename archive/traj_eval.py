"""Trajectory version of fast_eval for large N: the same noise model, unravelled into state-vector
trajectories (2^N memory instead of 4^N), so N up to about 20 fits.

Per moment: the gates, then a random Pauli on each gate with its calibrated Pauli error (the
average of these is fast_eval's depolarizing channel), then on every qubit an amplitude-damping
jump or no-jump step (T1), a random Z flip with the matching pure-dephasing probability (T2), and
the quasi-static detuning phase. Readout error is applied to the averaged distribution, as in
fast_eval. The squared terms of the score are corrected for trajectory sampling variance, so
they are unbiased. f, the Z floor and X agree with fast_eval within a few 1e-3 at 300 trajectories.
The Z bias term is multiplied by the shot count (10,000), so its estimate stays noisy (about
+-0.05 at 300 trajectories) and can go negative; "no-Zb" (1 / (Z floor + X)) is the steadier
number for A/B comparisons at large N, where fast_eval can't run.

Usage:
  python traj_eval.py --cases 9:4,12:6 --seeds 0 1 --traj 40
  python traj_eval.py --solution toby_sol --nmin 13 --nmax 16 --seeds 0 --traj 20
"""
import argparse
import importlib
import math
import time

import cirq
import numpy as np

import fast_eval as fe
import judge
from test_dicke import DUR_1Q, DUR_CZ, T1, T2, _err

_PAULI = [np.eye(2), cirq.unitary(cirq.X), cirq.unitary(cirq.Y), cirq.unitary(cirq.Z)]


def _apply1(psi, q, u):
    return np.moveaxis(np.tensordot(u, psi, axes=([1], [q])), 0, q)


def _flip_sign(psi, i, j=None):
    ix = [slice(None)] * psi.ndim
    ix[i] = 1
    if j is not None:
        ix[j] = 1
    psi[tuple(ix)] *= -1


def run_trajectory(psi, moments, index, cz_err, sq_err, det, rng):
    t_phi = 1 / (1 / T2 - 1 / (2 * T1))
    n = psi.ndim
    for moment in moments:
        dur = DUR_CZ if any(len(op.qubits) == 2 for op in moment) else DUR_1Q
        for op in moment:
            qs = [index[q] for q in op.qubits]
            if len(qs) == 2:
                _flip_sign(psi, *qs)
            else:
                psi = _apply1(psi, qs[0], cirq.unitary(op))
        for op in moment:
            qs = [index[q] for q in op.qubits]
            p = _err(cz_err, *op.qubits) if len(qs) == 2 else _err(sq_err, op.qubits[0])
            if rng.random() < p:
                #uniform over the non-identity Paulis on the gate's qubits
                while True:
                    paulis = rng.integers(4, size=len(qs))
                    if paulis.any():
                        break
                for q, w in zip(qs, paulis):
                    if w:
                        psi = _apply1(psi, q, _PAULI[w])
        g_ad = 1 - math.exp(-dur / T1)
        p_z = (1 - math.sqrt(math.exp(-2 * dur / t_phi))) / 2
        for q in range(n):
            p1 = float(np.sum(np.abs(np.take(psi, 1, axis=q)) ** 2))
            if rng.random() < g_ad * p1:
                psi = _apply1(psi, q, np.array([[0, 1], [0, 0]]))
            else:
                psi = _apply1(psi, q, np.diag([1, math.sqrt(1 - g_ad)]))
            psi /= np.linalg.norm(psi)
            if rng.random() < p_z:
                _flip_sign(psi, q)
            phi = 2 * math.pi * det[q] * dur
            psi = _apply1(psi, q, np.diag([np.exp(1j * phi / 2), np.exp(-1j * phi / 2)]))
    return psi


def traj_stats(circuit, qubits, cal, rng, traj=40, detuning_khz=7.5):
    """Per-trajectory statistics after readout error: running sum and sum of squares of the Z
    distribution, and the X-basis Hamming-weight distribution of every trajectory."""
    cz_err, sq_err, zero_err, one_err = cal
    order = sorted(qubits)
    extra = sorted(circuit.all_qubits() - set(qubits))
    full = order + extra
    index = {q: i for i, q in enumerate(full)}
    n, m = len(order), len(full)
    hmoment = [cirq.Moment(cirq.MatrixGate(cirq.unitary(cirq.H)).on(q) for q in order)]
    moments = list(circuit)
    weights = np.array([bin(i).count("1") for i in range(2 ** n)])
    s1, s2, pws = np.zeros(2 ** n), np.zeros(2 ** n), []
    for _ in range(traj):
        det = [rng.normal(0, detuning_khz * 1e3) for _ in range(m)]
        psi = np.zeros((2,) * m, dtype=np.complex128)
        psi[(0,) * m] = 1
        psi = run_trajectory(psi, moments, index, cz_err, sq_err, det, rng)
        p = np.abs(psi.reshape(-1)) ** 2
        pz = fe.readout(p.reshape(2 ** n, -1).sum(axis=1) if extra else p, order, zero_err, one_err)
        s1 += pz
        s2 += pz ** 2
        psi = run_trajectory(psi, hmoment, index, cz_err, sq_err, det, rng)
        p = np.abs(psi.reshape(-1)) ** 2
        px = fe.readout(p.reshape(2 ** n, -1).sum(axis=1) if extra else p, order, zero_err, one_err)
        pws.append(np.bincount(weights, weights=px, minlength=n + 1))
    return s1, s2, np.array(pws)


def unbiased_score(s1, s2, pws, N, n, k_max, shots):
    """expected_score from trajectory averages, minus the sampling-variance bias of its squares."""
    T = len(pws)
    C = math.comb(N, n)
    weights = np.array([bin(i).count("1") for i in range(2 ** N)])
    mean = s1 / T
    var = np.maximum(s2 / T - mean ** 2, 0) * T / max(T - 1, 1) / T  #variance of the mean
    sub, vsub = mean[weights == n], var[weights == n]
    f = sub.sum()
    q, vq = sub / f, vsub / f ** 2
    z_floor = (1 - f * (np.sum(q ** 2) - np.sum(vq))) / f
    z_bias = shots * (np.sum((q - 1 / C) ** 2) - np.sum(vq))
    comb = lambda a, b: math.comb(a, b) if 0 <= b <= a else 0
    x = 0.0
    for k in range(1, k_max + 1):
        kraw = np.array([sum((-1) ** j * comb(w, j) * comb(N - w, k - j) for j in range(k + 1)) for w in range(N + 1)])
        ms = pws @ kraw / math.comb(N, k)
        m, vm = ms.mean(), ms.var(ddof=1) / T if T > 1 else 0.0
        e = comb(k, k // 2) * comb(N - k, n - k // 2) / C if k % 2 == 0 else 0.0
        x += ((e - m) ** 2 - vm) / e ** 2 if e else (e - m) ** 2 - vm
    return f, z_floor, z_bias, x, 1 / (z_floor + z_bias + x)


def score_case(build, N, n, cal, seed, traj=40, shots=10_000, k_max=None):
    circuit, qubits = build(N, n, cal)
    rng = np.random.default_rng([seed, N, n, 7])
    s1, s2, pws = traj_stats(circuit, qubits, cal, rng, traj)
    f, zf, zb, x, es = unbiased_score(s1, s2, pws, N, n, N if k_max is None else k_max, shots)
    cz = sum(1 for op in circuit.all_operations() if len(op.qubits) == 2)
    return dict(N=N, n=n, cz=cz, moments=len(circuit), f=f, zf=zf, zb=zb, x=x, es=es, es0=1 / (zf + x))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--solution", default="toby_sol")
    ap.add_argument("--cases", default="", help="comma list N:n; overrides --nmin/--nmax")
    ap.add_argument("--nmin", type=int, default=9)
    ap.add_argument("--nmax", type=int, default=12)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0])
    ap.add_argument("--traj", type=int, default=40)
    ap.add_argument("--kmax", type=int, default=None, help="max correlator size (default N)")
    args = ap.parse_args()
    mod = importlib.import_module(args.solution)
    build = lambda N, n, cal: mod.create_dicke_state(N, n, *cal)
    cases = ([tuple(map(int, c.split(":"))) for c in args.cases.split(",")] if args.cases
             else fe.cases(args.nmin, args.nmax))
    t0, total, total0 = time.time(), 0.0, 0.0
    for N, n in cases:
        rs = [score_case(build, N, n, judge.fake_calibration(s), s, args.traj, k_max=args.kmax) for s in args.seeds]
        row = {k: float(np.mean([r[k] for r in rs])) for k in rs[0]}
        total += row["es"]
        total0 += row["es0"]
        print(f"{N:>3} {n:>2} cz {row['cz']:5.1f} mom {row['moments']:6.1f}  f {row['f']:.4f}"
              f"  Zf {row['zf']:.3f} Zb {row['zb']:+.3f} X {row['x']:.3f}  E[s] {row['es']:.4f}  no-Zb {row['es0']:.4f}",
              flush=True)
    print(f"total {total:.4f}  no-Zb {total0:.4f}  [{time.time() - t0:.0f}s]")
