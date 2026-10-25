"""Validate declared observations and compute matched finite benchmark statistics."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np

DESIGN_FIELDS = {
    "calibration_seed",
    "benchmark_cases",
    "benchmark_seeds",
    "detuning_khz",
    "shots",
    "run_ideal_baseline",
}


def validate_declared_records(data: dict) -> None:
    """Reject malformed records and falsely complete declared case/seed sets.

    Legacy payloads without a declared design can only describe observed records.
    A declared complete design must contain every expected mode/case/seed key.
    """
    records = data.get("results")
    if not isinstance(records, dict):
        raise ValueError("results must be a record mapping")
    for key, record in records.items():
        if not isinstance(key, str) or not isinstance(record, dict):
            raise ValueError("each result requires a string key and a record mapping")
    signature = data.get("signature", {})
    if not isinstance(signature, dict):
        raise ValueError("signature must be a mapping")
    settings = signature.get("settings", signature)
    if not isinstance(settings, dict):
        raise ValueError("signature settings must be a mapping")
    if signature.get("schema_version") == 2:
        if not DESIGN_FIELDS <= settings.keys():
            raise ValueError(
                f"incomplete schema-2 settings: missing {sorted(DESIGN_FIELDS - settings.keys())}"
            )
        if (
            type(settings["shots"]) is not int
            or settings["shots"] < 1
            or type(settings["calibration_seed"]) is not int
            or settings["calibration_seed"] < 0
            or type(settings["run_ideal_baseline"]) is not bool
            or not isinstance(settings["detuning_khz"], (int, float))
            or not math.isfinite(settings["detuning_khz"])
            or settings["detuning_khz"] < 0
        ):
            raise ValueError("invalid schema-2 effective design settings")
    if "benchmark_cases" not in settings or "benchmark_seeds" not in settings:
        return
    cases, seeds = settings["benchmark_cases"], settings["benchmark_seeds"]
    if not isinstance(cases, list) or not isinstance(seeds, list) or not cases or not seeds:
        raise ValueError("declared cases and seeds must be nonempty lists")
    if any(not isinstance(seed, int) or isinstance(seed, bool) or seed < 0 for seed in seeds):
        raise ValueError("declared seeds must be nonnegative integers")
    if any(
        not isinstance(case, list)
        or len(case) != 2
        or any(not isinstance(x, int) or isinstance(x, bool) for x in case)
        or case[0] < 1
        or not 0 <= case[1] <= case[0]
        for case in cases
    ):
        raise ValueError("invalid declared case sizes")
    if len(set(seeds)) != len(seeds) or len({tuple(case) for case in cases}) != len(cases):
        raise ValueError("declared seeds and cases must be unique")
    modes = (
        ("dd", "no-dd", "ideal") if settings.get("run_ideal_baseline", True) else ("dd", "no-dd")
    )
    expected = {f"{n},{k},{seed},{mode}" for n, k in cases for seed in seeds for mode in modes}
    missing, extra = expected - records.keys(), records.keys() - expected
    if extra or (data.get("complete") and missing):
        raise ValueError(
            f"incomplete or inconsistent declared experiment: {len(missing)} missing, {len(extra)} unexpected records"
        )


def has_complete_provenance(data: dict) -> bool:
    """Check recorded provenance structure, rather than trusting a schema-version label."""
    signature = data.get("signature", {})
    required = {
        "settings",
        "noise",
        "preparation",
        "sources",
        "scoring_sha256",
        "calibration_sha256",
        "runtime",
    }
    if (
        not isinstance(signature, dict)
        or signature.get("schema_version") != 2
        or not required <= signature.keys()
    ):
        return False
    if (
        not isinstance(signature.get("settings"), dict)
        or not DESIGN_FIELDS <= signature["settings"].keys()
    ):
        return False
    if not all(
        isinstance(signature[key], dict) and signature[key]
        for key in ("settings", "noise", "preparation", "sources", "runtime")
    ):
        return False
    digests = [
        signature["scoring_sha256"],
        signature["calibration_sha256"],
        *signature["sources"].values(),
    ]
    return all(
        isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)
        for value in digests
    )


def _finite(record: dict) -> bool:
    value = record.get("score")
    return (
        record.get("score_status", "finite") == "finite"
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def case_statistics(data: dict) -> list[dict[str, Any]]:
    """Compute matched finite seed pairs per case, retaining explicit excluded counts.

    Standard deviations describe seed dispersion. A singleton SD is displayed
    as zero by convention; its standard error is unknown, represented by null.
    Missing/undefined/infinite observations never become zero-valued scores.
    """
    validate_declared_records(data)
    cases: dict[tuple[int, int], dict[str, dict[int, dict]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for key, record in data["results"].items():
        fields = key.split(",")
        if len(fields) != 4:
            raise ValueError(f"invalid result key {key!r}")
        n, k, seed = map(int, fields[:3])
        if fields[3] not in ("dd", "no-dd", "ideal") or not isinstance(record, dict):
            raise ValueError(f"invalid result mode or record {key!r}")
        cases[(n, k)][fields[3]][seed] = record
    rows = []
    for (n, k), modes in sorted(cases.items()):
        dd, no_dd = modes.get("dd", {}), modes.get("no-dd", {})
        seeds = sorted(
            seed for seed in dd.keys() & no_dd.keys() if _finite(dd[seed]) and _finite(no_dd[seed])
        )
        a, b = (
            np.array([dd[s]["score"] for s in seeds]),
            np.array([no_dd[s]["score"] for s in seeds]),
        )
        differences = a - b
        # The same physical seed is paired; per-case means do not supply its uncertainty.
        count = len(seeds)
        rows.append(
            {
                "n": n,
                "k": k,
                "seeds": seeds,
                "dd_scores": a.tolist(),
                "no_dd_scores": b.tolist(),
                "n_pairs": count,
                "excluded": len(dd.keys() | no_dd.keys()) - count,
                "dd_mean": float(a.mean()) if count else None,
                "no_dd_mean": float(b.mean()) if count else None,
                "dd_std": float(a.std(ddof=1)) if count > 1 else 0.0,
                "no_dd_std": float(b.std(ddof=1)) if count > 1 else 0.0,
                "difference": float(differences.mean()) if count else None,
                "difference_se": float(differences.std(ddof=1) / np.sqrt(count))
                if count > 1
                else None,
                "moments": next(iter(dd.values()), next(iter(no_dd.values()), {})).get("moments"),
            }
        )
    return rows


def paired_aggregate(rows: list[dict]) -> dict:
    """Average each common seed over all cases, then estimate paired seed uncertainty.

    Only seeds with finite DD/no-DD scores in every case enter the aggregate.
    Between-case heterogeneity is never treated as uncertainty of that mean.
    """
    common = set(rows[0]["seeds"]) if rows else set()
    for row in rows:
        common &= set(row["seeds"])
    dd, no_dd = [], []
    for seed in sorted(common):
        dd.append(float(np.mean([row["dd_scores"][row["seeds"].index(seed)] for row in rows])))
        no_dd.append(
            float(np.mean([row["no_dd_scores"][row["seeds"].index(seed)] for row in rows]))
        )
    delta = np.asarray(dd) - np.asarray(no_dd)
    count = len(delta)
    return {
        "n_pairs": count,
        "seeds": sorted(common),
        "dd_seed_means": dd,
        "no_dd_seed_means": no_dd,
        "dd_mean": float(np.mean(dd)) if count else None,
        "no_dd_mean": float(np.mean(no_dd)) if count else None,
        "difference": float(delta.mean()) if count else None,
        "difference_se": float(delta.std(ddof=1) / np.sqrt(count)) if count > 1 else None,
    }
