# Submission checklist

- [ ] Export the current canonical module:
  `python -m claude.scripts.build_submission submission_outputs/submission.py`.
- [ ] Run the complete offline suite, artifact checks, and pre-commit in `duquantum`.
- [ ] Confirm both required functions exist and the export imports outside the repository.
- [ ] Confirm only standard-library, Cirq, cirq-google, and their dependencies are imported.
- [ ] Apply the organizer's email corrections from `CHALLENGE_CORRECTIONS.md`: bonus grading
  uses `range(2, 16)`, and `test_circuit` uses `range(len(qubits))`. Keep the original file intact.
- [ ] Confirm supported circuits use calibrated native gates, respect routing, and have at most
  1,750 moments. Unsupported requests must raise `NotImplementedError`.
- [ ] Keep the original challenge notebook unchanged. Its validator has a known bug; use the
  independent exact-state checks and the tested Python implementation.
- [ ] Prepare all supporting material requested by the original challenge and current upload form.
- [ ] Review the actual upload form's current instructions and submit by hand.

The development code includes local simulation only. Flipping a flag does not submit a job.
The adaptive entry point is a legal non-adaptive fallback; the rules allow it. The confirmed
bonus grading range is 2 ≤ N ≤ 15. Extra N=16–20 tests are stress tests. The hidden (N,n) choices
and `max_correlator_size` are not inferred from local benchmark settings. No submission, hardware
run, or GitHub publication is automatic.
