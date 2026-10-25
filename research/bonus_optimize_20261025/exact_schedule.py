"""CP-SAT scheduling of a fixed native gate list with diagonal commutation."""

import json
import time
from pathlib import Path

import cirq
import cirq_google
import numpy as np
from ortools.sat.python import cp_model

from .search import error

ROOT = Path(__file__).parent


def graph(circuit):
    ops = list(circuit.all_operations())
    diagonal = []
    for op in ops:
        u = cirq.unitary(op)
        diagonal.append(bool(np.max(np.abs(u - np.diag(np.diag(u)))) < 1e-13))
    wires = {q: [] for q in circuit.all_qubits()}
    moment_index = {}
    i = 0
    for t, moment in enumerate(circuit):
        for op in moment:
            moment_index[i] = t
            for q in op.qubits:
                wires[q].append(i)
            i += 1
    predecessors = [set() for _ in ops]
    for wire in wires.values():
        last, pending = None, []
        for i in wire:
            if last is not None:
                predecessors[i].add(last)
            if diagonal[i]:
                pending.append(i)
            else:
                predecessors[i].update(pending)
                last, pending = i, []
    prefix = [0] * len(ops)
    for i, ps in enumerate(predecessors):
        prefix[i] = max((prefix[j] + 1 for j in ps), default=0)
    return ops, wires, predecessors, prefix, moment_index


def solve(circuit, seconds):
    ops, wires, predecessors, prefix, hints = graph(circuit)
    lower = max(max(prefix) + 1, max(map(len, wires.values())))
    if lower == len(circuit):
        return circuit, dict(status="FIXED_DAG_OPTIMAL", lower_bound=lower, seconds=0)
    model = cp_model.CpModel()
    starts = [model.new_int_var(prefix[i], len(circuit) - 1, f"s{i}") for i in range(len(ops))]
    intervals = [model.new_fixed_size_interval_var(s, 1, f"g{i}") for i, s in enumerate(starts)]
    for wire in wires.values():
        model.add_no_overlap([intervals[i] for i in wire])
    for i, ps in enumerate(predecessors):
        for j in ps:
            model.add(starts[i] >= starts[j] + 1)
    depth = model.new_int_var(lower, len(circuit), "depth")
    for s in starts:
        model.add(depth >= s + 1)
    model.minimize(depth)
    for i, s in enumerate(starts):
        model.add_hint(s, hints[i])
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 20261025
    status = solver.solve(model)
    record = dict(
        status=solver.status_name(status),
        lower_bound=lower,
        proven_bound=solver.best_objective_bound,
        seconds=solver.wall_time,
    )
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return circuit, record
    moments = [[] for _ in range(int(solver.value(depth)))]
    for i, op in enumerate(ops):
        moments[solver.value(starts[i])].append(op)
    return cirq.Circuit(cirq.Moment(m) for m in moments if m), record


def main():
    if not hasattr(cirq_google, "Willow105"):
        cirq_google.Willow105 = cirq_google.engine.create_device_from_processor_id("willow_pink")
    circuits = cirq.read_json(ROOT / "circuits.json")
    rows, gains = [], []
    started = time.monotonic()
    keys = sorted(
        circuits,
        key=lambda key: (
            -np.prod(list(map(int, key.split(","))))
            / (len(circuits[key]) * (len(circuits[key]) - 1))
        ),
    )
    for key in keys:
        if time.monotonic() - started > 180:
            break
        n, k = map(int, key.split(","))
        before = circuits[key]
        trial, row = solve(before, 8)
        row.update(case=key, before=len(before), after=len(trial))
        if len(trial) < len(before):
            old_error = error(before, n, k)
            new_error = error(trial, n, k)
            assert new_error <= max(1e-10, 1.1 * old_error)
            row["state_l2_error"] = new_error
            circuits[key] = trial
            gains.append(row)
            print("GAIN", row, flush=True)
        rows.append(row)
        print(key, row, flush=True)
        cirq.to_json(circuits, ROOT / "cp_circuits.json")
        (ROOT / "cp_results.json").write_text(
            json.dumps(
                dict(
                    rows=rows,
                    improvements=gains,
                    score=sum(
                        np.prod(list(map(int, key.split(",")))) / len(c)
                        for key, c in circuits.items()
                    ),
                    seconds=time.monotonic() - started,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
