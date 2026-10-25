"""Shared artifact destinations for command-line tools and notebook consumers."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_FIGURE_ROOT = Path(__file__).resolve().parents[1] / "figs"


def figure_root() -> Path:
    """Return the absolute root for saved figures, without creating directories.

    Defaults to the repository's ``figs/`` directory. Tests and isolated notebook
    checks may set DUQUANTUM_FIGURES_DIR to a temporary destination. Rendering
    creates the run-specific subdirectory; filesystem failures propagate.
    """
    return Path(os.environ.get("DUQUANTUM_FIGURES_DIR", str(DEFAULT_FIGURE_ROOT))).resolve()
