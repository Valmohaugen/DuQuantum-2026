"""The check display must be compact while retaining complete subprocess evidence."""

from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import pytest


class Terminal(io.StringIO):
    """In-memory terminal for checking real tqdm rendering without a PTY."""

    def isatty(self) -> bool:
        return True


def check_commands(root: Path, source: str) -> list[tuple[str, list[str]]]:
    """Build three harmless gates followed by an isolated real pytest session."""
    test = root / "test_tiny.py"
    test.write_text(source)
    commands = [
        (name, [sys.executable, "-u", "-c", f"print('detailed {name} output')"])
        for name in ("lint", "format", "artifacts")
    ]
    commands.append(
        (
            "pytest",
            [
                sys.executable,
                "-u",
                "-m",
                "claude.scripts.check_quality",
                "pytest",
                "--progress-file",
                str(root / "check-progress.jsonl"),
                "--",
                "-c",
                os.devnull,
                "--rootdir",
                str(root),
                "-v",
                str(test),
            ],
        )
    )
    return commands


@pytest.mark.parametrize("tty", [False, True])
def test_checks_hide_verbose_output_and_count_each_test_once(tmp_path: Path, tty: bool) -> None:
    from claude.scripts.run_solution import _checks

    commands = check_commands(
        tmp_path,
        "import pytest\ndef test_ok(): pass\n@pytest.mark.skip(reason='tiny skip')\ndef test_skip(): pass\n",
    )
    console = Terminal() if tty else io.StringIO()
    log = io.StringIO()
    path = _checks(tmp_path, commands=commands, console=console, log=log)
    data = json.loads(path.read_text())
    assert data["status"] == "passed"
    assert data["completed_checks"] == data["total_checks"] == 5
    assert data["tests_completed"] == 2
    assert "detailed lint output" not in console.getvalue()
    assert "test_tiny.py::test_ok PASSED" not in console.getvalue()
    assert "test_tiny.py::test_ok PASSED" in log.getvalue()
    assert "tiny skip" in log.getvalue() or "SKIPPED" in log.getvalue()
    assert ("100%" in console.getvalue()) == tty
    if not tty:
        assert "\r" not in console.getvalue() and "\x1b" not in console.getvalue()


@pytest.mark.parametrize("phase", ["setup", "teardown"])
def test_fixture_failure_counts_once_and_replays_diagnostics(tmp_path: Path, phase: str) -> None:
    from claude.scripts.run_solution import _checks

    fixture = (
        "raise ValueError('fixture diagnostic')"
        if phase == "setup"
        else "yield\n    raise ValueError('fixture diagnostic')"
    )
    commands = check_commands(
        tmp_path,
        f"import pytest\n@pytest.fixture\ndef broken():\n    {fixture}\ndef test_broken(broken): pass\n",
    )
    console, log = io.StringIO(), io.StringIO()
    with pytest.raises(RuntimeError, match="pytest"):
        _checks(tmp_path, commands=commands, console=console, log=log)
    data = json.loads((tmp_path / "checks.json").read_text())
    assert data["status"] == "failed" and data["tests_completed"] == 1
    assert data["completed_checks"] == data["total_checks"] == 4
    assert "fixture diagnostic" in console.getvalue() and "fixture diagnostic" in log.getvalue()


def test_collection_failure_never_reports_success(tmp_path: Path) -> None:
    from claude.scripts.run_solution import _checks

    console = Terminal()
    with pytest.raises(RuntimeError, match="pytest"):
        _checks(
            tmp_path,
            commands=check_commands(tmp_path, "def invalid(:\n"),
            console=console,
            log=io.StringIO(),
        )
    data = json.loads((tmp_path / "checks.json").read_text())
    assert data["status"] == "failed" and data["tests_completed"] == 0
    assert "SyntaxError" in console.getvalue()


def test_interrupted_pytest_retains_partial_counts(tmp_path: Path) -> None:
    from claude.scripts.run_solution import _checks

    commands = check_commands(
        tmp_path, "def test_first(): pass\ndef test_interrupt(): raise KeyboardInterrupt()\n"
    )
    console = Terminal()
    with pytest.raises(KeyboardInterrupt):
        _checks(tmp_path, commands=commands, console=console, log=io.StringIO())
    data = json.loads((tmp_path / "checks.json").read_text())
    assert data["status"] == "interrupted" and data["tests_completed"] == 1
    assert data["completed_checks"] < data["total_checks"]


def test_artifact_checks_need_only_python_and_original_challenge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from claude.scripts import check_artifacts

    original = check_artifacts.REPO / "Google Quantum AI Challenge.ipynb"
    (tmp_path / original.name).write_bytes(original.read_bytes())
    (tmp_path / "solution.py").write_text("def main(): return 0\n")
    monkeypatch.setattr(check_artifacts, "REPO", tmp_path)
    check_artifacts.main()
    (tmp_path / "solution.py").write_text("def invalid(:\n")
    with pytest.raises(SyntaxError):
        check_artifacts.main()


def test_early_gate_failure_replays_output_and_stops(tmp_path: Path) -> None:
    from claude.scripts.run_solution import _checks

    commands = [("lint", [sys.executable, "-c", "print('lint diagnostic'); raise SystemExit(3)"])]
    console, log = io.StringIO(), io.StringIO()
    with pytest.raises(RuntimeError, match="lint"):
        _checks(tmp_path, commands=commands, console=console, log=log)
    state = json.loads((tmp_path / "checks.json").read_text())
    assert state["status"] == "failed" and state["completed_checks"] == 0
    assert "lint diagnostic" in console.getvalue() and "lint diagnostic" in log.getvalue()
