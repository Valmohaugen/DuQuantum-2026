"""Render scientific diagnostic figures without changing a notebook's global backend."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import BoundaryNorm, ListedColormap, Normalize
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from claude.diagnostic_metrics import mean_interval

COLORS = {"ideal": "#333333", "dd": "#0072B2", "no-dd": "#D55E00", "phase": "#009E73"}
FIGURE_SIZE = (12, 7)
WIDE_SIZE = (13, 6)
PLOT_DPI = 180
STYLE = {
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titlesize": 11,
    "legend.fontsize": 9,
    "savefig.facecolor": "white",
    "pdf.fonttype": 42,
}


def _figure(size: tuple = FIGURE_SIZE) -> Figure:
    figure = Figure(figsize=size, layout="constrained")
    FigureCanvasAgg(figure)
    return figure


def _save(figure: Figure, root: Path, name: str) -> str:
    for suffix in (".png", ".pdf"):
        figure.savefig(root / (name + suffix), dpi=PLOT_DPI)
    figure.clear()
    return name


def _state(data: dict, root: Path) -> str:
    state = data["state"]
    n, k = state["n"], state["k"]
    figure = _figure()
    axes = figure.subplots(2, 2)
    x = np.arange(len(state["basis_indices"]))
    labels = [format(index, f"0{n}b") for index in state["basis_indices"]]
    axes[0, 0].bar(x, state["aligned_real"], color=COLORS["dd"], label="aligned real amplitude")
    axes[0, 0].scatter(
        x, state["aligned_imag"], color=COLORS["phase"], marker="x", label="imaginary amplitude"
    )
    axes[0, 0].axhline(
        state["target_amplitude"], color=COLORS["ideal"], ls="--", label="ideal amplitude"
    )
    axes[0, 0].set(ylabel="Amplitude", title="Equal magnitudes and signs are both required")
    axes[0, 0].legend(loc="lower left")
    axes[0, 1].axis("off")
    text = (
        f"D({n},{k})   dimension = {state['dimension']}\n\n"
        f"Fidelity                  {state['fidelity']:.12f}\n"
        f"Infidelity                {state['infidelity']:.3e}\n"
        f"Leakage                   {state['leakage']:.3e}\n"
        f"Norm squared              {state['norm_squared']:.12f}\n"
        f"Max amplitude error       {state['max_amplitude_error']}\n\n"
        "One common global phase is removed.\nRelative phases remain part of the test."
    )
    axes[0, 1].text(0.02, 0.9, text, va="top", fontfamily="monospace", fontsize=10)
    phases = np.array([np.nan if value is None else value for value in state["phase_errors_rad"]])
    axes[1, 0].plot(x, phases, "o", color=COLORS["phase"])
    axes[1, 0].axhline(0, color="gray", lw=0.7)
    axes[1, 0].set(ylabel="Phase error [rad]", title="Relative phase after global alignment")
    error = np.asarray(state["aligned_real"]) - state["target_amplitude"]
    axes[1, 1].bar(x, error, color=COLORS["dd"], label="real residual")
    axes[1, 1].scatter(
        x, state["aligned_imag"], color=COLORS["phase"], marker="x", label="imaginary residual"
    )
    axes[1, 1].set(ylabel="Amplitude residual", title="Residual scale exposes numerical errors")
    axes[1, 1].legend()
    for axis in (axes[0, 0], axes[1, 0], axes[1, 1]):
        axis.set_xticks(x, labels, rotation=90, fontsize=8)
        axis.grid(axis="y", alpha=0.2)
    for axis in axes[1]:
        axis.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
        axis.set_xlabel("Target-weight computational basis state")
    figure.suptitle(f"Exact-state validation: D({n},{k})", fontsize=15, fontweight="bold")
    return _save(figure, root, "01_exact_state")


def _distributions(data: dict, root: Path) -> str:
    figure = _figure()
    axes = figure.subplots(2, 2)
    n, k = data["state"]["n"], data["state"]["k"]
    weights = np.arange(n + 1)
    target = np.zeros(n + 1)
    target[k] = 1
    axes[0, 0].bar(weights - 0.25, target, 0.25, label="ideal", color=COLORS["ideal"])
    indices = data["state"]["basis_indices"]
    x = np.arange(len(indices))
    axes[0, 1].axhline(1 / len(indices), color=COLORS["ideal"], ls="--", label="ideal uniform")
    for offset, mode in ((0.0, "dd"), (0.25, "no-dd")):
        row = data["distributions"][mode]
        axes[0, 0].bar(
            weights + offset,
            row["weight_probabilities"],
            0.25,
            color=COLORS[mode],
            label=f"{mode}, leakage {row['leakage']:.3f}",
        )
        mass = row["subspace_probability"]
        if mass > 1e-12:
            axes[0, 1].plot(
                x,
                np.asarray(row["z_probabilities"])[indices] / mass,
                "o-",
                color=COLORS[mode],
                label=mode,
                ms=4,
            )
        axes[1, 0].plot(row["x_orders"], row["x_observed"], "o-", color=COLORS[mode], label=mode)
        axes[1, 1].bar(
            np.asarray(row["x_orders"]) + (offset - 0.125),
            row["x_residuals"],
            0.25,
            color=COLORS[mode],
            label=mode,
        )
    example = data["distributions"]["dd"]
    axes[1, 0].plot(example["x_orders"], example["x_expected"], "k--", label="ideal")
    axes[0, 0].set(
        xlabel="Measured Hamming weight",
        ylabel="Probability",
        title="Leakage out of the requested weight",
    )
    axes[0, 0].set_xticks(weights)
    axes[0, 1].set(
        xlabel="State within requested weight",
        ylabel="Conditional probability",
        title="Nonuniformity conditioned on correct weight",
    )
    axes[0, 1].set_xticks(x, [format(i, f"0{n}b") for i in indices], rotation=90, fontsize=8)
    axes[1, 0].set(
        xlabel="X-correlator order",
        ylabel="Average correlator",
        title="Coherence visible in the X basis",
    )
    axes[1, 1].set(
        xlabel="X-correlator order",
        ylabel="Observed minus ideal",
        title="Signed X-correlator residuals",
    )
    axes[1, 1].axhline(0, color="gray", lw=0.8)
    for axis in axes[1]:
        axis.set_xticks(example["x_orders"])
    for axis in axes.flat:
        axis.legend(fontsize=8)
        axis.grid(axis="y", alpha=0.2)
    figure.suptitle(
        f"Noise diagnostics for D({n},{k}) — exact probabilities of the sampled ensemble",
        fontsize=14,
        fontweight="bold",
    )
    return _save(figure, root, "02_distributions")


def _layout(data: dict, root: Path) -> str:
    figure = _figure(WIDE_SIZE)
    axes = figure.subplots(1, 2)
    for a, b in data["device"]["pairs"]:
        axes[0].plot([a[1], b[1]], [-a[0], -b[0]], color="#DDDDDD", lw=0.7, zorder=0)
    usable = {tuple(q) for q in data["device"]["usable_qubits"]}
    for row, col in data["device"]["qubits"]:
        axes[0].plot(
            col, -row, "o" if (row, col) in usable else "x", color="#BBBBBB", ms=3, zorder=1
        )
    costs = data["circuits"]["dd"]
    maximum = max([r["cz_count"] for r in costs["couplers"]], default=1)
    norm = Normalize(vmin=0, vmax=maximum)
    for edge in costs["couplers"]:
        a, b = edge["a"], edge["b"]
        uses = edge["cz_count"]
        axes[0].plot(
            [a[1], b[1]],
            [-a[0], -b[0]],
            color=mpl.colormaps["Purples"](norm(uses)),
            lw=2 + 4 * uses / maximum,
            zorder=2,
        )
    qrows = costs["qubits"]
    nodes = axes[0].scatter(
        [r["col"] for r in qrows],
        [-r["row"] for r in qrows],
        c=[r["readout_proxy"] for r in qrows],
        cmap="Oranges",
        edgecolors="black",
        s=95,
        zorder=3,
    )
    figure.colorbar(
        nodes,
        ax=axes[0],
        orientation="horizontal",
        label="Readout error proxy on selected qubits",
        shrink=0.8,
    )
    for q in qrows:
        axes[0].annotate(
            q["label"], (q["col"], -q["row"]), xytext=(5, 7), textcoords="offset points", fontsize=8
        )
    if costs["couplers"]:
        figure.colorbar(
            mpl.cm.ScalarMappable(norm=norm, cmap="Purples"),
            ax=axes[0],
            label="CZ uses on selected edge",
            shrink=0.75,
        )
    axes[0].set_aspect("equal")
    axes[0].set(
        xlabel="Willow column",
        ylabel="Negative Willow row",
        title="Selected layout and actual coupler use",
    )
    x = np.arange(len(qrows))
    twin = axes[1].twinx()
    for shift, mode in ((-0.18, "dd"), (0.18, "no-dd")):
        row = data["circuits"][mode]
        axes[1].bar(
            x + shift,
            [q["oneq_count"] for q in row["qubits"]],
            0.36,
            color=COLORS[mode],
            label=f"{mode}: 1q gates",
        )
        twin.plot(
            x,
            [q["idle_ns"] / 1000 for q in row["qubits"]],
            "o-" if mode == "dd" else "s--",
            color=COLORS["phase"] if mode == "dd" else "#777777",
            label=f"{mode}: idle time",
        )
    axes[1].set_xticks(x, [q["label"] for q in qrows], rotation=35)
    axes[1].set(
        xlabel="Physical qubit [row,col]",
        ylabel="Single-qubit gate count",
        title="Pulse overhead and idle opportunities",
    )
    twin.set_ylabel("Idle time [µs]")
    handles, labels = axes[1].get_legend_handles_labels()
    h2, l2 = twin.get_legend_handles_labels()
    axes[1].legend(handles + h2, labels + l2, fontsize=8, loc="upper left")
    figure.suptitle(
        "Circuit placement and resource use — error sums are heuristics, not fidelities",
        fontsize=14,
        fontweight="bold",
    )
    return _save(figure, root, "03_layout_and_cost")


def _schedule(data: dict, root: Path) -> str:
    figure = _figure((12, 5))
    axes = figure.subplots(2, 1)
    cmap = ListedColormap(["#F1F3F5", COLORS["dd"], COLORS["no-dd"]])
    norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3)
    for axis, mode in zip(axes, ("no-dd", "dd")):
        row = data["circuits"][mode]
        edges = np.r_[0, np.cumsum(row["moment_durations_ns"])] / 1000
        if row["moments"]:
            axis.pcolormesh(
                edges,
                np.arange(len(row["qubits"]) + 1),
                row["schedule_types"],
                cmap=cmap,
                norm=norm,
                shading="flat",
            )
        else:
            axis.text(0.5, 0.5, "No gates required", transform=axis.transAxes, ha="center")
        axis.set_yticks(np.arange(len(row["qubits"])) + 0.5, [q["label"] for q in row["qubits"]])
        axis.set(
            xlabel="Model time [µs]",
            ylabel="Qubit [row,col]",
            title=f"{mode}: {row['moments']} moments, {row['oneq_count']} 1q gates, {row['cz_count']} CZ",
        )
    figure.legend(
        handles=[
            Patch(color=cmap(i), label=label)
            for i, label in enumerate(("idle", "single-qubit", "CZ"))
        ],
        loc="outside lower center",
        ncol=3,
    )
    figure.suptitle(
        "Native schedules: idle slots, one-qubit activity and CZ layers",
        fontsize=14,
        fontweight="bold",
    )
    return _save(figure, root, "04_schedule")


def _resources(data: dict, root: Path) -> str:
    figure = _figure()
    axes = figure.subplots(2, 2)
    columns = [
        ("cz_count", "CZ count"),
        ("moments", "Moments"),
        ("gate_error_proxy", "Σ gate count × calibrated error"),
        ("seconds", "Construction time [s]"),
    ]
    for family, color in (("W", COLORS["dd"]), ("balanced", COLORS["no-dd"])):
        rows = [row for row in data["resources"] if row["family"] == family]
        for axis, (column, label) in zip(axes.flat, columns):
            y = [
                row[column] if row["status"] == "supported" or column == "seconds" else np.nan
                for row in rows
            ]
            axis.plot([row["n"] for row in rows], y, "o-", color=color, label=family)
            axis.set(xlabel="Requested qubits N", ylabel=label)
            axis.grid(alpha=0.2)
        failed = [row for row in rows if row["status"] != "supported"]
        if failed:
            axes[1, 1].scatter(
                [row["n"] for row in failed],
                [row["seconds"] for row in failed],
                marker="x",
                s=80,
                color="red",
                label=f"{family}: unsupported",
            )
    axes[0, 0].set_yscale("log")
    axes[1, 0].set_yscale("log")
    axes[1, 1].set_yscale("log")
    axes[0, 1].axhline(1750, color="red", ls="--", label="1,750-moment limit")
    for axis in axes.flat:
        axis.legend(fontsize=8)
    figure.suptitle(
        "Scaling and coverage — large cases are structurally checked, not state-vector simulated",
        fontsize=13,
        fontweight="bold",
    )
    return _save(figure, root, "05_resource_scaling")


def _sensitivity(data: dict, root: Path) -> str:
    figure = _figure((12, 4.5))
    axes = figure.subplots(1, 2)
    for mode in ("dd", "no-dd"):
        rows = [row for row in data["sensitivity"] if row["mode"] == mode]
        x = [row["detuning_khz"] for row in rows]
        axes[0].plot(x, [row["leakage"] for row in rows], "o-", color=COLORS[mode], label=mode)
        axes[1].plot(x, [row["x_rms_error"] for row in rows], "o-", color=COLORS[mode], label=mode)
    axes[0].set(
        ylabel="Probability outside target weight", title="Detuning can change final populations"
    )
    axes[1].set(
        ylabel="RMS average X-correlator residual", title="Coherence error across correlator orders"
    )
    for axis in axes:
        axis.set_xlabel("Detuning standard deviation [kHz]")
        axis.grid(alpha=0.2)
        axis.legend()
    figure.suptitle(
        f"Fixed {data['noise']['n_realizations']}-realization ensemble; no measurement shot noise",
        fontsize=14,
        fontweight="bold",
    )
    return _save(figure, root, "06_noise_sensitivity")


def _paired(data: dict, root: Path) -> str:
    rows = data["comparison"]["cases"]
    figure = _figure()
    axes = figure.subplots(2, 1)
    labeled_modes: set[str] = set()
    for i, row in enumerate(rows):
        for offset, mode, key in ((-0.14, "dd", "dd_scores"), (0.14, "no-dd", "no_dd_scores")):
            values = row[key]
            if values:
                jitter = np.linspace(-0.06, 0.06, len(values))
                axes[0].scatter(
                    i + offset + jitter,
                    values,
                    color=COLORS[mode],
                    alpha=0.6,
                    s=20,
                    label=mode if mode not in labeled_modes else None,
                )
                labeled_modes.add(mode)
                axes[0].plot(i + offset, np.mean(values), "_", color=COLORS[mode], ms=18, mew=3)
        differences = np.asarray(row["dd_scores"]) - np.asarray(row["no_dd_scores"])
        interval = mean_interval(differences)
        if len(differences):
            axes[1].scatter(
                i + np.linspace(-0.12, 0.12, len(differences)),
                differences,
                color="#888888",
                alpha=0.6,
                s=18,
            )
            if interval["lower"] is not None:
                axes[1].errorbar(
                    i,
                    interval["mean"],
                    yerr=[
                        [interval["mean"] - interval["lower"]],
                        [interval["upper"] - interval["mean"]],
                    ],
                    fmt="o",
                    color=COLORS["dd"],
                    capsize=4,
                )
            else:
                axes[1].plot(i, interval["mean"], "o", color=COLORS["dd"])
    labels = [f"D({r['n']},{r['k']})\npairs {r['n_pairs']}, excluded {r['excluded']}" for r in rows]
    for axis in axes:
        axis.set_xticks(np.arange(len(rows)), labels, fontsize=8)
        axis.grid(axis="y", alpha=0.2)
    axes[0].set(ylabel="Official score", title="Individual matched observations and mean markers")
    if any(row["n_pairs"] for row in rows):
        finite_scores = [
            value for row in rows for key in ("dd_scores", "no_dd_scores") for value in row[key]
        ]
        if min(finite_scores) > 0:
            axes[0].set_yscale("log")
            axes[0].set_ylabel("Official score [log scale]")
        axes[0].legend()
    else:
        for axis in axes:
            axis.text(
                0.5,
                0.5,
                "No finite matched observations; uncertainty unavailable",
                transform=axis.transAxes,
                ha="center",
            )
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].set(
        ylabel="DD minus no-DD", title="Paired differences and approximate 95% Student-t intervals"
    )
    figure.suptitle(
        "Seed variability and paired DD comparison — model-specific, small-sample intervals",
        fontsize=14,
        fontweight="bold",
    )
    return _save(figure, root, "07_paired_scores")


def _convergence(data: dict, root: Path) -> str:
    aggregate = data["comparison"]["aggregate"]
    figure = _figure((12, 4.5))
    axes = figure.subplots(1, 2)
    dd, no_dd = np.array(aggregate["dd_seed_means"]), np.array(aggregate["no_dd_seed_means"])
    counts = np.arange(1, len(dd) + 1)
    if len(dd):
        for values, mode in ((dd, "dd"), (no_dd, "no-dd")):
            axes[0].plot(counts, np.cumsum(values) / counts, "o-", color=COLORS[mode], label=mode)
        estimates = [mean_interval((dd - no_dd)[:count]) for count in counts]
        axes[1].plot(counts, [row["mean"] for row in estimates], "o-", color=COLORS["dd"])
        axes[1].fill_between(
            counts,
            [np.nan if row["lower"] is None else row["lower"] for row in estimates],
            [np.nan if row["upper"] is None else row["upper"] for row in estimates],
            color=COLORS["dd"],
            alpha=0.18,
            label="approx. 95% t interval",
        )
        axes[0].legend()
        axes[1].legend()
    else:
        for axis in axes:
            axis.text(
                0.5, 0.5, "No common finite seed cohort", transform=axis.transAxes, ha="center"
            )
    axes[0].set(ylabel="Cumulative mean score", title="Sensitivity to replicate count")
    axes[1].axhline(0, color="black", lw=0.8)
    axes[1].set(
        ylabel="Cumulative paired difference", title="One replicate does not estimate uncertainty"
    )
    for axis in axes:
        axis.set_xlabel("Number of paired seed replicates (fixed seed order)")
        axis.grid(alpha=0.2)
        if len(dd):
            axis.set_xticks(counts)
    figure.suptitle(
        "Aggregate convergence across all declared cases", fontsize=14, fontweight="bold"
    )
    return _save(figure, root, "08_seed_convergence")


def render_figures(data: dict, output_dir: Path) -> list[str]:
    """Save PNG and vector PDF views of validated diagnostic data; return figure stems.

    Figures use an explicit Agg canvas, so importing/rendering does not switch
    the global backend of a live notebook. Paired views require score data.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    with mpl.rc_context(STYLE):
        figures = [
            function(data, output_dir)
            for function in (_state, _distributions, _layout, _schedule, _resources, _sensitivity)
        ]
        if data.get("comparison") is not None:
            figures.extend(function(data, output_dir) for function in (_paired, _convergence))
    return figures
