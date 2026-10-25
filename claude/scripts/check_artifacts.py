"""Verify generated/paired notebooks, syntax, outputs, and the protected challenge."""

from __future__ import annotations

import hashlib
import runpy
from pathlib import Path

import jupytext
import nbformat

REPO = Path(__file__).resolve().parents[2]
CHALLENGE_SHA256 = "ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1"


def main() -> None:
    """Fail on protected-file drift, invalid/stale notebooks, or committed outputs."""
    if (
        hashlib.sha256((REPO / "Google Quantum AI Challenge.ipynb").read_bytes()).hexdigest()
        != CHALLENGE_SHA256
    ):
        raise ValueError("protected original challenge notebook changed")
    notebook = jupytext.read(REPO / "solution.ipynb")
    mirror = jupytext.read(REPO / "solution.py")
    if [c.source for c in notebook.cells if c.cell_type == "code"] != [
        c.source for c in mirror.cells if c.cell_type == "code"
    ]:
        raise ValueError("working solution notebook and mirror disagree")
    generated = runpy.run_path(str(REPO / "claude/scripts/build_tutorial.py"))["CELLS"]
    tutorial = nbformat.read(REPO / "claude/tutorial/Dicke_Tutorial.ipynb", as_version=4)
    if len(generated) != len(tutorial.cells) or any(
        src != cell.source for (_, src), cell in zip(generated, tutorial.cells)
    ):
        raise ValueError("tutorial is stale; regenerate it from build_tutorial.py")
    for path in (REPO / "solution.ipynb", REPO / "claude/tutorial/Dicke_Tutorial.ipynb"):
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
        for index, cell in enumerate(nb.cells):
            if cell.cell_type == "code":
                compile(cell.source, f"{path.name}:cell-{index}", "exec")
                if cell.outputs or cell.execution_count is not None:
                    raise ValueError(
                        f"working notebook has saved output: {path.name}, cell {index}"
                    )
    print("[done] original protected; working notebooks valid, synchronized, output-free")


if __name__ == "__main__":
    main()
