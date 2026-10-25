"""Execute working notebook code in isolated namespaces without saving outputs."""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import matplotlib
import nbformat

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


def main() -> None:
    """Run all working cells headlessly; preserve every saved notebook and original."""
    os.environ["TUTORIAL_NO_WIDGETS"] = "1"
    os.chdir(REPO)
    with tempfile.TemporaryDirectory(prefix="duquantum-notebooks-") as directory:
        os.environ["DUQUANTUM_DIAGNOSTICS_DIR"] = directory
        os.environ["DUQUANTUM_FIGURES_DIR"] = str(Path(directory) / "figs")
        for relative in ("solution.ipynb", "claude/tutorial/Dicke_Tutorial.ipynb"):
            notebook = nbformat.read(REPO / relative, as_version=4)
            namespace = {"__name__": "__main__"}
            count = 0
            for index, cell in enumerate(notebook.cells):
                if cell.cell_type != "code":
                    continue
                try:
                    with (
                        contextlib.redirect_stdout(io.StringIO()),
                        patch.object(plt, "show", lambda: None),
                    ):
                        exec(compile(cell.source, f"{relative}:cell-{index}", "exec"), namespace)
                except Exception as exc:
                    raise RuntimeError(f"{relative}, code cell {index} failed: {exc}") from exc
                finally:
                    plt.close("all")
                count += 1
            print(f"[done] {relative}: {count} code cells executed in memory")


if __name__ == "__main__":
    main()
