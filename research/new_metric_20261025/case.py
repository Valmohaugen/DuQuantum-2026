"""One (variant, N, n, seed) case under the fast_eval noise model; writes a json row."""
import importlib, json, sys, time
variant, root, N, n, seed, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
sys.path[:0] = [f"{root}/ryon", f"{root}/toby", f"{root}/research/new_metric_20261025"]
import numpy as np
import fast_eval, judge
from test_dicke import expected_score
cal = judge.fake_calibration(seed)
t = time.time()
if variant.startswith("knob:"):
    m = importlib.import_module("toby_sol")
    for kv in variant[5:].split(","):
        k, v = kv.split("="); setattr(m, k, type(getattr(m, k))(eval(v)))
    c, qs = m.create_dicke_state(N, n, *cal)
elif variant == "main":
    m = importlib.import_module("toby_sol"); c, qs = m.create_dicke_state(N, n, *cal)
elif variant == "main_pack":
    m = importlib.import_module("toby_sol"); c, qs = m.create_dicke_state(N, n, *cal, dynamical_decoupling=False, pack=True)
elif variant == "main_nodd":
    m = importlib.import_module("toby_sol"); c, qs = m.create_dicke_state(N, n, *cal, dynamical_decoupling=False)
elif variant == "bonus_adaptive":
    m = importlib.import_module("bonus_sub_105326Z"); c, qs = m.create_dicke_state_adaptive(N, n)
elif variant == "main_adaptive":
    m = importlib.import_module("toby_sol"); c, qs = m.create_dicke_state_adaptive(N, n)
build = time.time() - t
import cirq
def fits(mp):
    ok = all(mp[q] in cal[1] for q in c.all_qubits())
    return ok and all((mp[o.qubits[0]], mp[o.qubits[1]]) in cal[0] or (mp[o.qubits[1]], mp[o.qubits[0]]) in cal[0]
                      for o in c.all_operations() if len(o.qubits) == 2)
if variant.startswith("bonus"):
    allq = list(c.all_qubits())
    mp = {q: q for q in allq}
    if not fits(mp):
        for dr in range(-6, 7):
            for dc in range(-6, 7):
                mp = {q: cirq.GridQubit(q.row + dr, q.col + dc) for q in allq}
                if fits(mp):
                    break
            else:
                continue
            break
        c = c.transform_qubits(lambda q: mp[q]); qs = {mp[q] for q in qs}
judge.test_circuit(c, n, qs)
rng = np.random.default_rng([seed, N, n])
pz, px = fast_eval.noisy_probs(c, qs, cal, rng, realisations=4)
f, zf, zb, x, es = expected_score(pz, px, N, n, N, 10_000)
cz = sum(1 for op in c.all_operations() if len(op.qubits) == 2)
dur = sum(42 if any(len(o.qubits) == 2 for o in mo) else 25 for mo in c)
json.dump(dict(variant=variant, N=N, n=n, seed=seed, cz=cz, moments=len(c), dur_ns=dur, ops1q=sum(1 for op in c.all_operations() if len(op.qubits) == 1),
               f=f, zf=zf, zb=zb, x=x, pen=zf + zb + x, es=es, build=build), open(out, "w"))
