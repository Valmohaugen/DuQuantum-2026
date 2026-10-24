"""Expose the solution in ``solution.ipynb`` as the module ``dicke_prep``.

The solution is written in ``solution.ipynb`` (mirrored by ``solution.py`` via
jupytext). The tests, the noisy benchmark and the tutorial ``import dicke_prep``.
This module runs every code cell of the notebook, except those tagged ``check``,
in its own namespace, so they always use the code being edited in the notebook.

Raises
------
ImportError
    If the notebook does not define ``create_dicke_state`` and ``create_dicke_state_adaptive``.
"""

import json
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / "solution.ipynb"
SKIP_TAG = "check"
REQUIRED = ("create_dicke_state", "create_dicke_state_adaptive")

for _i, _cell in enumerate(json.loads(NOTEBOOK.read_text())["cells"]):
    if _cell["cell_type"] == "code" and SKIP_TAG not in _cell.get("metadata", {}).get("tags", []):
        exec(compile("".join(_cell["source"]), f"{NOTEBOOK.name} [code cell {_i}]", "exec"), globals())

_missing = [name for name in REQUIRED if name not in globals()]
if _missing:
    raise ImportError(f"{NOTEBOOK.name} does not define {_missing}")
