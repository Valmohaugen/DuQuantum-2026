import json, glob, collections, sys
import numpy as np
dens = collections.defaultdict(list)
for f in glob.glob("res/*.json"):
    r = json.load(open(f)); dens[(r["variant"], r["N"], r["n"])].append(r["pen"])
tr = {}
for f in glob.glob("tres/*.json"):
    r = json.load(open(f)); tr[(r["variant"], r["N"], r["n"])] = r["pen0"]
for nmax in range(12, 21):
    out = []
    for v in ("main", "bonus_adaptive"):
        pens = []
        for N in range(2, nmax + 1):
            for n in range(1, N // 2 + 1):
                if N <= 12: pens.append(np.mean(dens[(v, N, n)]))
                elif (v, N, n) in tr: pens.append(tr[(v, N, n)])
                else: pens = None; break
            if pens is None: break
        out.append(f"{v} {1/np.mean(pens):.4f} ({len(pens)} cases)" if pens else f"{v} incomplete")
    print(f"N=2..{nmax}:", " | ".join(out))
