"""Draw the publication figures from figures/data/ (see compute_data.py to regenerate the data).

    python figures/make_figures.py          # all figures -> figures/*.pdf and figures/*.png

IEEE sizing: single column 3.5 in, double column 7.16 in; 8 pt sans text; PDFs embed TrueType
(Type 42) fonts; PNGs are 600 dpi. Colors follow one validated palette: categorical slots
blue / orange / aqua, a blue sequential ramp and an orange ramp stepped to the same lightness.
"""
import collections
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import patheffects  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, Normalize  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

SINGLE, DOUBLE = 3.5, 7.16  # IEEE column widths, inches

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
#sequential ramps, light -> dark; orange steps share the blue steps' OKLCH lightness
BLUE_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
ORANGE_RAMP = ["#ec9b7e", "#e07148", "#cb4801", "#9e3703", "#742702", "#611e00"]
BLUES = LinearSegmentedColormap.from_list("blues", BLUE_RAMP)
ORANGES = LinearSegmentedColormap.from_list("oranges", ORANGE_RAMP)
HALO = [patheffects.withStroke(linewidth=2.2, foreground=SURFACE)]

LAYOUT_CASE = (10, 5)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],
    "mathtext.fontset": "dejavusans",
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelcolor": INK2,
    "ytick.labelcolor": INK2,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "grid.color": GRID,
    "grid.linewidth": 0.5,
    "grid.linestyle": "-",
    "lines.linewidth": 1.25,
    "legend.frameon": False,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "savefig.dpi": 600,
    "figure.dpi": 150,
})


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(HERE / f"{name}.{ext}", facecolor=SURFACE)
    plt.close(fig)
    w, h = fig.get_size_inches()
    print(f"figures/{name}.pdf/.png  {w:.2f} x {h:.2f} in")


def panel_label(ax, text, x=-0.02, y=1.02):
    ax.text(x, y, text, transform=ax.transAxes, fontsize=8, fontweight="bold", color=INK,
            ha="right", va="bottom")


def read_csv(name):
    with open(DATA / name) as fh:
        return [{k: (float(v) if v.replace(".", "", 1).replace("-", "", 1).replace("e", "", 1).isdigit() else v)
                 for k, v in row.items()} for row in csv.DictReader(fh)]


#----------------------------------------------------------------------------- chip maps (figs 1, 2)
def cz_uses(circuit):
    uses = collections.Counter()
    for moment in circuit:
        for op in moment:
            if op[0] == "cz":
                uses[tuple(sorted([tuple(op[1:3]), tuple(op[3:5])]))] += 1
    return uses


def first_cz_moment(circuit):
    first = {}
    for t, moment in enumerate(circuit, start=1):
        for op in moment:
            if op[0] == "cz":
                for q in (tuple(op[1:3]), tuple(op[3:5])):
                    first.setdefault(q, t)
    return first


def chip_figure(chip, layout, node_values, node_label, node_norm, name, extend="neither"):
    fig = plt.figure(figsize=(SINGLE, 3.55), layout="constrained")
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 0.045], hspace=0.02, wspace=0.08)
    ax = fig.add_subplot(gs[0, :])
    dropped = {tuple(q) for q in chip["dropped_qubits"]}
    dropped_c = {tuple(map(tuple, c)) for c in chip["dropped_couplers"]}
    xy = lambda q: (q[1], q[0])

    segs = [[xy(a), xy(b)] for a, b in chip["couplers"] if (tuple(a), tuple(b)) not in dropped_c]
    ax.add_collection(LineCollection(segs, colors=AXIS, linewidths=0.6, zorder=1))
    live = [q for q in chip["qubits"] if tuple(q) not in dropped]
    ax.scatter([q[1] for q in live], [q[0] for q in live], s=5, color=MUTED, linewidths=0, zorder=2)
    if dropped:
        ax.scatter([q[1] for q in dropped], [q[0] for q in dropped], s=12, marker="x", color=MUTED,
                   linewidths=0.6, zorder=2)

    uses = cz_uses(layout["circuit"])
    edge_norm = Normalize(1, max(uses.values()))
    order = sorted(uses, key=uses.get)
    ax.add_collection(LineCollection([[xy(a), xy(b)] for a, b in order], colors=BLUES(edge_norm([uses[e] for e in order])),
                                     linewidths=3.0, capstyle="round", zorder=3))
    sel = [tuple(q) for q in layout["qubits"]]
    ax.scatter([q[1] for q in sel], [q[0] for q in sel], s=46, c=[node_values[q] for q in sel], cmap=ORANGES,
               norm=node_norm, edgecolors=SURFACE, linewidths=1.2, zorder=4)
    #label each qubit on a side with no selected neighbour: above, below, left, then right
    taken = set(sel)
    sides = (((-1, 0), (0, 5.2), "center", "bottom"), ((1, 0), (0, -5.2), "center", "top"),
             ((0, -1), (-5.2, 0), "right", "center"), ((0, 1), (5.2, 0), "left", "center"))
    for q in sel:
        _, off, ha, va = next((s for s in sides if (q[0] + s[0][0], q[1] + s[0][1]) not in taken), sides[0])
        ax.annotate(f"{q[0]},{q[1]}", xy(q), xytext=off, textcoords="offset points", ha=ha,
                    va=va, fontsize=7, color=INK, zorder=5, path_effects=HALO)

    ax.set_xlim(-0.7, 14.7)
    ax.set_ylim(12.7, -0.7)
    ax.set_aspect("equal")
    ax.set_xticks(range(0, 15, 2))
    ax.set_yticks(range(0, 13, 2))
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")
    ax.spines[["left", "bottom"]].set_visible(False)
    ax.tick_params(length=0)

    for col, cmap, norm, label, ext in ((0, BLUES, edge_norm, "CZ gates per coupler", "neither"),
                                        (1, ORANGES, node_norm, node_label, extend)):
        cax = fig.add_subplot(gs[1, col])
        cb = fig.colorbar(plt.cm.ScalarMappable(norm, cmap), cax=cax, orientation="horizontal", extend=ext)
        cb.outline.set_visible(False)
        cb.ax.tick_params(length=2, width=0.6, color=MUTED)
        cb.set_label(label, labelpad=2)
        if norm is edge_norm or isinstance(norm.vmax, int):
            cb.ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True, nbins=5))
    save(fig, name)


def fig_layouts():
    chip = json.loads((DATA / "chip.json").read_text())
    layouts = {(d["N"], d["n"], d["entry"]): d for d in json.loads((DATA / "layouts.json").read_text())}
    N, n = LAYOUT_CASE

    #main: shade qubits by expected readout error, (1 - n/N) e01 + (n/N) e10; the scale spans the
    #working chip (minimum to 95th percentile) so the chosen qubits read against the alternatives
    w = n / N
    readout = {(r, c): (1 - w) * e0 + w * e1 for r, c, e0, e1 in chip["readout"]}
    vals = np.array(list(readout.values()))
    norm = Normalize(vals.min() * 1e3, np.percentile(vals, 95) * 1e3)
    chip_figure(chip, layouts[N, n, "main"], {q: v * 1e3 for q, v in readout.items()},
                r"Readout error ($10^{-3}$)", norm, "fig1_layout_main", extend="max")

    #bonus: no calibration; shade qubits by the moment of their first CZ (how the entanglement spreads)
    bonus = layouts[N, n, "bonus"]
    first = first_cz_moment(bonus["circuit"])
    chip_figure(chip, bonus, first, "Moment of first CZ", Normalize(1, max(first.values())), "fig2_layout_bonus")


#----------------------------------------------------------------------------- bonus depth (fig 3)
def fig_bonus():
    rows = read_csv("bonus_cases.csv")
    Ns, ns = range(2, 16), range(1, 8)
    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE, 3.3), layout="constrained")
    for ax, key, label, fmt, tag in ((axes[0], "moments", "Circuit depth (moments)", "{:.0f}", "(a)"),
                                     (axes[1], "contribution", r"Score contribution $Nn/\mathrm{depth}$", "{:.2f}", "(b)")):
        grid = np.full((len(Ns), len(ns)), np.nan)
        for r in rows:
            grid[int(r["N"]) - 2, int(r["n"]) - 1] = r[key]
        norm = Normalize(np.nanmin(grid), np.nanmax(grid))
        im = ax.imshow(np.ma.masked_invalid(grid), cmap=BLUES, norm=norm, aspect="auto",
                       extent=(0.5, 7.5, 15.5, 1.5))
        for (i, j), v in np.ndenumerate(grid):
            if not np.isnan(v):
                ax.text(j + 1, i + 2, fmt.format(v), ha="center", va="center", fontsize=7,
                        color=SURFACE if norm(v) > 0.45 else INK)
        ax.set_xticks(list(ns))
        ax.set_yticks(list(Ns))
        ax.set_xlabel(r"Excitations $n$")
        ax.set_ylabel(r"Qubits $N$")
        ax.spines[["left", "bottom"]].set_visible(False)
        ax.tick_params(length=0)
        cb = fig.colorbar(im, ax=ax, shrink=0.85, pad=0.02)
        cb.outline.set_visible(False)
        cb.ax.tick_params(length=2, width=0.6, color=MUTED)
        cb.set_label(label)
        panel_label(ax, tag)
    save(fig, "fig3_bonus_depth")


#----------------------------------------------------------------------------- score history (fig 4)
def fig_progression():
    import datetime as dt

    rows = read_csv("progression.csv")
    end = dt.datetime(2026, 10, 25, 10, 45)
    fig, axes = plt.subplots(2, 1, figsize=(SINGLE, 3.6), sharex=True, layout="constrained")
    for ax, metric, label, fmt, tag in ((axes[0], "bonus", "Bonus score", "{:.3f}", "(a)"),
                                        (axes[1], "main_proxy", "Main score (local model)", "{:.3f}", "(b)")):
        pts = sorted((dt.datetime.strptime(r["time_edt"], "%Y-%m-%d %H:%M"), r["value"])
                     for r in rows if r["metric"] == metric)
        t = [p[0] for p in pts] + [end]
        v = [p[1] for p in pts] + [pts[-1][1]]
        ax.step(t, v, where="post", color=BLUE, linewidth=1.25)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "o", color=BLUE, markersize=4,
                markeredgecolor=SURFACE, markeredgewidth=0.8)
        ax.annotate(fmt.format(pts[-1][1]), (end, pts[-1][1]), xytext=(0, 4), textcoords="offset points",
                    ha="right", va="bottom", fontsize=8, color=INK)
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo, hi + 0.12 * (hi - lo))
        ax.set_ylabel(label)
        ax.grid(axis="y")
        panel_label(ax, tag, x=-0.17)
    axes[1].xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%H:%M"))
    axes[1].set_xlabel("Time, 24–25 Oct 2026 (EDT)")
    save(fig, "fig4_score_history")


#----------------------------------------------------------------------------- main scores (fig 5)
def fig_main_scores():
    rows = read_csv("main_scores.csv")
    labels = [f"D({int(r['N'])},{int(r['n'])})" for r in rows]
    y = np.arange(len(rows))[::-1]
    fig, ax = plt.subplots(figsize=(SINGLE, 3.6), layout="constrained")
    tot, ideal = sum(r["expected_score"] for r in rows), sum(r["ideal_score"] for r in rows)
    ax.barh(y, [r["expected_score"] for r in rows], height=0.62, color=BLUE,
            label=f"Our circuits, noise model (sum {tot:.2f}, {100 * tot / ideal:.0f}% of limit)")
    ax.plot([r["ideal_score"] for r in rows], y, "|", color=INK, markersize=9, markeredgewidth=1.4,
            label=f"Noiseless limit, 10,000 shots (sum {ideal:.2f})")
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Expected score per case, 1/(Z + X)")
    ax.grid(axis="x")
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)
    fig.legend(loc="outside upper left", handlelength=1.2)
    save(fig, "fig5_main_scores")


#----------------------------------------------------------------------------- resources (fig 6)
def fig_resources():
    rows = read_csv("resources.csv")
    series = (("main", "Ours, main", BLUE, "o"), ("bonus", "Ours, bonus", ORANGE, "s"),
              ("baseline", "Routed Bärtschi–Eidenbenz", AQUA, "^"))
    fig, axes = plt.subplots(2, 1, figsize=(SINGLE, 4.0), sharex=True, layout="constrained")
    for ax, key, label, tag in ((axes[0], "cz", "CZ gates", "(a)"), (axes[1], "moments", "Depth (moments)", "(b)")):
        for entry, name, color, marker in series:
            pts = sorted((r["N"], r[key]) for r in rows if r["entry"] == entry)
            ax.plot([p[0] for p in pts], [p[1] for p in pts], marker=marker, color=color, markersize=4,
                    markeredgecolor=SURFACE, markeredgewidth=0.6, label=name)
        ax.set_yscale("log")
        ax.set_ylabel(label)
        ax.grid(axis="y", which="major")
        panel_label(ax, tag, x=-0.15)
    axes[0].legend(loc="upper left", handlelength=1.6)
    axes[1].set_xlabel(r"Qubits $N$ (with $n = \lfloor N/2 \rfloor$)")
    axes[1].set_xticks(range(2, 16))
    save(fig, "fig6_resources")


FIGURES = dict(layouts=fig_layouts, bonus=fig_bonus, progression=fig_progression,
               scores=fig_main_scores, resources=fig_resources)

if __name__ == "__main__":
    import sys

    for name in sys.argv[1:] or FIGURES:
        FIGURES[name]()
