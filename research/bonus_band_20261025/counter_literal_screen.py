"""Finite-size screen of the literal three-batch counter architecture.

This is a resource bound on a specified stage-separated implementation, not
a lower bound on the unitary or on all optimizations of the cited paper.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).parent


def batches(n):
    m = n.bit_length()
    groups = [[], [], []]
    for _ in range(n//m):
        target = min(range(3), key=lambda i: len(groups[i]))
        groups[target].append(m)
    if n % m:
        target = min(range(3), key=lambda i: len(groups[i]))
        groups[target].append(n % m)
    # An input block requires a distinct full m-qubit dirty word outside
    # its own batch. This simple construction is unavailable otherwise.
    feasible = all(sum(s == m for j, g in enumerate(groups) if j != i for s in g) >= len(group)
                   for i, group in enumerate(groups))
    return m, groups, feasible


def main():
    validation = json.loads((ROOT/'native_submission_verified.json').read_text())
    incumbent = {(r['N'], r['k']): r['depth'] for r in validation['rows']}
    rows = []
    for n in range(2, 16):
        m, groups, feasible = batches(n)
        for k in range(1, n//2+1):
            p = math.comb(n, k)*(k/n)**k*(1-k/n)**(n-k)
            q = math.ceil(math.pi/(4*math.asin(math.sqrt(p)))-.5-1e-12)
            # D contains controlled phases for every source/dirty-word pair.
            # For m>=2, at least one dirty target has a non-Clifford phase;
            # its s controls cost 2s CZ in an individually decomposed D.
            # D^-1 is separate, three batches serial; ADD cost is omitted.
            counter_cz_layers = 4*sum(max(group, default=0) for group in groups) if feasible else None
            # Standard fixed-pi amplification: q iterations, two reflections
            # each, each reflection computes and uncomputes the counter.
            literal_lower = 4*q*counter_cz_layers if feasible else None
            rows.append(dict(N=n, k=k, output_qubits=n+m, count_bits=m,
                             batch_source_lengths=groups, borrowed_workspace_feasible=feasible,
                             max_product_overlap_squared=p, fixed_pi_iterations=q,
                             literal_counter_CZ_layer_bound=counter_cz_layers,
                             literal_preparation_CZ_layer_bound=literal_lower,
                             literal_target_reflections_only_bound=2*q*counter_cz_layers if feasible else None,
                             incumbent_native_depth=incumbent[n, k]))
    result = dict(status='literal architecture screened; no routed candidate or gain', rows=rows,
        source=dict(title='Exact quantum Hamming-weight computation at optimal depth and minimum width',
                    url='https://arxiv.org/html/2610.25315', submitted='2026-10-18',
                    consulted_sections=['III.1', 'V.1', 'V.2', 'Appendix A'],
                    summary='The paper gives an exact n+ceil(log2(n+1))-qubit all-to-all counter. Its three input batches borrow and restore dirty words. It applies the counter to expected-depth adaptive balanced-state preparation and fixed-weight unitary amplitude amplification.'),
        local_derivation='Each literal D/D-inverse stage separately decomposes controlled phases. A fractional-phase dirty target requires two CZ per control. Serial batch boundaries are preserved; additions, Fourier transforms, reflections, and routing are omitted. Reported bounds are lower bounds on CZ layers for this specified literal decomposition, not full circuit depths or universal lower bounds.',
        exclusions='The bound does not cover cross-stage cancellation, collective phase synthesis, replacing the zero-weight reflection, generalized final amplification phases, a different counter, or another preparation algorithm. It is not a lower bound on exact Dicke preparation.',
        challenge_inference='Almost-sure termination and expected adaptive depth do not provide a finite returned Cirq circuit that succeeds on every branch. A bounded exact fallback and legal readout diagonals would need explicit construction. Unitary circuits avoid this measurement issue but still require native routing.',
        next_action='Do not port the literal small-N three-batch architecture. A future optimized counter proposal must beat the native depth budget after both weight reflections, routing, and all amplification iterations; record any changed stage assumptions.')
    (ROOT/'counter_literal_screen.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps([r for r in rows if r['N'] in (8, 12, 14, 15) and r['k'] == r['N']//2], indent=2))


if __name__ == '__main__':
    main()
