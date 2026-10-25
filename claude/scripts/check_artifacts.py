"""Verify maintained Python syntax and the protected original challenge."""

from __future__ import annotations

import hashlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CHALLENGE_SHA256 = "ee1d7d53f64bde2e5f8da114d0bc198ea2666e40cc65ea4eadca2f97c062acd1"


def main() -> None:
    """Raise on original-file drift or Python syntax errors; notebooks are optional.

    Reads the original challenge and maintained Python sources beneath REPO.
    Private documentation is excluded. No files are modified or executed.
    Missing files raise OSError; changed original bytes raise ValueError and
    invalid Python raises SyntaxError with its filename and line number.
    """
    actual = hashlib.sha256((REPO / "Google Quantum AI Challenge.ipynb").read_bytes()).hexdigest()
    if actual != CHALLENGE_SHA256:
        raise ValueError(f"protected original challenge notebook changed: {actual}")
    sources = [REPO / "solution.py", *sorted((REPO / "claude").rglob("*.py"))]
    sources = [path for path in sources if ".docs" not in path.parts]
    for path in sources:
        compile(path.read_text(), str(path), "exec")
    print(f"[done] original protected; {len(sources)} Python sources compile")


if __name__ == "__main__":
    main()
