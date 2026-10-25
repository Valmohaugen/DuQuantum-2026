"""Sample the chart's three cases using the original notebook calibration recipe.

Noise assumption: calibrated stochastic Pauli errors after each gate, plus the
notebook's asymmetric readout errors. No idle, coherent or leakage model is
specified in the notebook, so those channels are not added here. qsim is an
evaluation-only dependency; it never enters submitted constructors.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np

from claude.scripts.evaluate_candidates import ROOT, builders, penalties


def notebook_api():
    notebook = ROOT / "Google Quantum AI Challenge.ipynb"
    cells = json.loads(notebook.read_text())["cells"]
    namespace = {}
    for index in (0, 7, 11):
        exec(compile("".join(cells[index]["source"]), f"{notebook}:cell{index}", "exec"), namespace)
    return namespace


def calibration(api, seed):
    """Call the notebook's functions with an explicit shared reproducible RNG."""
    rng = np.random.default_rng(seed)
    dropouts = api["pick_single_qubit_dropouts"](0.01, rng)
    sq = api["generate_qubit_error_rates"](4e-4, 0.5, dropouts, 2e-4, rng)
    cz = api["generate_two_qubit_pauli_error_rates"](rng=rng, single_qubit_dropouts=dropouts)
    zero = api["generate_qubit_error_rates"](5e-3, 0.5, dropouts, 2e-4, rng)
    one = api["generate_qubit_error_rates"](1e-2, 0.5, dropouts, 3e-4, rng)
    return cz, sq, zero, one


def noisy_circuit(circuit, cal, basis):
    """Calibrated Pauli mixture; basis rotations receive the same 1q noise."""
    cz, sq, _, _ = cal
    body = circuit.copy()
    order = sorted(circuit.all_qubits())
    if basis == "X":
        body.append(cirq.Moment(cirq.H(q) for q in order))
    moments = []
    for moment in body:
        moments.append(moment)
        errors = []
        for op in moment:
            if len(op.qubits) == 2:
                a, b = op.qubits
                rate = (cz.get((a, b)) or cz[(b, a)])[0]
            else:
                rate = sq[op.qubits[0]][0]
            errors.append(cirq.depolarize(rate, n_qubits=len(op.qubits)).on(*op.qubits))
        moments.append(cirq.Moment(errors))
    moments.append(cirq.Moment(cirq.measure(*order, key="m")))
    return cirq.Circuit(moments)


def apply_readout(bits, order, cal, rng):
    zero = np.array([cal[2][q][0] for q in order])
    one = np.array([cal[3][q][0] for q in order])
    return np.logical_xor(bits, rng.random(bits.shape) < np.where(bits, one, zero)).astype(np.int8)


def count_statistics(z_bits, x_bits, n, k):
    encoded = z_bits @ (2 ** np.arange(n))
    all_counts = np.bincount(encoded, minlength=2**n)
    weights = np.array([i.bit_count() for i in range(2**n)])
    z = np.append(all_counts[weights == k], all_counts[weights != k].sum())
    x = np.bincount(x_bits.sum(axis=1), minlength=n + 1)
    return z, x


def main():
    import qsimcirq

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--shots", type=int, default=10000)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()
    if args.seed < 0 or args.shots < 1 or args.threads < 1:
        parser.error("seed must be nonnegative; shots and threads must be positive")
    if args.output.exists():
        parser.error("choose a fresh output directory")
    sys.path.insert(0, str(ROOT / "ryon"))
    import judge
    from test_dicke import check_rules

    fallback = not hasattr(cirq_google, "Willow105")
    if fallback:
        cirq_google.Willow105 = judge.get_device()
    api = notebook_api()
    cal = calibration(api, args.seed)
    candidates = {
        "peer": ROOT / "ryon/toby_sol.py",
        "standalone": ROOT / "research/bonus_band_20261025/native_submission.py",
        "old_partial": ROOT / "research/chart_comparison_20261025/old_solution_partial.py",
    }
    constructors = builders(candidates)
    args.output.mkdir(parents=True)
    maps = [
        [
            {
                "qubits": [str(q) for q in key] if isinstance(key, tuple) else [str(key)],
                "rate": float(rate),
                "uncertainty": float(uncertainty),
            }
            for key, (rate, uncertainty) in mapping.items()
        ]
        for mapping in cal
    ]
    (args.output / "calibration.json").write_text(json.dumps(maps, indent=2))
    sources = [
        Path(__file__),
        ROOT / "Google Quantum AI Challenge.ipynb",
        ROOT / "claude/scripts/evaluate_candidates.py",
        ROOT / "claude/dicke_prep.py",
        ROOT / "ryon/judge.py",
        ROOT / "ryon/test_dicke.py",
        *candidates.values(),
    ]
    data = {
        "complete": False,
        "seed": args.seed,
        "shots_per_basis": args.shots,
        "noise": "calibrated Pauli gate errors + asymmetric readout; no idle noise",
        "calibration": "original notebook cells 11–12, shared RNG explicitly seeded",
        "cirq": cirq.__version__,
        "qsim": qsimcirq.__version__,
        "threads": args.threads,
        "willow_fallback": fallback,
        "sources_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources
        },
        "records": [],
    }
    cache = {}
    for n, k in [(10, 3), (10, 5), (15, 4)]:
        for name in ["peer", "standalone", "simple", "old_partial"]:
            if name == "old_partial" and n > 11:
                continue
            circuit, qubits = constructors[name](n, k, cal)
            problems = check_rules(circuit, qubits, n, *cal[:2])
            if problems or circuit.all_qubits() != set(qubits):
                raise ValueError(f"unsupported circuit: {problems}")
            fidelity = judge.test_circuit(
                circuit, k, qubits, sampler=cirq.Simulator(dtype=np.complex128)
            )
            serialized = cirq.to_json(circuit)
            digest = hashlib.sha256(serialized.encode()).hexdigest()
            started = time.monotonic()
            reused = digest in cache
            if not reused:
                measurements = []
                for basis_index, basis in enumerate(["Z", "X"]):
                    noisy = noisy_circuit(circuit, cal, basis)
                    seed = args.seed * 1000 + n * 10 + k + basis_index * 100000 + 117
                    simulator = qsimcirq.QSimSimulator(
                        qsim_options=qsimcirq.QSimOptions(
                            cpu_threads=args.threads, max_fused_gate_size=3
                        ),
                        seed=seed,
                    )
                    bits = simulator.run(noisy, repetitions=args.shots).measurements["m"]
                    bits = apply_readout(bits, sorted(qubits), cal, np.random.default_rng(seed + 1))
                    measurements.append(bits)
                    print(
                        f"seed={args.seed} {name} D({n},{k}) {basis} sampled "
                        f"in {time.monotonic() - started:.1f}s",
                        flush=True,
                    )
                cache[digest] = measurements
            z_bits, x_bits = cache[digest]
            z, x = count_statistics(z_bits, x_bits, n, k)
            scores = {
                str(cutoff): float(1 / penalties(z, x, n, k, cutoff))
                for cutoff in sorted({2, 4, n})
            }
            stem = f"{name}_{n}_{k}"
            (args.output / f"{stem}.json").write_text(serialized)
            np.savez_compressed(args.output / f"{stem}_samples.npz", z=z_bits, x=x_bits)
            data["records"].append(
                dict(
                    variant=name,
                    N=n,
                    n=k,
                    moments=len(circuit),
                    cz=sum(op.gate == cirq.CZ for op in circuit.all_operations()),
                    fidelity=fidelity,
                    scores=scores,
                    reused_identical=reused,
                    circuit_sha256=digest,
                    seconds=time.monotonic() - started,
                )
            )
            (args.output / "results.json").write_text(json.dumps(data, indent=2, allow_nan=False))
            print(f"seed={args.seed} {name} D({n},{k}) scores={scores}", flush=True)
    data["complete"] = True
    (args.output / "results.json").write_text(json.dumps(data, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
