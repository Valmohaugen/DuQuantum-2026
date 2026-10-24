"""The notebook and standalone Python solution must hold the same code cells."""

from pathlib import Path

import jupytext

REPO = Path(__file__).resolve().parents[2]
NOTEBOOK = REPO / "solution.ipynb"
MIRROR = REPO / "solution.py"


def test_mirror_matches_notebook() -> None:
    notebook_cells = jupytext.read(NOTEBOOK).cells
    mirror_cells = jupytext.read(MIRROR).cells
    expected = [cell.source for cell in notebook_cells if cell.cell_type == "code"]
    actual = [cell.source for cell in mirror_cells if cell.cell_type == "code"]
    assert actual == expected, (
        f"Executable cells in {MIRROR.name} differ from {NOTEBOOK.name}; "
        "update both working files."
    )


def test_mirror_runs_as_python() -> None:
    compile(MIRROR.read_text(), str(MIRROR), "exec")  # e.g. no mid-file __future__ import
