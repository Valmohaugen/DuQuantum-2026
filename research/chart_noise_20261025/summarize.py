"""Combine the three seeded chart simulations; fail on missing observations."""

import json
from pathlib import Path

import numpy as np


def main():
    root = Path(__file__).resolve().parent
    records = []
    for seed in range(3):
        for suffix in ("", "_old15"):
            data = json.loads((root / f"seed{seed}{suffix}" / "results.json").read_text())
            if not data["complete"]:
                raise ValueError(f"seed {seed}{suffix} incomplete")
            for row in data["records"]:
                row = {**row, "seed": seed}
                if row["variant"] == "old_partial":
                    row["variant"] = "old"
                records.append(row)
    if len(records) != 36:
        raise ValueError("expected 36 case/seed/variant records")

    def mean_se(values):
        a = np.asarray(values, dtype=float)
        return {
            "mean": float(a.mean()),
            "se": float(a.std(ddof=1) / np.sqrt(len(a))),
            "values": a.tolist(),
        }

    summaries = {}
    for variant in ["old", "simple", "standalone", "peer"]:
        selected = [r for r in records if r["variant"] == variant]
        if {(r["N"], r["n"], r["seed"]) for r in selected} != {
            (n, k, seed) for n, k in [(10, 3), (10, 5), (15, 4)] for seed in range(3)
        }:
            raise ValueError(f"incomplete cases for {variant}")
        summaries[variant] = {}
        for cutoff in ["2", "4", "all"]:

            def score(row):
                return row["scores"][str(row["N"]) if cutoff == "all" else cutoff]

            sums = [sum(score(r) for r in selected if r["seed"] == seed) for seed in range(3)]
            summaries[variant][cutoff] = {
                "sum_of_case_scores": mean_se(sums),
                "pooled_harmonic": float(len(selected) / sum(1 / score(r) for r in selected)),
                "cases": {
                    f"{n},{k}": mean_se([score(r) for r in selected if (r["N"], r["n"]) == (n, k)])
                    for n, k in [(10, 3), (10, 5), (15, 4)]
                },
            }
    for variant, result in summaries.items():
        for cutoff, entry in result.items():
            values = entry["sum_of_case_scores"]["values"]
            baseline = summaries["old"][cutoff]["sum_of_case_scores"]["values"]
            entry["paired_sum_change_vs_old"] = mean_se(np.array(values) - np.array(baseline))
    data = {
        "shots_per_basis": 10000,
        "seeds": [0, 1, 2],
        "noise": "Notebook calibration recipe; stochastic Pauli gate errors and asymmetric readout",
        "uncertainty": "SE across three calibration/shot seeds, not a hardware confidence interval",
        "summary": summaries,
        "records": records,
    }
    (root / "summary.json").write_text(json.dumps(data, indent=2, allow_nan=False))
    lines = [
        "| Constructor | D(10,3) | D(10,5) | D(15,4) | Sum |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for variant, result in summaries.items():
        row = result["all"]
        cells = [row["cases"][key] for key in ["10,3", "10,5", "15,4"]] + [
            row["sum_of_case_scores"]
        ]
        lines.append(
            f"| {variant} | " + " | ".join(f"{x['mean']:.4f} ± {x['se']:.4f}" for x in cells) + " |"
        )
    report = (
        "All X-correlator orders; sampled score mean ± SE over three seeds.\n\n"
        + "\n".join(lines)
        + "\n"
    )
    (root / "summary.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
