"""Export the circuits that beat the bonus portfolio as validated cirq JSON (one file per case) + summary."""
import glob, json, sys, os
sys.path.insert(0, "/home/rpeddap/Documents/DuQuantum-2026/ryon")
import cirq, judge, toby_sol as t
OUT = "/home/rpeddap/Documents/DuQuantum-2026/research/primary_depth_20261025"
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
        except Exception:
            continue
        if key not in best or len(c) < len(best[key][0]):
            best[key] = (c, lab, f)
summary = {}
for key, (c, lab, f) in best.items():
    N, k = map(int, key.split(","))
    if len(c) >= ref[key]:
        continue
    dev.validate_circuit(c)
    ov = judge.test_circuit(c, k, set(lab))
    assert all(isinstance(op.gate, cirq.PhasedXZGate) or op.gate == cirq.CZ for op in c.all_operations())
    name = f"d_{N}_{k}.json"
    open(os.path.join(OUT, name), "w").write(cirq.to_json({"circuit": c, "qubits": sorted(lab)}))
    summary[key] = dict(moments=len(c), portfolio=ref[key], cz=sum(len(o.qubits) == 2 for o in c.all_operations()),
                        overlap=ov, file=name, source=f, gain=N * k / len(c) - N * k / ref[key])
json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
print(len(summary), "cases, gain", round(sum(v["gain"] for v in summary.values()), 3))
