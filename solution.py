"""Dicke-state constructors and the local validation/benchmark command.

Importing this module performs no experiments. The canonical implementation
lives in claude.dicke_prep; the original challenge notebook remains the
protected scoring reference. Run ``python -u solution.py --help`` for options.
"""

from __future__ import annotations

from claude.dicke_prep import create_dicke_state, create_dicke_state_adaptive

__all__ = ["create_dicke_state", "create_dicke_state_adaptive", "main"]


def main(argv: list[str] | None = None) -> int:
    """Run the local CLI with explicit flags or process arguments; return its status.

    Parameters
    ----------
    argv : list of str or None
        Options described by --help, or process arguments when None.

    Returns
    -------
    int
        0 on completion, 1 on failure, or 130 on interruption. Imports are inert.

    Raises
    ------
    SystemExit
        With status 2 for invalid arguments, or 0 for --help.
    """
    from claude.scripts.run_solution import main as run

    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
