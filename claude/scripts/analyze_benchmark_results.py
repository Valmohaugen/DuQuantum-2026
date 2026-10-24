"""Summarize and interpret a saved noisy benchmark run.

Usage:
    python -u claude/scripts/analyze_benchmark_results.py
    python -u claude/scripts/analyze_benchmark_results.py path/to/results.json

The script prints a compact report and writes a Markdown copy next to the JSON.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DEFAULT_RESULTS = Path(__file__).resolve().parents[2] / "benchmark_outputs" / "noisy_benchmark_results.json"


def load_results(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"results file not found: {path}")
    data = json.loads(path.read_text())
    if not data.get("complete", False):
        raise RuntimeError("benchmark results are incomplete; use the checkpoint file or rerun the benchmark")
    return data


def summarize(data: dict) -> str:
    cases: dict[tuple[int, int], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for key, result in data["results"].items():
        n_text, k_text, _seed_text, mode = key.split(",")
        cases[(int(n_text), int(k_text))][mode].append(result)

    lines = [
        "# Noisy Benchmark Report",
        "",
        f"Cases analyzed: {len(cases)}",
        f"Completed scores: {len(data['results'])}",
        "",
        "## Aggregate result",
        "",
    ]
    aggregate = data["aggregate"]
    dd_mean = aggregate["dd_mean"]
    no_dd_mean = aggregate["no_dd_mean"]
    difference = dd_mean - no_dd_mean
    winner = "DD" if difference > 0 else "no-DD" if difference < 0 else "tie"
    lines.extend(
        [
            f"- DD: {dd_mean:.3f} +/- {aggregate['dd_std']:.3f}",
            f"- no-DD: {no_dd_mean:.3f} +/- {aggregate['no_dd_std']:.3f}",
            f"- Difference (DD - no-DD): {difference:+.3f}",
            f"- Aggregate winner: {winner}",
            "",
            "The aggregate values are averages of per-case means. The very large spread indicates "
            "that scores should be compared per case, not only by one pooled total.",
            "",
            "## Per-case comparison",
            "",
            "| N | n | Moments | DD mean +/- std | no-DD mean +/- std | Difference | Winner |",
            "|---:|---:|---:|---:|---:|---:|:---|",
        ]
    )

    wins = {"DD": 0, "no-DD": 0, "tie": 0}
    differences: list[tuple[float, tuple[int, int]]] = []
    for case in sorted(cases):
        values = cases[case]
        dd = values.get("dd", [])
        no_dd = values.get("no-dd", [])
        if not dd or not no_dd:
            continue
        dd_scores = [float(item["score"]) for item in dd]
        no_dd_scores = [float(item["score"]) for item in no_dd]
        dd_avg = mean(dd_scores)
        no_dd_avg = mean(no_dd_scores)
        delta = dd_avg - no_dd_avg
        case_winner = "DD" if delta > 0 else "no-DD" if delta < 0 else "tie"
        wins[case_winner] += 1
        differences.append((delta, case))
        dd_spread = stdev(dd_scores) if len(dd_scores) > 1 else 0.0
        no_dd_spread = stdev(no_dd_scores) if len(no_dd_scores) > 1 else 0.0
        moments = int(dd[0]["moments"])
        lines.append(
            f"| {case[0]} | {case[1]} | {moments} | {dd_avg:.3f} +/- {dd_spread:.3f} "
            f"| {no_dd_avg:.3f} +/- {no_dd_spread:.3f} | {delta:+.3f} | {case_winner} |"
        )

    strongest_gain = max(differences, default=(0.0, (0, 0)))
    strongest_loss = min(differences, default=(0.0, (0, 0)))
    lines.extend(
        [
            "",
            "## Insights",
            "",
            f"- DD wins {wins['DD']} cases; no-DD wins {wins['no-DD']}; ties: {wins['tie']}.",
            f"- Strongest DD improvement: D^{strongest_gain[1][0]}_{strongest_gain[1][1]} "
            f"({strongest_gain[0]:+.3f}).",
            f"- Strongest DD regression: D^{strongest_loss[1][0]}_{strongest_loss[1][1]} "
            f"({strongest_loss[0]:+.3f}).",
            "- A large standard deviation means more seeds or more shots are needed before changing the default.",
            "- Use the per-case winners to design conditional DD rather than enabling DD globally.",
            "",
            "## Recommended decision",
            "",
        ]
    )
    if difference < 0:
        lines.append("The current aggregate favors no-DD. Keep the default unchanged until a larger seed set confirms it.")
    elif difference > 0:
        lines.append("The current aggregate favors DD. Confirm the result with more seeds before making DD the default.")
    else:
        lines.append("The current aggregate is tied. Collect more seeds before changing the default.")
    return "\n".join(lines) + "\n"


def write_insight_plot(data: dict, path: Path) -> None:
    """Write a PNG comparing DD and no-DD scores with uncertainty bars."""
    cases: dict[tuple[int, int], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for key, result in data["results"].items():
        n_text, k_text, _seed_text, mode = key.split(",")
        cases[(int(n_text), int(k_text))][mode].append(result)

    ordered = sorted(cases)
    labels = [f"D{n},{k}" for n, k in ordered]
    dd_means = [mean([float(item["score"]) for item in cases[case]["dd"]]) for case in ordered]
    no_dd_means = [mean([float(item["score"]) for item in cases[case]["no-dd"]]) for case in ordered]
    dd_std = [stdev([float(item["score"]) for item in cases[case]["dd"]]) for case in ordered]
    no_dd_std = [stdev([float(item["score"]) for item in cases[case]["no-dd"]]) for case in ordered]
    deltas = np.asarray(dd_means) - np.asarray(no_dd_means)
    x = np.arange(len(ordered))

    aggregate = data["aggregate"]
    figure, (score_axis, delta_axis) = plt.subplots(
        2, 1, figsize=(max(12, len(labels) * 0.7), 8), height_ratios=(2, 1), constrained_layout=True
    )
    width = 0.38
    score_axis.bar(x - width / 2, dd_means, width, yerr=dd_std, capsize=3, label="DD", color="#2878b5")
    score_axis.bar(x + width / 2, no_dd_means, width, yerr=no_dd_std, capsize=3, label="no-DD", color="#e07a35")
    score_axis.set_ylabel("Official score")
    score_axis.set_title(
        f"Dicke benchmark: DD {aggregate['dd_mean']:.2f} vs no-DD {aggregate['no_dd_mean']:.2f}"
    )
    score_axis.set_xticks(x, labels)
    score_axis.legend()
    score_axis.grid(axis="y", alpha=0.25)

    delta_axis.bar(x, deltas, color=np.where(deltas >= 0, "#2878b5", "#c94c4c"))
    delta_axis.axhline(0, color="black", linewidth=0.8)
    delta_axis.set_ylabel("DD - no-DD")
    delta_axis.set_xlabel("Case (N, n)")
    delta_axis.set_xticks(x, labels, rotation=45, ha="right")
    delta_axis.grid(axis="y", alpha=0.25)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_RESULTS
    data = load_results(path)
    report = summarize(data)
    report_path = path.with_name("noisy_benchmark_report.md")
    plot_path = path.with_name("noisy_benchmark_insights.png")
    report_path.write_text(report)
    write_insight_plot(data, plot_path)
    print(report)
    print(f"[saved] report: {report_path}")
    print(f"[saved] plot: {plot_path}")


if __name__ == "__main__":
    main()
