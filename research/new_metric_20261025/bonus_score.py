import sys, importlib, time
root, mod = sys.argv[1], sys.argv[2]
sys.path[:0] = [f"{root}/ryon", f"{root}/toby", f"{root}/research/new_metric_20261025"]
m = importlib.import_module(mod)
tot = 0; mx = 0
for N in range(2, 16):
    for n in range(1, N // 2 + 1):
        c, q = m.create_dicke_state_adaptive(N, n); tot += N * n / len(c); mx = max(mx, len(c))
print(mod, "bonus N=2..15:", round(tot, 4), "max moments", mx)
