"""solution.ipynb and its jupytext mirror solution.py must hold the same code."""

from pathlib import Path

import jupytext

REPO = Path(__file__).resolve().parents[2]
NOTEBOOK = REPO / "solution.ipynb"
MIRROR = REPO / "solution.py"


def test_mirror_matches_notebook() -> None:
    expected = jupytext.writes(jupytext.read(NOTEBOOK), fmt="py:percent")
    assert MIRROR.read_text() == expected, (
        f"{MIRROR.name} is out of sync with {NOTEBOOK.name}; run: "
        f'jupytext --sync "{NOTEBOOK.name}"'
    )


def test_mirror_runs_as_python() -> None:
    compile(MIRROR.read_text(), str(MIRROR), "exec")  # e.g. no mid-file __future__ import
