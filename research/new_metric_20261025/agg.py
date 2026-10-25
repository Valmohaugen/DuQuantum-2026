import glob, json, sys, collections
import numpy as np
d = sys.argv[1]
rows = [json.loads(l) for l in open(d)] if d.endswith(".jsonl") else [json.load(open(f)) for f in glob.glob(f"{d}/*.json")]
by = collections.defaultdict(list)
for r in rows: by[(r["variant"], r["N"], r["n"])].append(r)
variants = sorted({r["variant"] for r in rows})
def summary(v, nmax, seeds=(0, 1, 2)):
    cs = [(N, n) for N in range(2, nmax + 1) for n in range(1, N // 2 + 1)]
    pens, ess, mom, cz, dur = [], [], [], [], []
    for c in cs:
        rs = [r for r in by.get((v, *c), []) if r["seed"] in seeds]
        if len(rs) < len(seeds): return None
        pens.append(np.mean([r["pen"] for r in rs])); ess.append(np.mean([r["es"] for r in rs]))
        mom.append(np.mean([r["moments"] for r in rs])); cz.append(np.mean([r["cz"] for r in rs])); dur.append(np.mean([r["dur_ns"] for r in rs]))
    return dict(new=1 / np.mean(pens), legacy=sum(ess), mom=np.mean(mom), cz=np.mean(cz), dur=np.mean(dur), ncase=len(cs))
for nmax, seeds in ((8, (0, 1, 2)), (10, (0, 1, 2)), (12, (0,))):
    print(f"--- N=2..{nmax} seeds {seeds}")
    for v in variants:
        s = summary(v, nmax, seeds)
        if s: print(f"{v:16s} new 1/mean(pen) {s['new']:.4f}  legacy sum E[s] {s['legacy']:.3f}  mean moments {s['mom']:.1f} cz {s['cz']:.1f} dur {s['dur']:.0f}ns  ({s['ncase']} cases)")
if "-v" in sys.argv:
    for (v, N, n), rs in sorted(by.items(), key=lambda t: (t[0][1], t[0][2], t[0][0])):
        print(f"{N:3d} {n:2d} {v:16s} pen {np.mean([r['pen'] for r in rs]):.3f} f {np.mean([r['f'] for r in rs]):.3f} zb {np.mean([r['zb'] for r in rs]):.3f} x {np.mean([r['x'] for r in rs]):.3f} mom {np.mean([r['moments'] for r in rs]):.0f} cz {np.mean([r['cz'] for r in rs]):.0f} n={len(rs)}")
