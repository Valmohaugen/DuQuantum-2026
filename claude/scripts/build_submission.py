"""Export the canonical physics module as one standalone challenge submission."""

from __future__ import annotations

import argparse
import ast
from dataclasses import asdict
from pathlib import Path

from claude import dicke_prep as dp

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "claude/dicke_prep.py"
ALLOWED_ROOTS = {
    "__future__",
    "functools",
    "math",
    "numbers",
    "time",
    "dataclasses",
    "cirq",
    "cirq_google",
    "numpy",
    "networkx",
}


def build_submission(destination: Path, *, configuration: dp.PrepConfig | None = None) -> Path:
    """Write a syntax-checked, allowed-import export of both challenge entry points.

    The destination is explicit to prevent overwriting a hand-edited submission.
    Raises ValueError for unexpected imports and OSError for unwritable paths.
    Returns the saved absolute path; no simulations or network calls are made.
    If configuration is supplied, its preparation defaults are embedded in CONFIG
    before function definitions bind their defaults. Otherwise the export is
    byte-identical to the canonical source. Noise/sampling settings are excluded.
    """
    source = SOURCE.read_text()
    if configuration is not None:
        original = "CONFIG = PrepConfig()"
        if source.count(original) != 1:
            raise ValueError("cannot identify the canonical preparation defaults for export")
        source = source.replace(original, f"CONFIG = PrepConfig(**{asdict(configuration)!r})", 1)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        roots = (
            [alias.name.split(".")[0] for alias in node.names]
            if isinstance(node, ast.Import)
            else []
        )
        if isinstance(node, ast.ImportFrom):
            roots = [(node.module or "").split(".")[0]]
        if any(root not in ALLOWED_ROOTS for root in roots):
            raise ValueError(f"submission contains an unsupported import at line {node.lineno}")
    compile(source, str(destination), "exec")
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="output Python file")
    args = parser.parse_args()
    print(f"[done] submission exported: {build_submission(args.destination)}")


if __name__ == "__main__":
    main()
