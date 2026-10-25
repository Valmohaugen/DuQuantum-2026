# Figures

Publication figures for the QuBillionaires solution
([`qubillionaires_solution.py`](../qubillionaires_solution.py)). Each figure comes as a vector PDF and a 600 dpi PNG.

The figures follow IEEE sizing rules:
- Width is 3.5 in for a single column and 7.16 in for double.
- Text is 8 pt sans serif (qubit and cell labels 7 pt).
- PDFs embed TrueType (Type 42) fonts.
- No titles inside the figure, so captions go in the paper.

The numbers behind every figure are in [`data/`](data). To redraw or recompute:

```bash
python figures/make_figures.py      # redraw from figures/data/ (seconds)
python figures/compute_data.py      # recompute figures/data/ (about 15 min on one core)
```

Main-entry figures use the challenge notebook's synthetic calibration recipe (`archive/judge.py`,
`fake_calibration`, seed 0 for layouts and seeds 0–2 for scores). They illustrate the method;
they do not predict a hardware score.

## Suggested captions

**Fig. 1** ([pdf](fig1_layout_main.pdf), [png](fig1_layout_main.png)), single column. Main-entry
circuit for D(10,5) placed on the Willow chip under a synthetic calibration. The coloured qubits
are the ones `create_dicke_state` selected, shaded by expected readout error
(1 − n/N)·e₀₁ + (n/N)·e₁₀. The scale runs from the chip minimum to its 95th percentile, so the
chosen qubits can be compared with the alternatives. Couplers are shaded by the number of CZ gates
the circuit applies on them. Gray qubits and couplers are unused, and × marks a qubit dropped by
the calibration. The circuit has 35 moments and 42 CZ gates.

**Fig. 2** ([pdf](fig2_layout_bonus.pdf), [png](fig2_layout_bonus.png)), single column. Bonus-entry
circuit for D(10,5): 29 moments, 48 CZ gates. The bonus gets no calibration data, so qubits are
shaded by the moment of their first CZ, which shows how the entanglement spreads. Couplers are
shaded by CZ count.

**Fig. 3** ([pdf](fig3_bonus_depth.pdf), [png](fig3_bonus_depth.png)), double column. Bonus results
for all 56 graded cases, 2 ≤ N ≤ 15 and 1 ≤ n ≤ ⌊N/2⌋. (a) Circuit depth in moments. (b) Each
case's contribution N·n/depth to the bonus score, which totals 52.482. Every circuit is exact and
passes `Willow105.validate_circuit`.

**Fig. 4** ([pdf](fig4_score_history.pdf), [png](fig4_score_history.png)), single column. Score over
the hackathon, one marker per pushed improvement (commit times; sources in
[`data/progression.csv`](data/progression.csv)). (a) Verified bonus score on the 56-case metric,
46.18 → 52.48. (b) Main entry in the local noise model: summed expected score over N = 2–8,
three calibrations, 16.62 → 17.66.

**Fig. 5** ([pdf](fig5_main_scores.pdf), [png](fig5_main_scores.png)), single column. Main-entry
expected score 1/(Z + X) for every case with N ≤ 8 and n ≤ N/2. Each bar is the mean over three
synthetic calibrations in the local noise model (gate and readout errors, T1/T2, 7.5 kHz detuning).
Ticks mark the noiseless limit for 10,000 shots per basis, where the Z term's shot-noise floor
remains even for a perfect state. The circuits reach 17.66 of the possible 19.18 (92 %).
