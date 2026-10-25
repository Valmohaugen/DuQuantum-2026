"""Regenerate the data behind the figures (figures/data/). Slow: builds circuits and runs the noise model.

    python figures/compute_data.py            # everything, about 15 minutes on one core
    python figures/compute_data.py layouts    # one part: chip, layouts, bonus, scores, resources

Main-entry results use the challenge notebook's synthetic calibration recipe (archive/judge.py,
fake_calibration), so they illustrate the method rather than predict a hardware score.
"""
import csv
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "figures" / "data"
sys.path[:0] = [str(ROOT), str(ROOT / "archive")]

import cirq_google  # noqa: E402
import numpy as np  # noqa: E402

import dicke_solution  # noqa: E402  (team's first solution: routed Bärtschi-Eidenbenz, the baseline)
import fast_eval  # noqa: E402
import judge  # noqa: E402
import qubillionaires_solution as sol  # noqa: E402
from test_dicke import expected_score  # noqa: E402

LAYOUT_CASES = [(8, 4), (10, 3), (10, 5), (12, 6), (15, 4)]
LAYOUT_SEED = 0
SCORE_SEEDS = (0, 1, 2)
SHOTS = 10_000


def write_csv(name, rows):
    with open(DATA / name, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote figures/data/{name} ({len(rows)} rows)", flush=True)


def write_json(name, obj):
    (DATA / name).write_text(json.dumps(obj, indent=1))
    print(f"wrote figures/data/{name}", flush=True)


def serialise(circuit):
    """Moments as lists of ["cz", r1, c1, r2, c2] / ["1q", r, c]."""
    out = []
    for moment in circuit:
        ops = []
        for op in moment:
            qs = op.qubits
            if len(qs) == 2:
                ops.append(["cz", qs[0].row, qs[0].col, qs[1].row, qs[1].col])
            else:
                ops.append(["1q", qs[0].row, qs[0].col])
        out.append(ops)
    return out


def count_cz(circuit):
    return sum(1 for op in circuit.all_operations() if len(op.qubits) == 2)


def chip():
    cz, sq, zero, one = judge.fake_calibration(LAYOUT_SEED)
    meta = cirq_google.Willow105.metadata
    working = {frozenset(p) for p in cz}
    write_json("chip.json", dict(
        calibration_seed=LAYOUT_SEED,
        qubits=sorted([q.row, q.col] for q in meta.qubit_set),
        couplers=sorted(sorted([q.row, q.col] for q in p) for p in meta.qubit_pairs),
        dropped_qubits=sorted([q.row, q.col] for q in meta.qubit_set if q not in sq),
        dropped_couplers=sorted(sorted([q.row, q.col] for q in p) for p in meta.qubit_pairs
                                if frozenset(p) not in working),
        readout=[[q.row, q.col, float(zero[q][0]), float(one[q][0])] for q in sorted(zero)],
    ))


def layouts():
    cal = judge.fake_calibration(LAYOUT_SEED)
    out = []
    for N, n in LAYOUT_CASES:
        t = time.monotonic()
        main, main_qs = sol.create_dicke_state(N, n, *cal)
        build = time.monotonic() - t
        bonus, bonus_qs = sol.create_dicke_state_adaptive(N, n)
        for entry, c, qs, b in (("main", main, main_qs, build), ("bonus", bonus, bonus_qs, None)):
            judge.test_circuit(c, n, qs)
            out.append(dict(N=N, n=n, entry=entry, moments=len(c), cz=count_cz(c), build_s=b,
                            qubits=sorted([q.row, q.col] for q in qs), circuit=serialise(c)))
        print(f"layout D({N},{n}): main {len(main)} moments / {count_cz(main)} cz, "
              f"bonus {len(bonus)} / {count_cz(bonus)}", flush=True)
    write_json("layouts.json", out)


def bonus():
    rows = []
    for N in range(2, 16):
        for n in range(1, N // 2 + 1):
            c, qs = sol.create_dicke_state_adaptive(N, n)
            rows.append(dict(N=N, n=n, moments=len(c), cz=count_cz(c), contribution=round(N * n / len(c), 6)))
    write_csv("bonus_cases.csv", rows)


def ideal_score(N, n):
    """Noiseless expected score: the finite-shot floor of the judging metric for a perfect state."""
    psi = judge.create_dicke_statevector(N, n)
    px = psi.reshape([2] * N)
    h = np.array([[1, 1], [1, -1]]) / math.sqrt(2)
    for axis in range(N):
        px = np.moveaxis(np.tensordot(h, px, axes=([1], [axis])), 0, axis)
    return expected_score(psi**2, px.reshape(-1) ** 2, N, n, N, SHOTS)


def scores():
    build = fast_eval.module_builder("qubillionaires_solution")
    _, rows = fast_eval.evaluate(build, fast_eval.cases(2, 8), SCORE_SEEDS)
    out = []
    for r in rows:
        _, izf, izb, ix, ies = ideal_score(int(r["N"]), int(r["n"]))
        out.append(dict(N=int(r["N"]), n=int(r["n"]), cz=r["cz"], moments=r["moments"], f=r["f"],
                        z_floor=r["zf"], z_bias=r["zb"], x=r["x"], expected_score=r["es"],
                        ideal_z_floor=izf, ideal_z_bias=izb, ideal_x=ix, ideal_score=ies))
    write_csv("main_scores.csv", out)


def resources():
    cal = judge.fake_calibration(LAYOUT_SEED)
    builders = (
        ("main", lambda N, n: sol.create_dicke_state(N, n, *cal)),
        ("bonus", sol.create_dicke_state_adaptive),
        ("baseline", lambda N, n: dicke_solution.create_dicke_state(N, n, *cal)),
    )
    rows = []
    for N in range(2, 16):
        n = N // 2
        for entry, build in builders:
            t = time.monotonic()
            try:
                c, qs = build(N, n)
            except NotImplementedError as e:  # a gap in the plot, not a crash
                print(f"resources D({N},{n}) {entry}: NotImplementedError {e}", flush=True)
                continue
            dt = time.monotonic() - t
            rows.append(dict(N=N, n=n, entry=entry, cz=count_cz(c), moments=len(c), build_s=round(dt, 2)))
            print(f"resources D({N},{n}) {entry}: {count_cz(c)} cz, {len(c)} moments, {dt:.1f} s", flush=True)
    write_csv("resources.csv", rows)


PARTS = dict(chip=chip, layouts=layouts, bonus=bonus, scores=scores, resources=resources)

if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or PARTS:
        PARTS[name]()
