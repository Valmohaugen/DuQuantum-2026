"""Plotting and widget helpers for the Dicke-state tutorial notebook.

The physics lives in ``solution.ipynb`` and in the tutorial's own cells. This module only
draws things and wires up sliders, so the notebook stays readable. Everything
works without ipywidgets: ``interactive`` then runs the function once with the
default values.
"""

from __future__ import annotations

import itertools
import math
import os
from collections.abc import Callable, Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import cm, colors

try:
    import ipywidgets as widgets
    from IPython.display import display

    # TUTORIAL_NO_WIDGETS=1 forces the static mode (used for headless test runs)
    HAVE_WIDGETS = os.environ.get("TUTORIAL_NO_WIDGETS") != "1"
except ImportError:  # pragma: no cover - exercised only without ipywidgets
    HAVE_WIDGETS = False

PROB_EPS = 1e-9  # probabilities below this are treated as zero in plots
WEIGHT_COLORS = plt.get_cmap("tab10")


# --------------------------------------------------------------------------- #
# Widgets
# --------------------------------------------------------------------------- #
def interactive(fn: Callable, manual: bool = False, **controls: tuple) -> None:
    """Show sliders for ``fn`` or, without ipywidgets, call it with the defaults.

    Parameters
    ----------
    fn : Callable
        Function taking the control names as keyword arguments.
    manual : bool
        If True, add a "Run" button instead of re-running on every slider move
        (use for slow cells such as noisy simulation).
    **controls : tuple
        ``name=(lo, hi, step, default)``. Integer tuples give an IntSlider,
        anything else a FloatSlider. A list gives a dropdown (first entry default).
    """
    defaults = {k: (v[0] if isinstance(v, list) else v[3]) for k, v in controls.items()}
    if not HAVE_WIDGETS:
        print(f"[warn] ipywidgets not installed; running once with {defaults}")
        fn(**defaults)
        return
    ws = {}
    for name, spec in controls.items():
        if isinstance(spec, list):
            ws[name] = widgets.Dropdown(options=spec, value=spec[0], description=name)
            continue
        lo, hi, step, value = spec
        cls = widgets.IntSlider if all(isinstance(x, int) for x in spec) else widgets.FloatSlider
        ws[name] = cls(min=lo, max=hi, step=step, value=value, description=name, continuous_update=False)
    if manual:
        out = widgets.Output()
        button = widgets.Button(description="Run", button_style="primary")

        def run(_=None) -> None:
            out.clear_output(wait=True)
            with out:
                fn(**{k: w.value for k, w in ws.items()})
                plt.show()

        button.on_click(run)
        display(widgets.VBox([widgets.HBox(list(ws.values())), button, out]))
        run()
    else:
        out = widgets.interactive_output(fn, ws)
        display(widgets.VBox([widgets.HBox(list(ws.values())), out]))


# --------------------------------------------------------------------------- #
# States
# --------------------------------------------------------------------------- #
def dicke_vector(n: int, k: int) -> np.ndarray:
    """Ideal |D^n_k> as a length-2^n real vector (any qubit order: it is symmetric)."""
    psi = np.zeros(2**n)
    for ones in itertools.combinations(range(n), k):
        psi[sum(2**i for i in ones)] = 1.0
    return psi / math.sqrt(math.comb(n, k))


def bits(index: int, n: int) -> str:
    """Bitstring of a basis index, most significant (first qubit) on the left."""
    return format(index, f"0{n}b")


def plot_probs(ax, psi: np.ndarray, n: int, only_nonzero: bool = False, title: str = "") -> None:
    """Bar chart of |amplitude|^2 over basis states, coloured by Hamming weight."""
    probs = np.abs(psi) ** 2
    idx = np.flatnonzero(probs > PROB_EPS) if only_nonzero else np.arange(2**n)
    weights = [bits(i, n).count("1") for i in idx]
    ax.bar(range(len(idx)), probs[idx], color=[WEIGHT_COLORS(w % 10) for w in weights])
    if len(idx) <= 40:
        ax.set_xticks(range(len(idx)), [bits(i, n) for i in idx], rotation=90, family="monospace")
    else:
        ax.set_xticks([])
        ax.set_xlabel(f"all {2**n} basis states (labels hidden)")
    ax.set_ylabel("probability")
    ax.set_ylim(0, 1.05 * max(probs.max(), PROB_EPS))
    ax.set_title(title)


def plot_line_occupation(ax, psi: np.ndarray, n: int, active: Sequence[int] = ()) -> None:
    """Draw the qubit line, shading each qubit by <n_i> and boxing the active ones."""
    probs = (np.abs(psi) ** 2).reshape([2] * n)
    occ = [float(np.moveaxis(probs, i, 0)[1].sum()) for i in range(n)]
    for i, p in enumerate(occ):
        ax.add_patch(plt.Circle((i, 0), 0.35, color=plt.get_cmap("Blues")(0.15 + 0.8 * p), ec="k"))
        ax.text(i, 0, f"{p:.2f}", ha="center", va="center", fontsize=8, color="w" if p > 0.5 else "k")
        ax.text(i, -0.6, str(i), ha="center", fontsize=8)
    if len(active):
        lo, hi = min(active), max(active)
        ax.add_patch(plt.Rectangle((lo - 0.45, -0.45), hi - lo + 0.9, 0.9, fill=False, ec="C3", lw=2))
    ax.set_xlim(-0.6, n - 0.4)
    ax.set_ylim(-0.8, 0.6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("line positions, shaded by P(qubit = 1)", fontsize=9)


# --------------------------------------------------------------------------- #
# Willow grid
# --------------------------------------------------------------------------- #
def draw_willow(ax, cal: tuple, all_qubits, all_pairs, layout_edges=(), layout_qubits=()) -> None:
    """Draw the Willow grid: nodes by readout+1q cost, couplers by CZ error.

    Parameters
    ----------
    cal : tuple
        ``(cz_pauli_error_rate, sq_pauli_error_rate, zero_errors, one_errors)``.
    all_qubits, all_pairs
        Full device qubits and couplers (dead ones are drawn as grey crosses / dotted).
    layout_edges, layout_qubits
        Chosen couplers (drawn thick) and qubits (drawn with a ring).
    """
    cz, sq, e0, e1 = cal
    xy = lambda q: (q.col, -q.row)
    cz_err = {frozenset(p): e for p, (e, _) in cz.items()}
    norm = colors.LogNorm(1e-3, 1e-2)
    for p in all_pairs:
        a, b = tuple(p)
        (x0, y0), (x1, y1) = xy(a), xy(b)
        err = cz_err.get(frozenset(p))
        if err is None:
            ax.plot([x0, x1], [y0, y1], ":", color="0.8", lw=1)
        else:
            ax.plot([x0, x1], [y0, y1], color=cm.viridis_r(norm(err)), lw=2, alpha=0.6)
    for a, b in layout_edges:
        (x0, y0), (x1, y1) = xy(a), xy(b)
        ax.plot([x0, x1], [y0, y1], color="C3", lw=5, solid_capstyle="round", zorder=3)
    node_norm = colors.LogNorm(3e-3, 3e-2)
    for q in all_qubits:
        x, y = xy(q)
        if q not in sq:
            ax.plot(x, y, "x", color="0.5", ms=7)
            continue
        cost = 0.5 * (e0[q][0] + e1[q][0]) + 2 * sq[q][0]
        ax.scatter(x, y, s=60, color=cm.magma_r(node_norm(cost)), edgecolors="k", lw=0.5, zorder=4)
    for q in layout_qubits:
        ax.scatter(*xy(q), s=180, facecolors="none", edgecolors="C3", lw=2, zorder=5)
    ax.set_aspect("equal")
    ax.axis("off")
    sm = cm.ScalarMappable(norm=norm, cmap="viridis_r")
    plt.colorbar(sm, ax=ax, fraction=0.03, label="CZ Pauli error")
