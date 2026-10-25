"""Exploratory figures must survive notebook output clearing and slider changes."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pytest


def test_explicit_show_saves_both_formats_and_preserves_changed_states(
    monkeypatch, tmp_path: Path
) -> None:
    from claude.notebook_figures import save_and_show

    shown = []
    monkeypatch.setattr(plt, "show", lambda: shown.append(True))
    plt.close("all")
    figure, axis = plt.subplots()
    (line,) = axis.plot([0, 1], [0, 1])
    axis.set_title("Diagnostic / slider")
    root = save_and_show("tutorial")
    assert root.is_relative_to(tmp_path / "figs" / "notebooks")
    assert len(list(root.glob("*.png"))) == len(list(root.glob("*.pdf"))) == 1
    save_and_show("tutorial")
    assert len(list(root.glob("*.png"))) == 1
    line.set_ydata([1, 0])
    save_and_show("tutorial")
    assert len(list(root.glob("*.png"))) == len(list(root.glob("*.pdf"))) == 2
    assert len(json.loads((root / "figures.json").read_text())["figures"]) == 2
    assert len(shown) == 3
    plt.close(figure)


@pytest.mark.parametrize("damage", ["png", "pdf", "both", "corrupt"])
def test_missing_or_corrupt_saved_view_is_restored(monkeypatch, damage: str) -> None:
    from claude.notebook_figures import save_and_show

    monkeypatch.setattr(plt, "show", lambda: None)
    plt.close("all")
    figure, axis = plt.subplots()
    axis.plot([0, 1], [1, 0])
    root = save_and_show("restore")
    png = next(root.glob("*.png"))
    pdf = next(root.glob("*.pdf"))
    if damage in ("png", "both"):
        png.unlink()
    if damage in ("pdf", "both"):
        pdf.unlink()
    if damage == "corrupt":
        pdf.write_bytes(b"broken")
    save_and_show("restore")
    assert png.read_bytes().startswith(b"\x89PNG")
    assert pdf.read_bytes().startswith(b"%PDF-")
    assert len(json.loads((root / "figures.json").read_text())["figures"]) == 1
    plt.close(figure)
