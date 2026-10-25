"""Test harness for the Dicke-state challenge.

For every (N, n) it:
  1. builds the circuit with create_dicke_state (timed against the 60 s limit),
  2. checks the challenge rules (gate set, allowed qubits/couplers, <= 1750 moments) and
     Willow device validation,
  3. checks the noiseless state with the notebook's (fixed) test_circuit,
  4. optionally runs a noisy density-matrix simulation of Willow and scores it with the
     notebook's own overall_score, 10,000 shots per basis.

Noise model (per moment): CZ -> 2-qubit depolarizing at the calibrated Pauli error;
PhasedXZ -> 1-qubit depolarizing; every qubit -> amplitude damping (T1) + pure dephasing
(T2) for the moment's duration (CZ 42 ns, single-qubit 25 ns); optional quasi-static
detuning (averaged over several random realisations) so dynamical decoupling has something
to refocus; asymmetric readout flips from zero_errors / one_errors.

Not modelled: leakage, ZZ crosstalk, coherent CZ phase errors, drift. Treat absolute scores
as optimistic and use the harness for *relative* comparisons.

Usage:
  python test_dicke.py                       # N=2..8 correctness + noisy scores
  python test_dicke.py --nmax 14 --noisy-nmax 6
  python test_dicke.py --compare-dd          # with vs without dynamical decoupling
  python test_dicke.py --bonus               # bonus-question score (moment counts)
  python test_dicke.py --solution minimal_dicke   # test another module with the same signature
"""
from __future__ import annotations

import argparse
import csv
import importlib
import inspect
import math
import time

import cirq
import numpy as np

import judge


def count_cz(circuit):
    return sum(1 for op in circuit.all_operations() if len(op.qubits) == 2)


T1, T2 = 68e-6, 89e-6  # Willow spec sheet / QEC paper medians
DUR_CZ, DUR_1Q = 42e-9, 25e-9  # Cirq willow_pink device spec


# ============================================================================ rule checks
def _err(d, a, b=None):
    if b is None:
        return d[a][0]
    return d[(a, b)][0] if (a, b) in d else d[(b, a)][0]


def check_rules(circuit, qubits, n_qubits, cz_err, sq_err):
    problems = []
    if len(circuit) > 1750:
        problems.append(f"{len(circuit)} moments > 1750")
    if len(qubits) != n_qubits:
        problems.append(f"returned {len(qubits)} qubits, expected {n_qubits}")
    if not set(qubits) <= circuit.all_qubits():
        problems.append("returned qubits not all in circuit")
    for op in circuit.all_operations():
        g = op.gate
        if isinstance(g, cirq.PhasedXZGate) or isinstance(g, cirq.ResetChannel):
            if op.qubits[0] not in sq_err:
                problems.append(f"1q gate on unusable qubit {op.qubits[0]}")
        elif g == cirq.CZ:
            a, b = op.qubits
            if (a, b) not in cz_err and (b, a) not in cz_err:
                problems.append(f"CZ on unlisted pair {a},{b}")
        else:
            problems.append(f"disallowed operation {op!r}")
        if cirq.is_measurement(op) or op.classical_controls:
            problems.append(f"measurement/classical control not allowed: {op!r}")
    try:
        judge.get_device().validate_circuit(circuit)
    except ValueError as e:
        problems.append(f"device validation: {e}")
    return problems


def check_readout_diagonals(circuit):
    """Bonus rule: a mid-circuit measurement must cover every device qubit on each
    anti-diagonal (row + col = const) it touches."""
    dev_qubits = judge.get_device().metadata.qubit_set
    diag = {}
    for q in dev_qubits:
        diag.setdefault(q.row + q.col, set()).add(q)
    problems = []
    for i, moment in enumerate(circuit):
        measured = {q for op in moment if cirq.is_measurement(op) for q in op.qubits}
        for s in {q.row + q.col for q in measured}:
            if not diag[s] <= measured:
                problems.append(f"moment {i}: partial measurement of diagonal {s}")
    return problems


# ============================================================================ noise model
class WillowNoise(cirq.NoiseModel):
    def __init__(self, cz_err, sq_err, detuning_hz=None):
        self.cz_err, self.sq_err = cz_err, sq_err
        self.detuning_hz = detuning_hz or {}

    def noisy_moment(self, moment, system_qubits):
        two_q = any(len(op.qubits) == 2 for op in moment)
        dur = DUR_CZ if two_q else DUR_1Q
        gate_noise = []
        for op in moment:
            if len(op.qubits) == 2:
                gate_noise.append(cirq.depolarize(_err(self.cz_err, *op.qubits), 2).on(*op.qubits))
            elif len(op.qubits) == 1 and not cirq.is_measurement(op):
                gate_noise.append(cirq.depolarize(_err(self.sq_err, op.qubits[0])).on(*op.qubits))
        gamma_ad = 1 - math.exp(-dur / T1)
        t_phi = 1 / (1 / T2 - 1 / (2 * T1))
        gamma_pd = 1 - math.exp(-2 * dur / t_phi)
        out = [moment]
        if gate_noise:
            out.append(cirq.Moment(gate_noise))
        out.append(cirq.Moment(cirq.amplitude_damp(gamma_ad).on(q) for q in system_qubits))
        out.append(cirq.Moment(cirq.phase_damp(gamma_pd).on(q) for q in system_qubits))
        det = [q for q in system_qubits if q in self.detuning_hz]
        if det:
            out.append(cirq.Moment(
                cirq.rz(2 * math.pi * self.detuning_hz[q] * dur).on(q) for q in det))
        return out


_H_PHXZ = cirq.PhasedXZGate.from_matrix(cirq.unitary(cirq.H))


def noisy_bitstrings(circuit, qubits, cal, shots, rng, detuning_khz=7.5, realisations=4):
    """Return (z_bits, x_bits) sampled from the noisy final state, with readout errors."""
    cz_err, sq_err, zero_err, one_err = cal
    order = sorted(qubits)
    extra = sorted(circuit.all_qubits() - set(qubits))  # ancillas (none in our circuits)
    full = order + extra
    n = len(order)
    probs = {"z": np.zeros(2**n), "x": np.zeros(2**n)}
    reals = realisations if detuning_khz else 1
    for _ in range(reals):
        det = {q: rng.normal(0, detuning_khz * 1e3) for q in full} if detuning_khz else None
        sim = cirq.DensityMatrixSimulator(noise=WillowNoise(cz_err, sq_err, det), dtype=np.complex128)
        rho = sim.simulate(circuit, qubit_order=full).final_density_matrix
        rho_x = sim.simulate(
            cirq.Circuit(cirq.Moment(_H_PHXZ.on(q) for q in order)),
            qubit_order=full, initial_state=rho,
        ).final_density_matrix
        for key, r in (("z", rho), ("x", rho_x)):
            p = np.clip(np.real(np.diag(r)), 0, None)
            if extra:  # trace out ancillas
                p = p.reshape(2**n, -1).sum(axis=1)
            probs[key] += p / reals
    # asymmetric readout as an exact confusion matrix per qubit (axis i = order[i], big-endian)
    for key in ("z", "x"):
        t = probs[key].reshape([2] * n)
        for i, q in enumerate(order):
            e0, e1 = zero_err[q][0], one_err[q][0]
            m = np.array([[1 - e0, e1], [e0, 1 - e1]])  # m[measured, true]
            t = np.moveaxis(np.tensordot(m, t, axes=([1], [i])), 0, i)
        probs[key] = t.reshape(-1) / t.sum()
    out = []
    for key in ("z", "x"):
        idx = rng.choice(2**n, size=shots, p=probs[key])
        out.append(((idx[:, None] >> np.arange(n - 1, -1, -1)) & 1).astype(np.int8))
    return out[0], out[1], probs["z"], probs["x"]


def score_parts(z_bits, x_bits, n_exc, k_max):
    z = judge.check_z_bitstring_distribution(z_bits, n_exc)
    x = judge.check_x_bitstring_distribution(x_bits, n_exc, k_max)
    f = float(np.mean(z_bits.sum(axis=1) == n_exc))
    return z, x, 1 / (z + x), f


def expected_score(pz, px, n_qubits, n_exc, k_max, shots):
    """Shot-noise-free proxy computed exactly from the outcome distributions.

    Z: E[Z] ~ (1 - f*sum q_j^2)/f + S*sum (q_j - 1/C)^2, where q_j are the in-subspace
       probabilities; the first term is the unavoidable shot-noise floor, the second the bias.
    X: average weight-k parity depends only on the Hamming weight w:
       m_k = sum_w P(w) K_k(w) / C(N,k), with Krawtchouk K_k(w) = sum_j (-1)^j C(w,j) C(N-w,k-j).
    Returns (f, Z_floor, Z_bias, X, 1/(Z_floor + Z_bias + X)).
    """
    N, n, C = n_qubits, n_exc, math.comb(n_qubits, n_exc)
    weights = np.array([bin(i).count("1") for i in range(2**N)])
    sub = pz[weights == n]
    f = sub.sum()
    q = sub / f
    z_floor = (1 - f * np.sum(q**2)) / f
    z_bias = shots * np.sum((q - 1 / C) ** 2)
    pw = np.bincount(weights, weights=px, minlength=N + 1)
    comb = lambda a, b: math.comb(a, b) if 0 <= b <= a else 0
    x = 0.0
    for k in range(1, k_max + 1):
        kraw = [sum((-1) ** j * comb(w, j) * comb(N - w, k - j) for j in range(k + 1)) for w in range(N + 1)]
        m = float(np.dot(pw, kraw)) / math.comb(N, k)
        e = comb(k, k // 2) * comb(N - k, n - k // 2) / C if k % 2 == 0 else 0.0
        x += (e - m) ** 2 / e**2 if e else (e - m) ** 2
    return f, z_floor, z_bias, x, 1 / (z_floor + z_bias + x)


# ============================================================================ runners
def cases(nmin, nmax, all_n):
    for N in range(nmin, nmax + 1):
        for n in range(1, (N if all_n else N // 2) + 1):
            yield N, n


def run_main(args):
    cal = judge.fake_calibration(args.seed)
    rng = np.random.default_rng(args.seed + 1)
    solution = importlib.import_module(args.solution)
    # The full solution takes an extra dd_schema knob; any other file with the notebook's
    # create_dicke_state signature is tested as-is.
    if "dd_schema" in inspect.signature(solution.create_dicke_state).parameters:
        variants = ([("sparse", "sparse"), ("cirqDD", "DEFAULT"), ("noDD", None)]
                    if args.compare_dd else [("sparse", "sparse")])
        build_fn = lambda N, n, schema: solution.create_dicke_state(N, n, *cal, dd_schema=schema)
    else:  # any module with the notebook's create_dicke_state signature
        variants = [(args.solution[:6], None)]
        build_fn = lambda N, n, schema: solution.create_dicke_state(N, n, *cal)
    rows = []
    total = {v: 0.0 for v, _ in variants}
    total_sampled = {v: 0.0 for v, _ in variants}
    hdr = f"{'N':>3} {'n':>2} {'var':>6} {'CZ':>4} {'mom':>4} {'build':>6} {'rules':>5} {'ideal':>7}" \
          f" {'f':>6} {'Zfloor':>6} {'Zbias':>6} {'X':>6} {'E[s]':>6} {'sampled':>7}"
    print(hdr)
    print("-" * len(hdr))
    for N, n in cases(args.nmin, args.nmax, args.all_n):
        for vname, schema in variants:
            t = time.time()
            try:
                circuit, qubits = build_fn(N, n, schema)
            except NotImplementedError as e:
                print(f"{N:>3} {n:>2} {vname:>6}  NotImplementedError: {e}")
                continue
            build = time.time() - t
            problems = check_rules(circuit, qubits, N, cal[0], cal[1])
            if build > 60:
                problems.append(f"build took {build:.0f}s > 60s")
            ideal = judge.test_circuit(circuit, n, qubits) if N <= args.ideal_nmax else float("nan")
            row = dict(N=N, n=n, variant=vname, cz=count_cz(circuit), moments=len(circuit),
                       build_s=round(build, 2), rule_problems=len(problems), ideal=ideal)
            if N <= args.noisy_nmax:
                zb, xb, pz, px = noisy_bitstrings(circuit, qubits, cal, args.shots, rng,
                                                  args.detuning_khz, args.realisations)
                k_max = args.k if args.k else N
                z, x, s, _ = score_parts(zb, xb, n, k_max)
                f, zf, zb_, xe, es = expected_score(pz, px, N, n, k_max, args.shots)
                row.update(f=f, Zfloor=zf, Zbias=zb_, Xexp=xe, exp_score=es,
                           Z_sampled=z, X_sampled=x, score_sampled=s)
                total[vname] += es
                total_sampled[vname] += s
            rows.append(row)
            fmt = lambda key, w, p: f"{row[key]:>{w}.{p}f}" if key in row else " " * w
            print(f"{N:>3} {n:>2} {vname:>6} {row['cz']:>4} {row['moments']:>4} {build:>5.1f}s"
                  f" {'ok' if not problems else 'FAIL':>5} {ideal:>7.5f} {fmt('f', 6, 3)}"
                  f" {fmt('Zfloor', 6, 3)} {fmt('Zbias', 6, 3)} {fmt('Xexp', 6, 3)}"
                  f" {fmt('exp_score', 6, 3)} {fmt('score_sampled', 7, 3)}")
            for p in problems[:5]:
                print("      !", p)
    for v in total:
        print(f"\n[{v}] total over N<={args.noisy_nmax}: expected {total[v]:.3f}"
              f" | one 10k-shot draw {total_sampled[v]:.3f}")
    if args.csv:
        keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0]).index(k) if k in rows[0] else 99)
        with open(args.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote {args.csv}")


def run_bonus(args):
    solution = importlib.import_module(args.solution)
    create_dicke_state_adaptive = getattr(solution, "create_dicke_state_adaptive", None)
    if create_dicke_state_adaptive is None:
        print(f"{args.solution}.py has no create_dicke_state_adaptive function, so there is "
              f"no bonus to score. Point --solution at a file that defines it (the full version does).")
        return
    score, t_all = 0.0, time.time()
    print(f"{'N':>3} {'n':>2} {'moments':>7} {'pts':>6} {'build':>6} {'check':>8}")
    for N in range(2, args.bonus_nmax + 1):
        for n in range(1, N // 2 + 1):
            t = time.time()
            try:
                circuit, qubits = create_dicke_state_adaptive(N, n)
            except NotImplementedError:
                print(f"{N:>3} {n:>2}  not implemented")
                continue
            build = time.time() - t
            judge.get_device().validate_circuit(circuit)
            assert not check_readout_diagonals(circuit)
            check = "skipped"
            if N <= args.ideal_nmax:
                judge.test_circuit(circuit, n, qubits)
                check = "exact"
            pts = N * n / len(circuit)
            score += pts
            print(f"{N:>3} {n:>2} {len(circuit):>7} {pts:>6.3f} {build:>5.1f}s {check:>8}")
    print(f"\nBonus score (sum of N*n/moments, N<={args.bonus_nmax}): {score:.3f}"
          f"  [{time.time() - t_all:.0f}s]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nmin", type=int, default=2)
    ap.add_argument("--nmax", type=int, default=8)
    ap.add_argument("--all-n", action="store_true", help="also test n > N/2")
    ap.add_argument("--ideal-nmax", type=int, default=14, help="largest N for the exact state check")
    ap.add_argument("--noisy-nmax", type=int, default=8, help="largest N for the noisy simulation")
    ap.add_argument("--shots", type=int, default=10_000)
    ap.add_argument("--k", type=int, default=0, help="max_correlator_size (default: N)")
    ap.add_argument("--detuning-khz", type=float, default=7.5,
                    help="std of quasi-static detuning (0 disables; ~7.5 kHz gives T2* ~ 30 us)")
    ap.add_argument("--realisations", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--compare-dd", action="store_true")
    ap.add_argument("--csv", default="")
    ap.add_argument("--solution", default="dicke_solution",
                    help="module to test, e.g. minimal_dicke (file name without .py)")
    ap.add_argument("--bonus", action="store_true")
    ap.add_argument("--bonus-nmax", type=int, default=20)
    args = ap.parse_args()
    run_bonus(args) if args.bonus else run_main(args)