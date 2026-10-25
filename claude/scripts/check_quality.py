"""Explicit Ruff settings and structured pytest progress for local quality checks."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Sequence, TextIO

if TYPE_CHECKING:
    from pytest import ExceptionInfo, Session, TestReport

RUFF_COMMON = (
    "--isolated",
    "--target-version",
    "py312",
    "--force-exclude",
    "--exclude",
    "*.ipynb,benchmark_outputs,submission_outputs,.mypy_cache,.docs,ryon,toby",
)
RUFF_LINT = ("--select", "E4,E7,E9,F,I", "--config", "line-length=100")
RUFF_FORMAT = ("--check", "--line-length", "100")
DEFAULT_TARGETS = ("solution.py", "claude")


class _PytestProgress:
    """Write flushed JSON events separately from pytest's full diagnostic output."""

    def __init__(self, stream: TextIO) -> None:
        self.stream = stream
        self.torn_down: set[str] = set()
        self.finished: set[str] = set()

    def emit(self, **event: object) -> None:
        self.stream.write(json.dumps(event) + "\n")
        self.stream.flush()

    def pytest_collection_finish(self, session: Session) -> None:
        self.emit(event="collected", total=len(session.items), errors=session.testsfailed)

    def pytest_runtest_logreport(self, report: TestReport) -> None:
        if report.when == "teardown":
            self.torn_down.add(report.nodeid)

    def pytest_runtest_logfinish(self, nodeid: str, location: tuple[str, int | None, str]) -> None:
        if nodeid in self.torn_down and nodeid not in self.finished:
            self.finished.add(nodeid)
            self.emit(event="completed", completed=len(self.finished))

    def pytest_keyboard_interrupt(self, excinfo: ExceptionInfo[BaseException]) -> None:
        self.emit(event="interrupted", keyboard=excinfo.typename == "KeyboardInterrupt")


def ruff_command(kind: str, paths: Sequence[str] = ()) -> list[str]:
    """Return an isolated, read-only Ruff command using the project's fixed settings.

    Parameters
    ----------
    kind : str
        ``lint`` or ``format``; both check without rewriting sources.
    paths : sequence of str
        Optional file/directory arguments, defaulting to maintained sources.

    Returns
    -------
    list of str
        Command arguments using the active interpreter and isolated settings.

    Raises
    ------
    ValueError
        If kind is unsupported. This function executes no commands.
    """
    if kind not in {"lint", "format"}:
        raise ValueError(f"unknown Ruff check: {kind}")
    mode, settings = ("check", RUFF_LINT) if kind == "lint" else ("format", RUFF_FORMAT)
    return [
        sys.executable,
        "-m",
        "ruff",
        mode,
        *RUFF_COMMON,
        *settings,
        *(paths or DEFAULT_TARGETS),
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Run lint/format or pytest with a separate progress-event file.

    Parameters
    ----------
    argv : sequence of str or None
        CLI arguments, or process arguments when None. Pytest requires
        --progress-file and accepts its own arguments after ``--``.

    Returns
    -------
    int
        Subprocess/pytest exit status. Diagnostic output remains on stdout/stderr
        for the caller to capture; only the requested progress file is written.

    Raises
    ------
    SystemExit
        For invalid CLI options. No physics or Git writes occur.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="kind", required=True)
    for kind in ("lint", "format"):
        commands.add_parser(kind).add_argument("paths", nargs="*")
    tests = commands.add_parser("pytest")
    tests.add_argument("--progress-file", type=Path, required=True)
    tests.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.kind != "pytest":
        return subprocess.call(ruff_command(args.kind, args.paths))
    import pytest

    pytest_args = args.pytest_args
    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    with args.progress_file.open("w") as stream:
        return int(pytest.main(pytest_args, plugins=[_PytestProgress(stream)]))


if __name__ == "__main__":
    raise SystemExit(main())
