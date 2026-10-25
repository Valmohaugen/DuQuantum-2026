"""Finite register bounds and deliberately unoptimized network examples.

No quantum simulation, synthesis, or hardware routing. Run with stdlib Python.
This is a resource screen, not an emitted candidate or an impossibility proof
for all deterministic Dicke-state constructions.
"""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
baseline_path = ROOT / 'research/bonus_terminal_integration_20261025/integration_results.json'
baseline = json.loads(baseline_path.read_text())
rows = []
for n in (8, 12, 15):
    b = (n - 1).bit_length()  # optimistic zero-based permutation labels
    record_lb = (math.factorial(n) - 1).bit_length()
    # Exact odd-even transposition network counts, without power-of-two padding.
    layers = [[(i, i + 1) for i in range(t % 2, n - 1, 2)] for t in range(n)]
    comparators = sum(map(len, layers))
    assert comparators == n * (n - 1) // 2
    frozen = next(r for r in baseline['rows'] if r['N'] == n and r['k'] == n // 2)
    rows.append({
        'N': n, 'k': n // 2, 'label_bits_per_item': b,
        'record_bits_information_lower_bound': record_lb,
        'outer_ancilla_lower_bound': n * b + record_lb,
        'outer_total_qubits_lower_bound': n + n * b + record_lb,
        'outer_bound_exceeds_105': n + n * b + record_lb > 105,
        'literal_generic_merge_reversible_sort_qubits_lower_bound': 4 * n * b + 2 * record_lb,
        'example_network': 'odd-even transposition, no padding',
        'example_layers': layers, 'example_comparators': comparators,
        'example_outer_total_qubits_without_scratch': n + n * b + comparators,
        'outer_cswap_calls_before_optimization': 3 * (b + 1) * comparators,
        'outer_cswap_layer_schedule_before_decomposition': 3 * (b + 1) * n,
        'frozen_native_portfolio': {'depth': frozen['depth'], 'CZ': frozen['CZ'], 'qubits': n},
        'full_native_CZ_count': None, 'full_native_depth': None,
        'Willow_routing_depth': None,
    })

audit = {
    'status': 'Read-only resource screen complete; finite native implementation remains unbuilt',
    'source': {
        'title': 'Low-Depth Quantum Symmetrization',
        'authors': ['Zhenning Liu', 'Andrew M. Childs', 'Daniel Gottesman'],
        'citation': 'Physical Review X 16, 031056 (2026)',
        'published': '2026-08-31',
        'url': 'https://journals.aps.org/prx/pdf/10.1103/9qhy-ms2y',
        'read_sections': ['Result 2', 'II A/C/D', 'III C, Eqs. 36-41', 'IV A/B', 'VIII'],
        'finding': 'Result 2 is unitary and succeeds with probability one. It uses exact lower-exceeding-sequence permutation generation, reversible merging, sorting, prefix sums, and subgroup cleanup. The outer construction retains input, permutation-label and comparison-record registers. Each sorting comparator gets a record bit. Its six outer network passes include three on labels and three on data. Comparator arithmetic, conditional swaps and uniform interval preparation require native decomposition; sorting requires routing. The paper supplies asymptotic costs, not a finite Willow netlist. Restricted-connectivity sorting remains open. For a known single input, subgroup junk factors from the output; cleaning it is still needed if a clean-ancilla interface is required.',
    },
    'derivation': {
        'scope': 'Our independent arithmetic for the direct register layout, not a lower bound on all possible implementations.',
        'label_width': 'Optimistically relabel 1..N as 0..N-1; b=ceil(log2 N). Literal positive binary labels require an extra bit at N=8.',
        'record_bound': 'N! distinct permutation inputs must yield distinct sorting records, so C>=ceil(log2(N!)).',
        'qubit_bound': 'N data + N*b labels + C records, simultaneously live in Eq.36; excludes generator, comparator, merge and cleanup scratch.',
        'network_example': 'N alternating even/odd adjacent comparator layers have N*(N-1)/2 comparators. This explicit selection is illustrative and not optimized.',
        'cswap_count': 'For six outer passes with widths b,1,b,1,b,1: 3*(b+1)*C bitwise controlled swaps. This excludes comparison predicates and all resource preparation/cleanup.',
        'cswap_schedule': 'Serial bit swaps sharing each comparator control and parallel disjoint comparators give 3*(b+1)*N controlled-swap layers for this example. These are NOT native CZ moments or a lower bound after optimization.',
        'literal_merge_screen': 'Eq.51 stores three-word tuples at the top merge. Applying the generic Eq.27 reversible-sort construction literally needs 3*N*b tuple bits, N*b auxiliary labels, and two C-bit record registers: at least 4*N*b+2*ceil(log2(N!)) = 128/250/322 bits at N8/12/15. This conditional bound assumes full generic sorting networks, no promise-specialized record compression, no register elision, and optimistic b-bit words. It is not a lower bound on an optimized specialized merge.',
    },
    'rows': rows,
    'native_implementation_gaps': [
        'Select and emit exact LES interval preparations and the recursive merging/arithmetic circuits with scratch lifetimes.',
        'Decompose comparison predicates, controlled swaps, additions and conditional interval preparations to allowed one-qubit gates and two-qubit CZ.',
        'Provide an injective Willow placement, route every logical interaction, and count native moments after optimization.',
        'Revalidate coherent subgroup cleanup; for fixed k, exploit constant duplicate structure only with an explicit proof.',
    ],
    'measurement_status': 'The audited deterministic route uses no measurements; no postselection or diagonal feed-forward exemption is assumed.',
    'recommendation': 'Do not start synthesis for the direct construction. N15 fails the optimistic 105-qubit register screen; N8/N12 have no demonstrated depth benefit. Revisit only with a compressed-record or specialized fixed-weight construction and an explicit resource schedule.',
    'limits': 'Full finite ancilla maxima, native depth and Willow routing are undetermined. PORT-008 implementation acceptance checks remain unmet; this negative screen is not a completed native candidate.',
    'baseline': {'path': str(baseline_path.relative_to(ROOT)), 'sha256': hashlib.sha256(baseline_path.read_bytes()).hexdigest(), 'score': baseline['score']},
}
(HERE / 'resource_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
print(json.dumps({'status': audit['status'], 'rows': [{k: r[k] for k in ('N', 'outer_total_qubits_lower_bound', 'example_outer_total_qubits_without_scratch', 'outer_cswap_calls_before_optimization', 'frozen_native_portfolio')} for r in rows]}, indent=2))
