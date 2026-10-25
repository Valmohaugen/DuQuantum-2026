# Exact synthesis adapted from test_sol.py

The maintained solver now uses the useful circuit ideas from the user-provided candidate
without its fitted angle tables. The original constructor remains available with
`--construction analytic`; `--construction optimized` is the default. Both policies use
the same validation, scheduling, calibration input, scoring and artifact pipeline.

Source: /Users/valentine/Downloads/test_sol.py, SHA-256
5a9bc743c89a4f5af1e561c8162ba3af2aeb8d795a45d9dc00fd1fbb23c3f245.
The split/shift recursion is from [Bärtschi & Eidenbenz, Section 2](https://arxiv.org/abs/1904.07358).
The exact local synthesis identities below were independently derived from the supplied
candidate; they are not claimed as identities stated in that paper.

## Four-CZ replacement, derived before implementation

Use big-endian |abc> basis order, Ry(t)=[[cos(t/2),-sin(t/2)],
[sin(t/2),cos(t/2)]], and CZ_ab|abc>=(-1)^(ab)|abc>.
For independent real angles alpha,beta, apply:

| Group | Chronological operations |
| --- | --- |
| 1 | Ry_a(-alpha), Ry_c(-pi/2), CZ_ab |
| 2 | Ry_a(alpha), Ry_b(pi/2), CZ_bc |
| 3 | Ry_b(pi/2+beta), Ry_c(beta), CZ_ab |
| 4 | Ry_b(-pi/2), CZ_bc, Ry_b(-pi/2), Ry_c(pi/2) |

Multiplying these elementary matrices gives the ordered columns for inputs 000,001,011:

```text
output       input000    input001    input011
000              1           0           0
001              0       cos(beta)       0
010              0       sin(beta)       0
011              0           0       cos(alpha)
100              0           0           0
101              0           0           0
110              0           0       sin(alpha)
111              0           0           0
```

All columns have the same positive phase. The original first Givens followed by the
adjacent flagged shift has these columns: 000 stays; 001 first sees G on 00 and then
the beta split; 011 first splits into cos(alpha)011+sin(alpha)101, and the flagged
shift takes 101 to 110 while preserving 011. Consequently the replacement works on
an arbitrary superposition, including inputs entangled with untouched qubits.

In an m-qubit recursion stage, the first possible excitation count is r. Substituting
alpha=acos(sqrt(r/m)), beta=acos(sqrt((r-1)/m)) reproduces both probabilities. The
stage's sorted prefix has first-three-bit input 011 for count r, 001 for count r-1,
and 000 for lower counts. This holds at m>k. At m<=k an all-one prefix can occur;
the replacement is disabled there. If a second adjacent MUX is absent, keep the
existing first known-input optimization and unflagged shifts instead.

The merged pattern uses CZ_ab,CZ_bc,CZ_ab,CZ_bc: two per adjacent edge. The old pair
used two CZ_ab plus one CZ_ab and four CZ_bc, seven total. Save three and recompute
the edge loads before physical layout search. Keep all remaining pruned logical gates.

Limits checked: alpha=beta=0 preserves inputs; alpha=beta=pi/2 performs positive
full shifts; alpha=beta=pi/4 yields positive equal amplitudes. Mixed endpoints and
arbitrary unequal angles are also tested. Independent full-state checks cover all
152 requests N=1–16, k=0–N, including zero/full excitation and complementary states.

## Five-CZ D(4,2) square, exact closed form

Label a square as 0,1 on its top row and 2,3 on its bottom row. Start in |0000>.
Let a=atan2(2,1), b=2asin(1/sqrt(6)), c=cos(a/2), s=sin(a/2). Then
c=sqrt((5+sqrt(5))/10), s=sqrt((5-sqrt(5))/10), cos(b/2)=sqrt(5/6).

Apply initial Ry angles (a,-pi/2,b,pi/2), followed by these CZ and Ry groups:

| Group | CZ | Following Ry gates |
| --- | --- | --- |
| 1 | (3,2) | Ry_3(-pi), Ry_2(0) |
| 2 | (2,0) | Ry_2(-pi/2), Ry_0(a) |
| 3 | (0,1) | Ry_0(pi/2), Ry_1(pi) |
| 4 | (2,0) | Ry_2(pi), Ry_0(-3pi/2) |
| 5 | (1,3) | Ry_1(pi/2), Ry_3(-pi) |

After group 1 the state factors as
(c|0>+s|1>)_0 (|0>-|1>)_1/sqrt(2) times
[sqrt(5)(|00>-|01>)-|10>-|11>]_23/sqrt(12).
Applying the remaining matrices gives these intermediate states, with all bitstrings
in label order 0123:

```text
After group 2, multiply the following vector by 1/sqrt(12):
 -0001 -0010 +0101 +0110 +1000 -1001 -1010 +1011 -1100 +1101 +1110 -1111

After group 3, multiply by 1/(2sqrt(6)):
 +0000 +0011 -0100 -0111 -1000 -1011 +1100 +1111
 -2*0001 -2*0010 -2*1101 -2*1110

After group 4, multiply by 1/sqrt(12):
 -0000 -0010 +0011 -0100 +0110 -0111 -1000 +1001 +1011 +1100 -1101 +1111

After group 5:
 (0011+0101+0110+1001+1010+1100)/sqrt(6) = +D(4,2).
```

Thus all six target amplitudes are equal and positive, every other amplitude is zero,
and the state is normalized. No fitted numbers remain. Independent symbolic algebra
and native Cirq complex128 checks agree, with amplitude residual below 3e-16.
All eight square rotations/reflections preserve the target state by permutation symmetry.

## Physical selection, compatibility and limitations

Only a complete calibrated square is eligible. Enumerate its eight labelings and minimize
the same node/coupler cost used for path selection, counting the repeated edge twice.
Prefer the five-CZ square when its cost estimate is no worse than the available optimized
path; a costly/missing square keeps the path. A square remains usable if a heuristic path
search fails. Connected-patch routing, timing, native gates and the 1,750-moment cap remain
enforced. Calibration cost is a heuristic, not an expected noisy score.

The chosen construction is saved in PrepConfig, benchmark fingerprints, reports and
standalone exports. Existing datasets lacking the new field resolve to the original
analytical constructor, so their diagnostics are not silently rebuilt with a new circuit.
No dependency on Downloads, SymPy, a runtime optimizer or lookup tables is introduced.

The original challenge notebook and upstream reference files are unchanged. New matched
experiments and figures use separate run folders; older recorded results are retained.
See OPTIMIZED_SYNTHESIS_PLAN.md for the verified safety snapshot and integration status.
