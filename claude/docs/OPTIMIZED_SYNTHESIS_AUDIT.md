Independent audit of analytic split/shift and square optimizations

The replacement is valid on the reachable sorted-prefix subspace and both improvements can use closed-form angles. No fitted-angle table is required. All repository and reference files were read only; probes and evidence are confined to this directory.

1. Original split/shift convention and source residuals

For local width k+1 and r=1,...,k, the input is |0^(k+1-r)1^r>. The required output is sqrt(r/m)|0^(k+1-r)1^r> + sqrt((m-r)/m)|0^(k-r)1^r0>; r=0 stays all zero. Direct application of the canonical ideal Givens/mux step agrees with this expression for every source-table entry, with worst amplitude residual 8.93e-16.

All 81 source block entries have one common phase across every reachable basis column. No input-dependent phase mismatch was found. Their fitted angles are approximate: worst amplitude residual 1.38146e-6 at (m,k)=(13,6), followed by 1.35399e-6 at (12,8). Source D(4,2) angles have residual 7.32211e-9. These source constants should not be described as exact at a 1e-12 amplitude tolerance. `residuals.json` contains every entry and phase.

2. Four-CZ analytic kernel

Let a and b be arbitrary real angles. On q0,q1,q2, apply:

Ry(-a)[0], Ry(-pi/2)[2], CZ01, Ry(a)[0], Ry(pi/2)[1], CZ12, Ry(pi/2+b)[1], Ry(b)[2], CZ01, Ry(-pi/2)[1], CZ12, Ry(-pi/2)[1], Ry(pi/2)[2].

The exact reachable-column matrix, in ordered inputs 000,001,011 and output rows 000,...,111, is

[[1,0,0], [0,cos(b),0], [0,sin(b),0], [0,0,cos(a)], [0,0,0], [0,0,0], [0,0,sin(a)], [0,0,0]].

There is no relative or common phase. `four_cz_identity.py` proves this by multiplying the elementary matrices symbolically and reducing only c_a^2+s_a^2=c_b^2+s_b^2=1. The zero-angle limit retains all three inputs; the a=b=pi/2 limit fully shifts the two nonzero-weight inputs.

This matrix equals the original first Givens(a), followed by its adjacent mux(b), on the sorted-prefix states. For a split/shift step m>k>=2, a=acos(sqrt(k/m)), b=acos(sqrt((k-1)/m)). The remaining original pruned gates can be retained exactly. Every such replacement saves three CZ gates. Restrict replacement to adjacent first Givens/mux gates in the same step; preserve the m>k guard and known-first-product split optimization. The local identity is subspace restricted, so a full-unitary equality assertion is inappropriate.

Replacing the entire step by the uniform 5k-6 CZ structure is cheaper only when r_min<=1 and ties at r_min=2. Partial replacement gives greater savings while retaining all pruning. The separate original pruning for m<=k remains necessary: all-ones prefix branches must not acquire an accidental relative phase.

`global_partial.json` independently checks the partial strategy for all 152 (N,k) requests with N=1,...,16 and k=0,...,N. Worst final amplitude residual is 5.26e-16. This includes k=0, k=N, and the m<=k boundary. The probe uses ideal Givens plus the explicit elementary four-CZ kernel, without the maintained solver's optimized implementation.

3. Analytic five-CZ D(4,2)

Use the original square sequence ((3,2),(2,0),(0,1),(2,0),(1,3)). Let a=atan2(2,1), b=2*asin(1/sqrt(6)). The initial four Ry angles followed by two Ry angles after each CZ are:

[a,-pi/2,b,pi/2,-pi,0,-pi/2,a,pi/2,pi,pi,-3pi/2,pi/2,-pi].

The initial q2,q3 product has coefficients [sqrt5,sqrt5,1,1]/sqrt12. CZ32 changes the 11 sign; the following Ry(-pi) on q3 sends it to psi23=[sqrt5,-sqrt5,-1,-1]/sqrt12. Qubit 0 is [cos(a/2),sin(a/2)] and qubit 1 is [1,-1]/sqrt2. Multiplying the remaining four CZ groups and their stated rotations gives exactly six nonzero amplitudes at 0011,0101,0110,1001,1010,1100, each +1/sqrt6. There is no global phase. `d42_symbolic.json` records every intermediate sparse amplitude vector, and `d42_symbolic.py` proves the final equality with exact radicals.

Native Cirq complex128 verification gives maximum amplitude error 2.78e-16 (`d42_analytic.json`). The construction requires the four square edges 01,02,13,23, with edge 02 used twice. Preserve the line fallback when a complete calibrated square is unavailable. Every square labeling is valid because the final Dicke target is permutation invariant.

4. Additional numerical evidence

Independent forward-mode analytic-Jacobian least-squares polishing works for the raw data: (3,2), (13,6), and (12,8) reach errors 3.14e-16, 5.69e-16, and 3.33e-16 in three or four evaluations. An independently polished D42 solution reached 1.67e-16 (NumPy) and 2.78e-16 (native Cirq), but the closed-form version above is preferable. The polished-angle evidence remains in `polish_evidence.json` and `d42_certificate.json`.

Scope limits: this audit covers exact ideal state behavior and CZ structure. It does not claim a noisy-score improvement, execute hardware, or run the repository's full suite. Parent integration tests cover native scheduling, calibrated layout selection, fallback behavior, CLI export, and full repository regression checks.
