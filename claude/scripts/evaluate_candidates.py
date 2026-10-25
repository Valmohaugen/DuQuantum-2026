"""Paired circuit ablations ranked by harmonic finite-shot score.

Run from the repository root with ``python -m claude.scripts.evaluate_candidates``.
The simulator is the existing ryon.fast_eval model; count statistics reproduce
the notebook scorer without allocating shot-by-qubit arrays. No solver is edited.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import sys
import time
from dataclasses import replace
from pathlib import Path

import cirq
import cirq_google
import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def penalties(z_counts, x_counts, n, k, max_correlator_size=None):
    """Notebook Z+X penalty from sector counts and X Hamming-weight counts.

    z_counts ends with one outside-sector bin. A draw with no in-sector Z
    observations is undefined in the original scorer and fails explicitly here.
    """
    shots = z_counts.sum(axis=-1)
    sector = z_counts[..., :-1]
    surviving = sector.sum(axis=-1)
    if np.any(surviving == 0):
        raise ValueError("undefined notebook score: no in-sector Z shots")
    q = sector / surviving[..., None]
    z = shots * np.sum((q - 1 / math.comb(n, k)) ** 2, axis=-1)
    x = np.zeros_like(z, dtype=float)

    def comb(a, b):
        return math.comb(a, b) if 0 <= b <= a else 0

    for order in range(1, (n if max_correlator_size is None else max_correlator_size) + 1):
        parity = np.array(
            [
                sum((-1) ** j * comb(w, j) * comb(n - w, order - j) for j in range(order + 1))
                / math.comb(n, order)
                for w in range(n + 1)
            ]
        )
        observed = x_counts @ parity / x_counts.sum(axis=-1)
        expected = (
            (comb(order, order // 2) * comb(n - order, k - order // 2) / comb(n, k))
            if order % 2 == 0
            else 0
        )
        x += (observed - expected) ** 2 / (expected**2 if expected else 1)
    return z + x


def sampled_penalties(pz, px, n, k, shots, repeats, seed):
    weights = np.array([i.bit_count() for i in range(2**n)])
    sector = pz[weights == k]
    z_probs = np.append(sector, max(0, 1 - sector.sum()))
    z_probs /= z_probs.sum()
    x_probs = np.bincount(weights, weights=px, minlength=n + 1)
    x_probs /= x_probs.sum()
    rng = np.random.default_rng(seed)
    return penalties(
        rng.multinomial(shots, z_probs, size=repeats),
        rng.multinomial(shots, x_probs, size=repeats),
        n,
        k,
    )


def summary(rows):
    """Equal weight per case and calibration; never silently discard failures."""
    values = np.array([r["mean_penalty"] for r in rows])
    by_case = {}
    for row in rows:
        by_case.setdefault((row["N"], row["n"]), []).append(row["mean_score"])
    case_scores = np.array([np.mean(v) for v in by_case.values()])
    seed_h = [
        1 / np.mean([r["mean_penalty"] for r in rows if r["seed"] == seed])
        for seed in sorted({r["seed"] for r in rows})
    ]
    return {
        "harmonic_sampled": float(1 / values.mean()),
        "harmonic_proxy": float(1 / np.mean([1 / r["proxy"] for r in rows])),
        "harmonic_of_case_mean_scores": float(1 / np.mean(1 / case_scores)),
        "arithmetic_score": float(np.mean([r["mean_score"] for r in rows])),
        "worst_case_mean_score": float(case_scores.min()),
        "harmonic_by_seed": [float(v) for v in seed_h],
        "mean_moments": float(np.mean([r["moments"] for r in rows])),
        "max_moments": max(r["moments"] for r in rows),
        "mean_cz": float(np.mean([r["cz"] for r in rows])),
        "mean_oneq": float(np.mean([r["oneq"] for r in rows])),
    }


def builders(extra):
    from claude.dicke_prep import CONFIG, create_dicke_state

    def configured(**kw):
        config = replace(CONFIG, **kw)
        return lambda n, k, cal: create_dicke_state(n, k, *cal, config=config)

    def packed(n, k, cal):
        circuit, qubits = configured(use_dynamical_decoupling=False)(n, k, cal)
        return cirq.Circuit(circuit.all_operations()), qubits

    result = {
        "simple": configured(use_dynamical_decoupling=False),
        "analytic": configured(construction="analytic", use_dynamical_decoupling=False),
        "current": configured(use_dynamical_decoupling=True),
        "sparse": configured(use_dynamical_decoupling=True, dd_strategy="sparse"),
        "packed": packed,
    }
    for name, path in extra.items():
        spec = importlib.util.spec_from_file_location(f"eval_{name}", path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        result[name] = lambda n, k, cal, module=module: module.create_dicke_state(n, k, *cal)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", default=["2,1", "4,2", "6,3", "8,4"])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument(
        "--variants", nargs="+", default=["simple", "analytic", "current", "sparse"]
    )
    parser.add_argument("--candidate", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--shots", type=int, default=10000)
    parser.add_argument("--repeats", type=int, default=256)
    parser.add_argument("--realisations", type=int, default=4)
    parser.add_argument("--detuning-khz", type=float, default=7.5)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--willow-fallback",
        action="store_true",
        help="Explicitly allow stable Cirq's willow_pink device alias",
    )
    args = parser.parse_args()
    cases = [tuple(map(int, value.split(","))) for value in args.cases]
    if (
        len(set(cases)) != len(cases)
        or len(set(args.seeds)) != len(args.seeds)
        or not args.seeds
        or min(args.seeds) < 0
        or any(not 2 <= n <= 10 or not 0 < k < n for n, k in cases)
        or min(args.shots, args.repeats, args.realisations) < 1
        or not math.isfinite(args.detuning_khz)
        or args.detuning_khz < 0
    ):
        parser.error(
            "use unique cases (2<=N<=10, 0<k<N), unique nonnegative seeds and positive counts"
        )
    sys.path.insert(0, str(ROOT / "ryon"))
    import fast_eval
    import judge
    from test_dicke import check_rules, expected_score

    fallback = not hasattr(cirq_google, "Willow105")
    if fallback:
        if not args.willow_fallback:
            parser.error("Willow105 unavailable; use the locked runtime or --willow-fallback")
        cirq_google.Willow105 = judge.get_device()
    extra = {
        name: (ROOT / path).resolve()
        for name, path in (value.split("=", 1) for value in args.candidate)
    }
    available = builders(extra)
    names = args.variants + list(extra)
    if len(set(names)) != len(names) or set(names) - available.keys():
        parser.error("candidate names must be unique and variants must be known")
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "results.json").exists():
        parser.error("output already contains results; choose a fresh directory")
    sources = [
        Path(__file__),
        ROOT / "claude/dicke_prep.py",
        ROOT / "ryon/fast_eval.py",
        ROOT / "ryon/test_dicke.py",
        ROOT / "ryon/judge.py",
        *extra.values(),
    ]
    data = {
        "complete": False,
        "settings": {**vars(args), "output": str(args.output)},
        "runtime": {
            "python": platform.python_version(),
            "cirq": cirq.__version__,
            "numpy": np.__version__,
            "willow_fallback": fallback,
        },
        "sources": {
            str(p.relative_to(ROOT) if p.is_relative_to(ROOT) else p): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in sources
        },
        "records": [],
        "summary": {},
    }
    calibrations = {seed: judge.fake_calibration(seed) for seed in args.seeds}
    for name in names:
        for n, k in cases:
            for seed in args.seeds:
                cal = calibrations[seed]
                started = time.monotonic()
                circuit, qubits = available[name](n, k, cal)
                build_s = time.monotonic() - started
                problems = check_rules(circuit, qubits, n, *cal[:2])
                if problems:
                    raise ValueError(f"{name} {n, k}: {problems}")
                if len(circuit.all_qubits()) > 10:
                    raise ValueError("density simulation is limited to ten total qubits")
                fidelity = judge.test_circuit(
                    circuit, k, qubits, sampler=cirq.Simulator(dtype=np.complex128)
                )
                pz, px = fast_eval.noisy_probs(
                    circuit,
                    qubits,
                    cal,
                    np.random.default_rng([seed, n, k]),
                    detuning_khz=args.detuning_khz,
                    realisations=args.realisations,
                )
                draws = sampled_penalties(pz, px, n, k, args.shots, args.repeats, [seed, n, k, 117])
                ops = list(circuit.all_operations())
                row = dict(
                    variant=name,
                    N=n,
                    n=k,
                    seed=seed,
                    moments=len(circuit),
                    cz=sum(len(op.qubits) == 2 for op in ops),
                    oneq=sum(len(op.qubits) == 1 for op in ops),
                    fidelity=fidelity,
                    build_s=build_s,
                    mean_penalty=float(draws.mean()),
                    mean_score=float(np.mean(1 / draws)),
                    proxy=float(expected_score(pz, px, n, k, n, args.shots)[-1]),
                    pz=pz.tolist(),
                    px=px.tolist(),
                )
                artifact = f"{name}_{n}_{k}_{seed}.json"
                circuit_dir = args.output / "circuits"
                circuit_dir.mkdir(exist_ok=True)
                cirq.to_json(circuit, circuit_dir / artifact)
                row["circuit"] = f"circuits/{artifact}"
                data["records"].append(row)
                (args.output / "results.json").write_text(
                    json.dumps(data, indent=2, allow_nan=False)
                )
                print(
                    f"{name:12} {n},{k} seed={seed} moments={len(circuit):3} "
                    f"CZ={row['cz']:3} H={1 / draws.mean():.6f}",
                    flush=True,
                )
        data["summary"][name] = summary([r for r in data["records"] if r["variant"] == name])
    data["complete"] = True
    (args.output / "results.json").write_text(json.dumps(data, indent=2, allow_nan=False))
    lines = [
        "| Candidate | Harmonic sampled | Harmonic proxy | Worst case mean | Mean depth | Max depth | Mean CZ |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, row in sorted(data["summary"].items(), key=lambda pair: -pair[1]["harmonic_sampled"]):
        lines.append(
            f"| {name} | {row['harmonic_sampled']:.6f} | {row['harmonic_proxy']:.6f} | "
            f"{row['worst_case_mean_score']:.6f} | {row['mean_moments']:.2f} | "
            f"{row['max_moments']} | {row['mean_cz']:.2f} |"
        )
    report = "\n".join(lines) + "\n"
    (args.output / "summary.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
