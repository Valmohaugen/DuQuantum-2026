"""Offline synthesis of short CZ + Ry circuits for Dicke states (numpy + scipy only).

A circuit is an initial Ry on every qubit, then a list of CZ edges, each followed by an Ry on
both of its qubits. All gates are real, so the state stays real and the Dicke target is
reachable. Angles are fitted by maximising <D|psi> with exact (adjoint) gradients, from many
random starts at once.
"""
import math

import numpy as np
from scipy.optimize import minimize


def dicke(N, k):
    psi = np.zeros(2 ** N)
    for i in range(2 ** N):
        if bin(i).count("1") == k:
            psi[i] = 1
    return psi / np.linalg.norm(psi)


def _ry(psi, q, c, s):
    #psi: (B, 2, ..., 2); qubit q is axis q + 1 (big-endian, qubit 0 = most significant)
    a = np.take(psi, 0, axis=q + 1)
    b = np.take(psi, 1, axis=q + 1)
    sh = (-1,) + (1,) * (a.ndim - 1)
    c, s = c.reshape(sh), s.reshape(sh)
    return np.stack([c * a - s * b, s * a + c * b], axis=q + 1)


def _gen(psi, q):
    a = np.take(psi, 0, axis=q + 1)
    b = np.take(psi, 1, axis=q + 1)
    return np.stack([-b, a], axis=q + 1)


def _cz(psi, i, j):
    ix = [slice(None)] * psi.ndim
    ix[i + 1] = ix[j + 1] = 1
    psi = psi.copy()
    psi[tuple(ix)] *= -1
    return psi


def gate_list(N, edges):
    #(kind, data) in order; "ry" carries its qubit, params are consumed in order
    gates = [("ry", q) for q in range(N)]
    for a, b in edges:
        gates += [("cz", (a, b)), ("ry", a), ("ry", b)]
    return gates


def run(N, edges, theta):
    gates = gate_list(N, edges)
    B = theta.shape[0]
    psi = np.zeros((B,) + (2,) * N)
    psi[(slice(None),) + (0,) * N] = 1
    p = 0
    for kind, d in gates:
        if kind == "ry":
            psi = _ry(psi, d, np.cos(theta[:, p] / 2), np.sin(theta[:, p] / 2))
            p += 1
        else:
            psi = _cz(psi, *d)
    return psi.reshape(B, -1)


def fid_grad(N, edges, theta, target):
    """Overlap f = <target|psi> per batch row and df/dtheta."""
    gates = gate_list(N, edges)
    B, P = theta.shape
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    psi = np.zeros((B,) + (2,) * N)
    psi[(slice(None),) + (0,) * N] = 1
    p = 0
    for kind, d in gates:
        if kind == "ry":
            psi = _ry(psi, d, c[:, p], s[:, p])
            p += 1
        else:
            psi = _cz(psi, *d)
    lam = np.broadcast_to(target.reshape((1,) + (2,) * N), psi.shape).copy()
    f = np.sum((psi * lam).reshape(B, -1), axis=1)
    grad = np.zeros_like(theta)
    for kind, d in reversed(gates):
        if kind == "ry":
            p -= 1
            grad[:, p] = 0.5 * np.sum((lam * _gen(psi, d)).reshape(B, -1), axis=1)
            psi = _ry(psi, d, c[:, p], -s[:, p])
            lam = _ry(lam, d, c[:, p], -s[:, p])
        else:
            psi, lam = _cz(psi, *d), _cz(lam, *d)
    return f, grad


def n_params(N, edges):
    return N + 2 * len(edges)


def fit(N, k, edges, restarts=64, iters=400, seed=0, tol=1e-10, target=None):
    """Best (infidelity, angles) over random restarts: batched Adam, then L-BFGS polish."""
    target = dicke(N, k) if target is None else target
    rng = np.random.default_rng(seed)
    P = n_params(N, edges)
    th = rng.uniform(-math.pi, math.pi, (restarts, P))
    m, v = np.zeros_like(th), np.zeros_like(th)
    lr, b1, b2 = 0.1, 0.9, 0.999
    for t in range(1, iters + 1):
        f, g = fid_grad(N, edges, th, target)
        g = -2 * f[:, None] * g  #gradient of 1 - f^2
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * g * g
        th -= lr * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + 1e-12)
    f, _ = fid_grad(N, edges, th, target)
    order = np.argsort(-(f ** 2))
    best = (1.0, None)
    for i in order[:4]:
        def loss(x):
            ff, gg = fid_grad(N, edges, x[None], target)
            return 1 - ff[0] ** 2, -2 * ff[0] * gg[0]
        r = minimize(loss, th[i], jac=True, method="L-BFGS-B", options=dict(maxiter=3000, gtol=1e-14, ftol=1e-16))
        if r.fun < best[0]:
            best = (float(r.fun), r.x)
        if best[0] < tol:
            break
    return best


def layers(edges):
    """Greedy CZ depth of an edge sequence (each CZ goes after the last one on its qubits)."""
    t = {}
    depth = 0
    for a, b in edges:
        d = max(t.get(a, 0), t.get(b, 0)) + 1
        t[a] = t[b] = d
        depth = max(depth, d)
    return depth


def polish(N, k, edges, x0, target=None):
    target = dicke(N, k) if target is None else target

    def loss(x):
        ff, gg = fid_grad(N, edges, x[None], target)
        return 1 - ff[0] ** 2, -2 * ff[0] * gg[0]
    r = minimize(loss, x0, jac=True, method="L-BFGS-B", options=dict(maxiter=3000, gtol=1e-14, ftol=1e-16))
    return float(r.fun), r.x


def prune(N, k, edges, theta, rng, tol=1e-10, restarts=16, iters=300):
    """Drop CZs one at a time (warm start, then random restarts) while an exact fit survives."""
    edges = list(edges)
    improved = True
    while improved:
        improved = False
        for i in rng.permutation(len(edges)):
            trial = edges[:i] + edges[i + 1:]
            p = N + 2 * i
            x0 = np.concatenate([theta[:p], theta[p + 2:]])
            inf, x = polish(N, k, trial, x0)
            if inf > tol:
                inf, x = fit(N, k, trial, restarts=restarts, iters=iters, seed=int(rng.integers(1 << 30)), tol=tol)
            if inf < tol:
                edges, theta, improved = trial, x, True
                break
    return edges, theta
