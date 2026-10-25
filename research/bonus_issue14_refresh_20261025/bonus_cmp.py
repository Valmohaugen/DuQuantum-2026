"""Packed moment count of every searched circuit vs the bonus portfolio's, per (N, k)."""
import glob, json, sys
sys.path.insert(0, "/home/rpeddap/Documents/DuQuantum-2026/ryon")
import cirq, judge, toby_sol as t
dev = judge.get_device()
qs = list(dev.metadata.qubit_set); pairs = list(dev.metadata.qubit_pairs)
uni = {q: (1e-3, 0) for q in qs}; czu = {tuple(p): (2.5e-3, 0) for p in pairs}
adj, node = t.make_chip(czu, uni, uni, uni, 10, 2)
ref = json.load(open(sys.argv[1]))
best = {}
for f in glob.glob("out/g*.json") + glob.glob("out/hist_*.jsonl"):
    rows = [json.loads(l) for l in open(f)] if f.endswith("jsonl") else [json.load(open(f))]
    for d in rows:
        key = f"{d['N']},{d['k']}"
        if key not in ref:
            continue
        seq, th, z = [tuple(e) for e in d["edges"]], d["angles"], d.get("zset", [])
        try:
            if d.get("path"):
                w = [0] * (d["N"] - 1)
                for a, b in seq: w[min(a, b)] += 1
                lab = t.best_path(adj, node, w, 1e18)
            else:
                lab = t.best_patch(adj, node, [tuple(c) for c in d["cells"]], seq)
            c = t.compile_circuit(t.patch_ops(lab, seq, th, z), (), False, True)
        except Exception as e:
            continue
        m = len(c)
        if key not in best or m < best[key][0]:
            best[key] = (m, f, d["cz"])
gain = 0
for key in sorted(best, key=lambda s: tuple(map(int, s.split(",")))):
    m, f, cz = best[key]
    N, k = map(int, key.split(","))
    if m < ref[key]:
        gain += N * k / m - N * k / ref[key]
        print(key, "mine", m, "portfolio", ref[key], f, cz)
print("total gain if merged", round(gain, 3))
