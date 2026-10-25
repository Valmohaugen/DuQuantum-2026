"""Persist explicit exploratory plot displays without changing Matplotlib's backend."""

from __future__ import annotations

import hashlib
import io
import json
import platform
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt

from claude.output_paths import figure_root

SESSION_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
PLOT_DPI = 180


def save_and_show(session: str = "tutorial") -> Path:
    """Save every open pyplot figure as PNG/PDF, then display normally.

    Parameters
    ----------
    session : str
        Human-readable group name, sanitized for a subfolder below figs/notebooks/.

    Returns
    -------
    pathlib.Path
        This kernel session's folder, with figures.json listing all saved images.
        Identical views are retained once; changed slider/plot views get content
        hashes and never replace earlier views. Explicit plt.show calls should
        use this helper; report figures have their own saving pipeline. Filesystem
        errors propagate so a failed save is not silently presented as persistent.
    """
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", session).strip("-") or "notebook"
    root = figure_root() / "notebooks" / name / SESSION_ID
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "figures.json"
    manifest = (
        json.loads(manifest_path.read_text())
        if manifest_path.exists()
        else {
            "session": SESSION_ID,
            "python": platform.python_version(),
            "matplotlib": matplotlib.__version__,
            "saving_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "figures": [],
        }
    )
    known = {entry["png_sha256"]: entry for entry in manifest["figures"]}
    for number in plt.get_fignums():
        figure = plt.figure(number)
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png", dpi=PLOT_DPI)
        content = buffer.getvalue()
        digest = hashlib.sha256(content).hexdigest()
        title = figure.get_suptitle() or next(
            (ax.get_title() for ax in figure.axes if ax.get_title()), "figure"
        )
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", title).strip("-")[:70] or "figure"
        stem = f"{slug}-{digest[:12]}"
        png, pdf = root / (stem + ".png"), root / (stem + ".pdf")
        existing = known.get(digest)
        png_valid = png.exists() and hashlib.sha256(png.read_bytes()).hexdigest() == digest
        pdf_valid = (
            pdf.exists()
            and existing is not None
            and hashlib.sha256(pdf.read_bytes()).hexdigest() == existing["pdf_sha256"]
        )
        if existing and png_valid and pdf_valid:
            continue
        if not png_valid:
            temporary_png = png.with_suffix(".png.tmp")
            temporary_png.write_bytes(content)
            temporary_png.replace(png)
        if not pdf_valid:
            temporary_pdf = pdf.with_suffix(".pdf.tmp")
            figure.savefig(temporary_pdf, format="pdf")
            temporary_pdf.replace(pdf)
        entry = {
            "title": title,
            "png": str(png),
            "pdf": str(pdf),
            "png_sha256": digest,
            "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
            "saved_at": existing["saved_at"]
            if existing
            else datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if existing:
            existing.update(entry)
            existing["restored_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        else:
            manifest["figures"].append(entry)
            known[digest] = entry
        print(f"[saved] {png}")
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    temporary.replace(manifest_path)
    plt.show()
    return root
