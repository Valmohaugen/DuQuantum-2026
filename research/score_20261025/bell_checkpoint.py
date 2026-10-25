"""Reproduce the calibrated Bell checkpoint on fresh fields and shot batches.

Run from the repository root. The baseline is loaded from the recorded Git
revision; the candidate imports outside the repository source tree as a single
standalone file. Outputs go under benchmark_outputs by default.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import time
import types
from pathlib import Path

import cirq
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ryon"))
import fast_eval as fe  # noqa: E402
import judge  # noqa: E402


def sampled_stats(pz, px, seed, replicates, shots=10_000):
    rng = np.random.default_rng([seed, 9931])
    scores = []
    undefined = infinite = 0
    pz_grouped = np.array([pz[1], pz[2], pz[0] + pz[3]])
    px_grouped = np.array([px[0], px[1] + px[2], px[3]])
    for start in range(0, replicates, 10_000):
        size = min(10_000, replicates - start)
        z = rng.multinomial(shots, pz_grouped, size=size)
        x = rng.multinomial(shots, px_grouped, size=size)
        accepted = z[:, 0] + z[:, 1]
        difference = z[:, 0] - z[:, 1]
        z_score = (
            shots * difference.astype(float) ** 2 / (2 * np.maximum(accepted, 1).astype(float) ** 2)
        )
        x_one = (x[:, 0] - x[:, 2]) / shots
        x_two = (x[:, 0] + x[:, 2] - x[:, 1]) / shots
        denominator = z_score + x_one**2 + (1 - x_two) ** 2
        undefined += int((accepted == 0).sum())
        infinite += int(((accepted > 0) & (denominator == 0)).sum())
        valid = (accepted > 0) & (denominator > 0)
        scores.extend((1 / denominator[valid]).tolist())
    values = np.asarray(scores)
    return dict(
        mean=float(values.mean()),
        standard_error=float(values.std(ddof=1) / math.sqrt(len(values))),
        median=float(np.median(values)),
        p10=float(np.quantile(values, 0.1)),
        p90=float(np.quantile(values, 0.9)),
        maximum=float(values.max()),
        undefined=undefined,
        infinite=infinite,
        finite_count=len(values),
    )


def probabilities(circuit, qubits, cal, seed, realisations):
    physical = sorted(cal[1])
    fields = np.random.default_rng([seed, 1107]).normal(0, 7500, size=(realisations, len(physical)))
    lookup = {q: i for i, q in enumerate(physical)}
    order = sorted(qubits) + sorted(circuit.all_qubits() - set(qubits))
    draws = fields[:, [lookup[q] for q in order]]

    class FixedNormal:
        def __init__(self):
            self.values = iter(draws.reshape(-1))

        def normal(self, *args, **kwargs):
            return next(self.values)

    return fe.noisy_probs(circuit, qubits, cal, FixedNormal(), realisations=realisations)


def summarize(rows):
    output = {}
    for key in ("proxy", "mean", "median", "p10"):
        values = []
        for row in rows:
            before, after = row["choices"]["baseline"], row["choices"]["candidate"]
            values.append(
                (before[key], after[key])
                if key == "proxy"
                else (before["sampled"][key], after["sampled"][key])
            )
        values = np.asarray(values)
        delta = values[:, 1] - values[:, 0]
        output[key] = dict(
            before=float(values[:, 0].mean()),
            after=float(values[:, 1].mean()),
            gain=float(delta.mean()),
            calibration_se=float(delta.std(ddof=1) / math.sqrt(len(delta))),
            wins=int(sum(delta > 0)),
        )
    return output


def run(args):
    baseline_code = subprocess.check_output(
        ["git", "show", f"{args.baseline}:ryon/toby_sol.py"], cwd=ROOT, text=True
    )
    baseline = types.ModuleType("recorded_baseline")
    exec(compile(baseline_code, "recorded_baseline.py", "exec"), baseline.__dict__)
    source = ROOT / "toby/calibrated_score_sol.py"
    spec = importlib.util.spec_from_file_location("checkpoint_candidate", source)
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)
    report = dict(
        baseline_commit=args.baseline,
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        shots=10_000,
        replicates=args.replicates,
        detuning_realisations=args.realisations,
        k_max=2,
        rows=[],
    )
    for seed in args.seeds:
        cal = judge.fake_calibration(seed)
        before, bq = baseline.create_dicke_state(2, 1, *cal)
        started = time.monotonic()
        after, aq = candidate.create_dicke_state(2, 1, *cal)
        build_seconds = time.monotonic() - started
        assert build_seconds < 60
        candidate.check_circuit(after, cal[0], cal[1])
        judge.get_device().validate_circuit(after)
        state = cirq.final_state_vector(after, qubit_order=sorted(aq), dtype=np.complex128)
        target = np.array([0, 1, 1, 0]) / math.sqrt(2)
        overlap = np.vdot(target, state)
        error = float(np.linalg.norm(state - target * overlap / abs(overlap)))
        assert error < 1e-10
        row = dict(seed=seed, build_seconds=build_seconds, state_l2=error, choices={})
        for label, circuit, qubits in [
            ("baseline", before, bq),
            ("candidate", after, aq),
        ]:
            pz, px = probabilities(circuit, qubits, cal, seed + 900_000, args.realisations)
            row["choices"][label] = dict(
                pair=[str(q) for q in sorted(qubits)],
                proxy=fe.expected_score(pz, px, 2, 1, 2, 10_000)[-1],
                sampled=sampled_stats(pz, px, seed + 400_000, args.replicates),
                pz=pz.tolist(),
                px=px.tolist(),
                moments=len(circuit),
                cz=sum(len(op.qubits) == 2 for op in circuit.all_operations()),
                pulses=sum(len(op.qubits) == 1 for op in circuit.all_operations()),
            )
        report["rows"].append(row)
        print(json.dumps(row), flush=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    report["summary"] = summarize(report["rows"])
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="5732c7bb2bc95181fa218ffe2a8733426800dd71")
    parser.add_argument("--seeds", nargs="+", type=int, default=list(range(50000, 50050)))
    parser.add_argument("--realisations", type=int, default=64)
    parser.add_argument("--replicates", type=int, default=100_000)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "benchmark_outputs/bell_checkpoint_recheck.json",
    )
    run(parser.parse_args())
