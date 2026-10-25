"""Trajectory version of case.py for N >= 11 (main vs bonus build)."""
import importlib, json, sys, time
variant, root, N, n, seed, traj, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7]
sys.path[:0] = [f"{root}/ryon", f"{root}/toby", f"{root}/bonus56"]
import numpy as np, cirq
import traj_eval, judge
cal = judge.fake_calibration(seed)
def build(N, n, cal):
    if variant == "main":
        return importlib.import_module("toby_sol").create_dicke_state(N, n, *cal)
    if variant == "bonus_main":
        return importlib.import_module("bonus_sub").create_dicke_state(N, n, *cal)
    c, qs = importlib.import_module("bonus_sub").create_dicke_state_adaptive(N, n)
    allq = list(c.all_qubits())
    def fits(mp):
        return all(mp[q] in cal[1] for q in allq) and all((mp[o.qubits[0]], mp[o.qubits[1]]) in cal[0] or (mp[o.qubits[1]], mp[o.qubits[0]]) in cal[0]
                   for o in c.all_operations() if len(o.qubits) == 2)
    for dr in [0] + [d for a in range(1, 7) for d in (a, -a)]:
        for dc in [0] + [d for a in range(1, 7) for d in (a, -a)]:
            mp = {q: cirq.GridQubit(q.row + dr, q.col + dc) for q in allq}
            if fits(mp):
                return c.transform_qubits(lambda q: mp[q]), {mp[q] for q in qs}
    raise RuntimeError("no fit")
t = time.time()
r = traj_eval.score_case(build, N, n, cal, seed, traj=traj)
r.update(variant=variant, seed=seed, pen=r["zf"] + r["zb"] + r["x"], pen0=r["zf"] + r["x"], wall=time.time() - t)
json.dump({k: (float(v) if isinstance(v, (np.floating, float)) else v) for k, v in r.items()}, open(out, "w"))
