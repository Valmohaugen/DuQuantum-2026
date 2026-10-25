"""Select verified depth improvements and export a standalone native cache."""

import ast
import hashlib
import json

import cirq
import cirq_google

from .exact_schedule import solve
from .search import BASE, ROOT, error


def main():
    if not hasattr(cirq_google, "Willow105"):
        cirq_google.Willow105 = cirq_google.engine.create_device_from_processor_id("willow_pink")
    original = cirq.read_json(BASE / "circuits.json")
    circuits = cirq.read_json(ROOT / "cp_circuits.json")
    checks = []
    origins = {}
    for path in ROOT.glob("refined_[0-9]*_[0-9]*.json"):
        if path.stem.endswith("_angles"):
            continue
        n, k = map(int, path.stem.split("_")[1:])
        c = cirq.read_json(path)
        assert error(c, n, k) < 1e-10
        c, proof = solve(c, 8)
        checks.append(dict(N=n, k=k, proof=proof))
        if len(c) < len(circuits[f"{n},{k}"]):
            circuits[f"{n},{k}"] = c
            origins[f"{n},{k}"] = "offline_complex_angle_learning"
    peer_path = ROOT / "fresh_peer_circuits.json"
    if peer_path.exists():
        for key, c in cirq.read_json(peer_path).items():
            if len(c) >= len(circuits[key]):
                continue
            n, k = map(int, key.split(","))
            raw_error = error(c, n, k)
            assert raw_error < 1e-5
            raw_depth = len(c)
            c, proof = solve(c, 8)
            assert error(c, n, k) <= max(1e-10, 1.1 * raw_error)
            checks.append(dict(N=n, k=k, raw_peer_depth=raw_depth, proof=proof))
            circuits[key] = c
            origins[key] = "fresh_peer_portfolio"
    table, changes = {}, []
    for key, c in circuits.items():
        n, k = map(int, key.split(","))
        qs = sorted(c.all_qubits())
        idx = {q: i for i, q in enumerate(qs)}
        assert len(c) <= len(original[key])
        err = error(c, n, k)
        assert err < 1e-5
        if len(c) < len(original[key]):
            changes.append(
                dict(
                    N=n,
                    k=k,
                    before=len(original[key]),
                    moments=len(c),
                    CZ=sum(op.gate == cirq.CZ for op in c.all_operations()),
                    state_l2_error=err,
                    gain=n * k * (1 / len(c) - 1 / len(original[key])),
                    source=origins.get(key, "native_recompilation"),
                )
            )
        layers = []
        for moment in c:
            entries = []
            for op in moment:
                if op.gate == cirq.CZ:
                    entries.append(tuple(idx[q] for q in op.qubits))
                else:
                    g = op.gate
                    entries.append(
                        (
                            idx[op.qubits[0]],
                            float(g.x_exponent),
                            float(g.z_exponent),
                            float(g.axis_phase_exponent),
                        )
                    )
            layers.append(tuple(entries))
        table[n, k] = (tuple((q.row, q.col) for q in qs), tuple(layers))
    source = (BASE / "submission.py").read_text()
    assignment = next(
        n
        for n in ast.parse(source).body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "_BONUS_NATIVE" for t in n.targets)
    )
    lines = source.splitlines(True)
    exported = (
        "".join(lines[: assignment.lineno - 1])
        + "_BONUS_NATIVE = "
        + repr(table)
        + "\n"
        + "".join(lines[assignment.end_lineno :])
    )

    def strip(tree):
        return ast.dump(
            ast.Module(
                body=[
                    n
                    for n in tree.body
                    if not (
                        isinstance(n, ast.Assign)
                        and any(
                            isinstance(t, ast.Name) and t.id == "_BONUS_NATIVE" for t in n.targets
                        )
                    )
                ],
                type_ignores=[],
            ),
            include_attributes=False,
        )

    assert strip(ast.parse(source)) == strip(ast.parse(exported))
    (ROOT / "submission.py").write_text(exported)
    cirq.to_json(circuits, ROOT / "best_circuits.json")
    baseline = sum(
        int(key.split(",")[0]) * int(key.split(",")[1]) / len(c) for key, c in original.items()
    )
    score = sum(
        int(key.split(",")[0]) * int(key.split(",")[1]) / len(c) for key, c in circuits.items()
    )
    report = dict(
        baseline_score=baseline,
        score=score,
        gain=score - baseline,
        cases=len(circuits),
        changes=changes,
        new_schedule_checks=checks,
        main_and_constructor_ast_unchanged=True,
        peer_input_sha256=hashlib.sha256(peer_path.read_bytes()).hexdigest()
        if peer_path.exists()
        else None,
        source_sha256=hashlib.sha256(exported.encode()).hexdigest(),
    )
    (ROOT / "summary.json").write_text(json.dumps(report, indent=2))
    print(report)


if __name__ == "__main__":
    main()
