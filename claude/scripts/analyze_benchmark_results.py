"""Analyze matched finite DD/no-DD observations without changing recorded data."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from claude.benchmark_statistics import (  # noqa: E402
    _finite,
    case_statistics,
    has_complete_provenance,
    paired_aggregate,
    validate_declared_records,
)
from claude.output_paths import figure_root  # noqa: E402

DEFAULT_RESULTS = (
    Path(__file__).resolve().parents[2] / "benchmark_outputs/noisy_benchmark_results.json"
)
SCORE_DISPLAY_LIMITS = (0.0, 2.0)


def latest_results(root: Path | None = None) -> Path:
    """Find a current-run JSON, never substitute unavailable historical raw data."""
    root = root if root is not None else REPO / "benchmark_outputs"
    candidates = list((root / "runs").glob("*/noisy_benchmark_results.json"))
    if not candidates:
        raise FileNotFoundError(
            "No new run JSON exists. Historical raw data is unavailable; the original report and figure survive. Run a new experiment or pass an explicit results path."
        )
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


def load_results(path: Path) -> dict:
    """Read completed benchmark JSON; raise clear errors for missing/incomplete data."""
    if not path.exists():
        raise FileNotFoundError(f"results file not found: {path}")
    data = json.loads(path.read_text())
    if (
        not isinstance(data, dict)
        or not data.get("complete")
        or not isinstance(data.get("results"), dict)
    ):
        raise ValueError("expected completed benchmark data with a results mapping")
    validate_declared_records(data)
    return data


def _format(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.4g}"


def summarize(data: dict) -> str:
    """Return an honest paired comparison, sample counts, exclusions, and provenance caveats."""
    rows = case_statistics(data)
    aggregate = paired_aggregate(rows)
    statuses = Counter(
        record.get("score_status", "finite" if _finite(record) else "undefined")
        for record in data["results"].values()
    )
    modern = has_complete_provenance(data)
    lines = [
        "# Noisy benchmark report",
        "",
        f"Cases: {len(rows)}; records: {len(data['results'])}; statuses: {dict(statuses)}.",
        "Provenance: "
        + (
            "effective configuration, sources and runtime recorded."
            if modern
            else "UNVERIFIED / LEGACY — complete source/model fingerprint unavailable; interpret cautiously."
        ),
        "",
        "## Matched comparison",
        "",
        f"Common finite paired seeds across every case: {aggregate['n_pairs']}.",
        f"DD mean: {_format(aggregate['dd_mean'])}; no-DD mean: {_format(aggregate['no_dd_mean'])}.",
        f"DD minus no-DD: {_format(aggregate['difference'])}; paired standard error: {_format(aggregate['difference_se'])}.",
        "Standard error is estimated across paired seed means, not across different cases.",
        "",
        "| N | n | Paired seeds | Excluded | DD mean | no-DD mean | Difference | Paired SE |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['n']} | {row['k']} | {row['n_pairs']} | {row['excluded']} | "
            f"{_format(row['dd_mean'])} | {_format(row['no_dd_mean'])} | "
            f"{_format(row['difference'])} | {_format(row['difference_se'])} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "- Undefined and infinite official scores are reported explicitly and excluded from finite paired statistics.",
        "- A single seed does not estimate uncertainty. Plot SD bars describe dispersion, not a confidence interval.",
        "- The matched-score panel displays 0–2. Boundary triangles mark clipped means or SD bars; labels show means above 2. Official scores are not bounded by 2, and the table/raw data retain their full values.",
        "- Increasing shots reduces sampling variation; increasing noise seeds samples more physical realizations.",
        "- Between-case spread measures case heterogeneity and does not imply that more shots will reduce it.",
        "- These are results for the stated synthetic noise model and calibration; they do not establish a hardware-wide DD preference.",
        "- Maximum correlator size is a local experiment setting; the original challenge does not fix it.",
    ]
    return "\n".join(lines) + "\n"


def write_insight_plot(data: dict, path: Path) -> None:
    """Save paired scores in a 0–2 view with explicit overflow; retain full statistics.

    Mean/SD bars are visually clipped, never numerically capped. Boundary markers
    indicate clipped means or SD endpoints; overflowing means retain numeric labels.
    The difference panel keeps its own scale. Singleton/undefined cases are supported.
    """
    rows = case_statistics(data)
    valid = [row for row in rows if row["n_pairs"]]
    figure, axes = plt.subplots(
        2, 1, figsize=(max(9, len(valid) * 0.7), 7), constrained_layout=True
    )
    if valid:
        x = np.arange(len(valid))
        for key, label, offset, color in (
            ("dd", "DD", -0.19, "#2878b5"),
            ("no_dd", "no-DD", 0.19, "#e07a35"),
        ):
            positions = x + offset
            means = np.asarray([r[f"{key}_mean"] for r in valid], dtype=float)
            spread = np.asarray([r[f"{key}_std"] for r in valid], dtype=float)
            axes[0].bar(positions, means, 0.38, yerr=spread, label=label, color=color, capsize=3)
            # Undefined singleton SD does not hide an overflowing finite mean.
            finite_spread = np.where(np.isfinite(spread), spread, 0.0)
            for boundary, mask, marker in (
                (SCORE_DISPLAY_LIMITS[1], means + finite_spread > SCORE_DISPLAY_LIMITS[1], "^"),
                (SCORE_DISPLAY_LIMITS[0], means - finite_spread < SCORE_DISPLAY_LIMITS[0], "v"),
            ):
                axes[0].scatter(
                    positions[mask],
                    np.full(np.count_nonzero(mask), boundary),
                    marker=marker,
                    color=color,
                    s=30,
                    zorder=5,
                    clip_on=False,
                )
            for position, mean in zip(positions, means):
                if mean > SCORE_DISPLAY_LIMITS[1]:
                    axes[0].annotate(
                        f"{mean:.3g}",
                        (position, SCORE_DISPLAY_LIMITS[1]),
                        xytext=(0, -8),
                        textcoords="offset points",
                        ha="center",
                        va="top",
                        fontsize=8,
                        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.85},
                    )
        differences = np.array([r["difference"] for r in valid])
        axes[1].bar(x, differences, color=np.where(differences >= 0, "#2878b5", "#c94c4c"))
        labels = [f"D({r['n']},{r['k']})\nn={r['n_pairs']}" for r in valid]
        for axis in axes:
            axis.set_xticks(x, labels, rotation=45, ha="right")
        axes[0].legend()
    else:
        for axis in axes:
            axis.text(
                0.5, 0.5, "No finite paired observations", transform=axis.transAxes, ha="center"
            )
    axes[0].set_ylim(*SCORE_DISPLAY_LIMITS)
    axes[0].set_title(
        "Matched scores; bars show seed SD (singleton spread unestimated)\n"
        "View 0–2; triangles mark clipped means or SD bars; full values retained in report/data"
    )
    axes[0].set_ylabel("Official score — higher is better")
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_ylabel("DD minus no-DD")
    axes[1].set_xlabel("Case and finite paired sample count")
    for axis in axes:
        axis.grid(axis="y", alpha=0.2)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=160)
    plt.close(figure)


def main(path: Path | None = None, output_dir: Path | None = None) -> Path:
    """Write analysis in a separate folder, preserving historical reports and figures."""
    path = path if path is not None else latest_results()
    data = load_results(path)
    output_dir = output_dir if output_dir is not None else path.parent / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = summarize(data)
    dataset_id = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    figure_path = figure_root() / "benchmarks" / dataset_id / "noisy_benchmark_insights.png"
    write_insight_plot(data, figure_path)
    report += f"\n![Matched score comparison]({figure_path})\n"
    destination = output_dir / "noisy_benchmark_report.md"
    destination.write_text(report)
    print(report)
    print(f"[saved] {destination}")
    return destination


if __name__ == "__main__":
    plt.switch_backend("Agg")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path)
    main(parser.parse_args().path)
