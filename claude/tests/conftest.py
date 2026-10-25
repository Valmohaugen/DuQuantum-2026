"""Keep every in-process benchmark regression inside pytest's temporary directory."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_benchmark_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Redirect both dynamic and legacy bound paths before a test can call main.

    Legacy revisions bound checkpoint/results paths at import. Redirecting only
    OUTPUT_DIR was insufficient and caused the documented historical data loss.
    These guards apply even when the revision under test regresses that design.
    """
    from claude.scripts import noisy_benchmark

    root = tmp_path / "isolated-benchmark"
    monkeypatch.setenv("DUQUANTUM_FIGURES_DIR", str(tmp_path / "figs"))
    monkeypatch.setattr(noisy_benchmark, "OUTPUT_DIR", root)
    for name, filename in (
        ("CHECKPOINT_PATH", "noisy_benchmark_checkpoint.json"),
        ("RESULTS_PATH", "noisy_benchmark_results.json"),
    ):
        if hasattr(noisy_benchmark, name):
            monkeypatch.setattr(noisy_benchmark, name, root / filename)
