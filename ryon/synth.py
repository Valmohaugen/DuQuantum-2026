"""Offline synthesis of short CZ + Ry circuits for Dicke states (numpy + scipy only).

A circuit is an initial Ry on every qubit, then a list of CZ edges, each followed by an Ry on
both of its qubits. All gates are real, so the state stays real and the Dicke target is
reachable. Angles are fitted by maximising the overlap with exact (adjoint) gradients, from many
random starts at once.

A target is either one state (prepared from |0...0>) or a pair (inputs, outputs) of (R, 2^N)
arrays: the circuit must map every input to its output with one common sign. The pair form fits
a block that only has to be right on the inputs that can occur, like one split-and-cyclic-shift
step of the line construction (see scs_target).
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


def basis(N, bits):
    #big-endian: bits[0] is qubit 0, the most significant
    psi = np.zeros(2 ** N)
    psi[int("".join(map(str, bits)), 2)] = 1
    return psi


def scs_target(m, k, r_min=0, r_max=None):
    """Inputs and outputs of one split-and-cyclic-shift step on its window of k + 1 qubits.

    The window is positions m-k-1 .. m-1 of the line; it holds |0^(k+1-r) 1^r> for every
    excitation count r that can occur. The step keeps the last qubit at 1 with amplitude
    sqrt(r/m), otherwise it moves one excitation to the first zero: |0^(k-r) 1^r 0>.
    """
    r_max = k if r_max is None else r_max
    W = k + 1
    ins, outs = [], []
    for r in range(r_min, r_max + 1):
        x = basis(W, [0] * (W - r) + [1] * r)
        if r == 0:
            y = x
        else:
            y = math.sqrt(r / m) * x + math.sqrt((m - r) / m) * basis(W, [0] * (W - r - 1) + [1] * r + [0])
        ins.append(x)
        outs.append(y)
    return np.array(ins), np.array(outs)


def _problem(N, k, target):
    if target is None:
        target = dicke(N, k)
    if isinstance(target, tuple):
        return np.asarray(target[0], float), np.asarray(target[1], float)
    return basis(N, [0] * N)[None], np.asarray(target, float)[None]


#states are (B, R, 2, ..., 2): batch of angle sets, then inputs; qubit q is axis q + 2
def _ry(psi, q, c, s):
    a = np.take(psi, 0, axis=q + 2)
    b = np.take(psi, 1, axis=q + 2)
    sh = (-1,) + (1,) * (a.ndim - 1)
    c, s = c.reshape(sh), s.reshape(sh)
    return np.stack([c * a - s * b, s * a + c * b], axis=q + 2)


def _gen(psi, q):
    a = np.take(psi, 0, axis=q + 2)
    b = np.take(psi, 1, axis=q + 2)
    return np.stack([-b, a], axis=q + 2)


def _cz(psi, i, j):
    ix = [slice(None)] * psi.ndim
    ix[i + 2] = ix[j + 2] = 1
    psi = psi.copy()
    psi[tuple(ix)] *= -1
    return psi


def gate_list(N, edges):
    #(kind, data) in order; "ry" carries its qubit, params are consumed in order
    gates = [("ry", q) for q in range(N)]
    for a, b in edges:
        gates += [("cz", (a, b)), ("ry", a), ("ry", b)]
    return gates


def _start(N, theta, ins):
    B, R = theta.shape[0], ins.shape[0]
    return np.broadcast_to(ins.reshape((1, R) + (2,) * N), (B, R) + (2,) * N).copy()


def run(N, edges, theta, inputs=None):
    ins = basis(N, [0] * N)[None] if inputs is None else np.asarray(inputs, float)
    psi = _start(N, theta, ins)
    p = 0
    for kind, d in gate_list(N, edges):
        if kind == "ry":
            psi = _ry(psi, d, np.cos(theta[:, p] / 2), np.sin(theta[:, p] / 2))
            p += 1
        else:
            psi = _cz(psi, *d)
    return psi.reshape(theta.shape[0], ins.shape[0], -1)


def fid_grad(N, edges, theta, target, k=None):
    """Mean overlap f = sum_r <out_r|U|in_r> / R per batch row, and df/dtheta."""
    ins, outs = _problem(N, k, target)
    R = ins.shape[0]
    gates = gate_list(N, edges)
    B, P = theta.shape
    c, s = np.cos(theta / 2), np.sin(theta / 2)
    psi = _start(N, theta, ins)
    p = 0
    for kind, d in gates:
        if kind == "ry":
            psi = _ry(psi, d, c[:, p], s[:, p])
            p += 1
        else:
            psi = _cz(psi, *d)
    lam = _start(N, theta, outs) / R
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


def polish(N, k, edges, x0, target=None, maxiter=3000):
    target = _problem(N, k, target)

    def loss(x):
        ff, gg = fid_grad(N, edges, x[None], target)
        return 1 - ff[0] ** 2, -2 * ff[0] * gg[0]
    r = minimize(loss, x0, jac=True, method="L-BFGS-B", options=dict(maxiter=maxiter, gtol=1e-14, ftol=1e-16))
    return float(r.fun), r.x


def fit(N, k, edges, restarts=64, iters=400, seed=0, tol=1e-10, target=None, x0=None, free=None):
    """Best (infidelity, angles) over random restarts: batched Adam, then L-BFGS polish.

    With x0, every restart starts from x0 and only the parameters in free are randomised.
    """
    target = _problem(N, k, target)
    rng = np.random.default_rng(seed)
    P = n_params(N, edges)
    th = rng.uniform(-math.pi, math.pi, (restarts, P))
    if x0 is not None:
        keep = np.ones(P, bool)
        keep[list(free)] = False
        th[:, keep] = np.asarray(x0)[keep]
    m, v = np.zeros_like(th), np.zeros_like(th)
    lr, b1, b2 = 0.1, 0.9, 0.999
    for t in range(1, iters + 1):
        f, g = fid_grad(N, edges, th, target)
        g = -2 * f[:, None] * g  #gradient of 1 - f^2
        m = b1 * m + (1 - b1) * g
        v = b2 * v + (1 - b2) * g * g
        th -= lr * (m / (1 - b1 ** t)) / (np.sqrt(v / (1 - b2 ** t)) + 1e-12)
    f, _ = fid_grad(N, edges, th, target)
    best = (1.0, None)
    for i in np.argsort(-(f ** 2))[:4]:
        inf, x = polish(N, k, edges, th[i], target)
        if inf < best[0]:
            best = (inf, x)
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


def prune(N, k, edges, theta, rng, tol=1e-10, restarts=16, iters=300, target=None, window=0, polish_iters=3000):
    """Drop CZs one at a time while an exact fit survives.

    Each try first polishes from the old angles. If that fails and restarts > 0, it refits with
    random restarts: all angles if window = 0, else only the angles of the CZs within window
    places of the removed one (the rest stay warm, which works far better on long circuits).
    polish_iters caps each warm polish; a few hundred is enough to tell on large isometries.
    """
    target = _problem(N, k, target)
    edges = list(edges)
    improved = True
    while improved:
        improved = False
        for i in rng.permutation(len(edges)):
            trial = edges[:i] + edges[i + 1:]
            p = N + 2 * i
            x0 = np.concatenate([theta[:p], theta[p + 2:]])
            inf, x = polish(N, k, trial, x0, target, polish_iters)
            if inf > tol and restarts:
                free = None
                if window:
                    lo, hi = max(0, i - window), min(len(trial), i + window)
                    qs = {q for e in trial[lo:hi] for q in e}
                    free = [N + 2 * j + h for j in range(lo, hi) for h in (0, 1)]
                    free += [q for q in qs if all(q not in e for e in trial[:lo])]
                inf, x = fit(N, k, trial, restarts=restarts, iters=iters, seed=int(rng.integers(1 << 30)),
                             tol=tol, target=target, x0=x0 if window else None, free=free)
            if inf < tol:
                edges, theta, improved = trial, x, True
                break
    return edges, theta


def from_ops(ops, qubits):
    """Rewrite a circuit of CZ and real single-qubit gates as (edges, theta, zset).

    Each 1q gate is Ry(t) or Ry(t) Z up to phase. The Z parts commute with CZ, so they are pushed
    to the end (flipping later Ry angles) and left as a final Z layer on zset. The circuit then
    equals Z_zset times the CZ + Ry ansatz with these angles.
    """
    idx = {q: i for i, q in enumerate(qubits)}
    N = len(qubits)
    acc, z = [0.0] * N, [0] * N
    slot = list(range(N))  #param index each qubit's next Ry goes to
    theta, edges = [0.0] * N, []
    for op in ops:
        qs = [idx[q] for q in op.qubits]
        if len(qs) == 2:
            for q in qs:
                theta[slot[q]] += acc[q]
                acc[q] = 0.0
            edges.append(tuple(qs))
            theta += [0.0, 0.0]
            slot[qs[0]], slot[qs[1]] = len(theta) - 2, len(theta) - 1
            continue
        u = np.asarray(__import__("cirq").unitary(op))
        u = u * np.exp(-1j * np.angle(u[np.unravel_index(np.argmax(abs(u)), u.shape)]))
        assert np.allclose(u.imag, 0, atol=1e-9), f"not a real gate: {op}"
        u = u.real
        b = int(np.linalg.det(u) < 0)
        r = u @ np.diag([1, -1]) if b else u  #r = Ry(t)
        t = 2 * math.atan2(r[1, 0], r[0, 0])
        q = qs[0]
        c = b ^ z[q]
        acc[q] += -t if c else t
        z[q] = c
    for q in range(N):
        theta[slot[q]] += acc[q]
    return edges, np.array(theta), [q for q in range(N) if z[q]]


def flip_signs(psi, N, zset):
    #apply Z on every qubit in zset to a state vector
    out = psi.copy()
    for i in range(2 ** N):
        if sum((i >> (N - 1 - q)) & 1 for q in zset) % 2:
            out[i] = -out[i]
    return out
