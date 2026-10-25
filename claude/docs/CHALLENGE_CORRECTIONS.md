# Organizer corrections supplied by email

The user supplied this organizer clarification during the October 24, 2026 repair session.
The email's send date was not supplied. It corrects interpretation of the protected original
challenge notebook; that file is intentionally unchanged.

1. Bonus grading covers **2 ≤ N ≤ 15**. The bonus `score_solution` loop should be
   `for num_qubits in range(2, 16)`.
2. In `test_circuit`, `keep_indices = range(qubits)` should be
   `keep_indices = range(len(qubits))`.
3. Grading choices of `(N,n)` and `max_correlator_size` will not be disclosed in advance.

The canonical preparation does not use a correlator cutoff or a list of grading cases.
The independent validator checks the complete ideal state, gates, routing, qubit count and
moment limit. Regression tests cover all excitation counts 0 ≤ n ≤ N through the confirmed
bonus range structurally, exact states for all those counts through N=11, and selected larger
states including complements through N=16. Extra N=16–20 cases are stress tests. The local
finite-shot benchmark's cases and cutoff of four are explicit model choices, not grading claims.

The earlier review report records what the original notebook contained at review time.
Its observations about the old N≤20 loop remain historical evidence; this clarification
supersedes that loop when describing the official grading scope.
