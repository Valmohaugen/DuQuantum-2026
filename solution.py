# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.17.2
#   kernelspec:
#     display_name: duquantum
#     language: python
#     name: duquantum
# ---

# %% [markdown]
# # Dicke-state preparation on Google Willow
#
# The tested implementation lives in `claude/dicke_prep.py`. This working notebook
# is for exploration; the original challenge notebook remains reference-only.
# The constructor enforces the 1,750-moment challenge limit. The bonus uses a legal
# non-adaptive construction; no hardware execution path is provided here.
# The organizer confirmed bonus grading for 2 ≤ N ≤ 15 and corrected the original
# validator to use `range(len(qubits))`. Grading cases and correlator sizes remain
# undisclosed. See `claude/docs/CHALLENGE_CORRECTIONS.md`; the original stays intact.
# Optimized synthesis uses exact four-CZ split-pair identities and a calibrated
# five-CZ D(4,2) square. Use `--construction analytic` to compare the previous solver.

# %%
import os
from pathlib import Path

from claude import dicke_prep as dp
from claude.scripts.challenge_calibration import make_challenge_calibration
from claude.validation import validate_preparation

create_dicke_state = dp.create_dicke_state
create_dicke_state_adaptive = dp.create_dicke_state_adaptive

# %% [markdown]
# ## A bounded exact example
#
# Dicke fidelity tests amplitudes and relative phases. Device validation also
# checks native gates and connectivity. Execute this example deliberately.


# %%
def exact_example(n: int = 6, k: int = 3) -> float:
    """Build and validate one small noiseless example; return its fidelity."""
    calibration = make_challenge_calibration()
    circuit, qubits = create_dicke_state(n, k, *calibration)
    fidelity = validate_preparation(circuit, qubits, n, k, calibration)
    print(f"[done] D({n},{k}): {len(circuit)} moments; exact fidelity {fidelity:.12f}")
    return fidelity


# %% [markdown]
# ## Script entry point
#
# Importing this file only defines functions. Direct execution runs the complete
# full workflow, including software/notebook checks and the complete bonus range.
# Use `python -u solution.py --preset quick` for a smoke run,
# `--help` for options, and `--plan` to inspect settings without running anything.


# %%
def main(argv: list[str] | None = None) -> int:
    """Run the local CLI; pass a list of flags when calling from a notebook."""
    from claude.scripts.run_solution import main as run

    if argv is None and "__file__" not in globals():
        argv = []
    return run(argv)


# %% [markdown]
# ## Diagnostic outputs and saved figures
#
# Run this cell in the notebook to inspect exact phases/amplitudes, noisy
# distributions, schedules, layout costs, resource scaling and matched-seed
# comparisons. Saved PNG/PDF, JSON and CSV files accompany the report.
# Figures are stored under the repository's `figs/` directory and linked by each report.
# A raw score dataset is optional; unavailable paired data is clearly labeled.
# To create paired data and all reports, run `python -u solution.py`.
# Notebook users can call `main(["--preset", "quick"])` deliberately.


# %%
def diagnostic_example(output_root: Path | None = None, results_path: Path | None = None) -> Path:
    """Build the bounded notebook diagnostic example and return the saved report."""
    from claude.scripts.analyze_benchmark_results import latest_results
    from claude.scripts.diagnose import DEFAULT_OUTPUT, build_report

    if output_root is None:
        output_root = Path(os.environ.get("DUQUANTUM_DIAGNOSTICS_DIR", str(DEFAULT_OUTPUT)))
    if results_path is None:
        try:
            results_path = latest_results()
        except FileNotFoundError:
            print("[data] Paired score data unavailable; generating state/circuit diagnostics.")
    return build_report(output_root, results_path=results_path, resource_sizes=(4, 8, 16, 30, 60))


# %%
if "__file__" not in globals():
    import json

    from IPython.display import Image, Markdown, display

    from claude.notebook_figures import save_and_show as save_and_show

    exact_example()
    diagnostic_report = diagnostic_example()
    diagnostic_data = json.loads((diagnostic_report.parent / "diagnostics.json").read_text())
    display(Markdown(diagnostic_report.read_text().split("## Figures")[0]))
    for figure_name in diagnostic_data["figures"]:
        display(
            Image(
                filename=str(Path(diagnostic_data["figure_dir"]) / (figure_name + ".png")),
                width=950,
            )
        )


# %%
if __name__ == "__main__" and "__file__" in globals():
    raise SystemExit(main())
