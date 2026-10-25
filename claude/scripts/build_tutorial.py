"""Write claude/tutorial/Dicke_Tutorial.ipynb, an interactive walk-through of the solution
in the canonical Python module claude/dicke_prep.py.

The notebook is generated so its source stays reviewable as plain Python. It only
reads the challenge notebook (for the official scoring functions) and never writes it.

Usage: python claude/scripts/build_tutorial.py
"""

from __future__ import annotations

from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = ROOT / "tutorial" / "Dicke_Tutorial.ipynb"

CELLS: list[tuple[str, str]] = []


def md(src: str) -> None:
    CELLS.append(("md", src.strip("\n")))


def code(src: str) -> None:
    CELLS.append(("code", src.strip("\n")))


# --------------------------------------------------------------------------- #
md(r"""
# Preparing Dicke states on Google Willow: an interactive tutorial

This notebook explains, step by step, how the tested module `claude/dicke_prep.py`
(imported here as `dp`) builds the circuits for the
Google Quantum AI challenge. That challenge asks for an $N$-qubit, weight-$n$ Dicke state
on the Willow 105-qubit chip, using only CZ and `PhasedXZGate`.

**What you will learn**

1. What a Dicke state is, and the recursion that builds one.
2. The Givens rotation, the one two-qubit building block.
3. The *split-and-cyclic-shift* construction, watched gate by gate.
4. The 5-CZ "multiplexed" gate that keeps every interaction between neighbouring qubits.
5. Why the W state ($n = 1$) uses a tree instead.
6. How the qubits are chosen on the noisy chip, how the circuit is scheduled, and how it is scored.

**How to use it.** Run the cells top to bottom (*Run All* works). Cells marked 🎛️ have
sliders. Cells marked ✏️ are exercises; open *Solution* only after trying. If `ipywidgets`
is missing, the interactive cells run once with default values. You can then edit those values
in the call.

**Background assumed:** kets, tensor products, and what CZ and single-qubit rotations do.
""")

md("## 0. Setup")
code(r"""
import math
import sys
from pathlib import Path

import cirq
import cirq_google
import matplotlib.pyplot as plt
import numpy as np

REPO = Path.cwd().resolve()
while not (REPO / "solution.ipynb").exists():  # repo root or claude/tutorial/
    if REPO == REPO.parent:
        raise FileNotFoundError("run this notebook from inside the DuQuantum-2026 repo")
    REPO = REPO.parent
sys.path.insert(0, str(REPO))

from claude import dicke_prep as dp  # noqa: E402
from claude.notebook_figures import save_and_show  # noqa: E402
from claude.scripts.challenge_calibration import make_challenge_calibration as fake_calibration  # noqa: E402
from claude.tutorial.tutorial_utils import (  # noqa: E402
    HAVE_WIDGETS, bits, dicke_vector, draw_willow, interactive, plot_line_occupation, plot_probs,
)

# Faster layout search than the submission defaults, so sliders feel responsive.
FAST = dp.PrepConfig(beam_width=300, search_time_s=2.0)
CAL = fake_calibration(1234)  # production calibration generator; no test-suite dependency
DEVICE = cirq_google.Willow105.metadata
print(f"[setup] cirq {cirq.__version__}, widgets: {HAVE_WIDGETS}, simulator: local CPU")
""")

md(r"""
## 0.1 Explicit local simulation

The working examples use Cirq state-vector and density-matrix simulators. No hardware
submission or execution path is included, and there is no unused hardware toggle.
The source of truth is `claude/dicke_prep.py`; both working notebooks import it.
`solution.py` is a thin jupytext mirror, and importing it performs no experiments.
The standalone submission export contains the same tested preparation functions.
""")

# --------------------------------------------------------------------------- #
md(r"""
## 1. What is a Dicke state?

The Dicke state $|D^N_n\rangle$ is the equal superposition of every $N$-bit string with
exactly $n$ ones:

$$
|D^N_n\rangle = \binom{N}{n}^{-1/2} \sum_{|x| = n} |x\rangle .
$$

Examples:

* $|D^3_1\rangle = (|001\rangle + |010\rangle + |100\rangle)/\sqrt{3}$, the **W state**.
* $|D^4_2\rangle = (|0011\rangle + |0101\rangle + |0110\rangle + |1001\rangle + |1010\rangle + |1100\rangle)/\sqrt{6}$.

It is unchanged by any permutation of the qubits, and for $1 \le n \le N-1$ it is entangled.
It is not a product state, so we need two-qubit gates.

🎛️ Move the sliders. Each bar is one basis state, and the colour is its Hamming weight. Only one
weight is present, and all bars have the same height $1/\binom{N}{n}$.
""")
code(r"""
def show_dicke(N, n):
    n = min(n, N)
    fig, ax = plt.subplots(figsize=(9, 2.8))
    plot_probs(ax, dicke_vector(N, n), N,
               title=f"|D^{N}_{n}>: {math.comb(N, n)} terms, each with probability 1/{math.comb(N, n)}")
    save_and_show("tutorial")

interactive(show_dicke, N=(2, 8, 1, 4), n=(0, 8, 1, 2))
""")
md(r"""
✏️ **Exercise 1.** How many basis states appear in $|D^{10}_3\rangle$, and what is each amplitude?

<details><summary>Solution</summary>

$\binom{10}{3} = 120$ terms, each with amplitude $1/\sqrt{120} \approx 0.0913$.
</details>

✏️ **Exercise 2.** Show that applying $X$ to every qubit maps $|D^N_n\rangle$ to $|D^N_{N-n}\rangle$.
Check it numerically in the cell below. (`dp.create_dicke_state` uses this to handle $n > N/2$.)

<details><summary>Solution</summary>

$X^{\otimes N}$ flips every bit, so it maps the strings of weight $n$ one-to-one onto the
strings of weight $N - n$, and the amplitudes stay equal. In the code, flipping all bits of
index $i$ gives index $2^N - 1 - i$, so the vector is reversed:

```python
assert np.allclose(dicke_vector(N, n)[::-1], dicke_vector(N, N - n))
```
</details>
""")
code(r"""
# Exercise 2: your check here
N, n = 6, 2
""")

# --------------------------------------------------------------------------- #
md(r"""
## 2. The recursion that builds it

Look at the last qubit of $|D^m_r\rangle$. In a fraction $r/m$ of the terms it is 1 and the other
$m-1$ qubits hold $r-1$ ones. In the rest it is 0 and the others hold $r$ ones:

$$
|D^m_r\rangle = \sqrt{\tfrac{r}{m}}\; |D^{m-1}_{r-1}\rangle |1\rangle
              + \sqrt{\tfrac{m-r}{m}}\; |D^{m-1}_{r}\rangle |0\rangle .
$$

*Derivation:* there are $\binom{m-1}{r-1}$ strings ending in 1 and $\binom{m-1}{r}$ ending in 0.
Each has amplitude $\binom{m}{r}^{-1/2}$, and $\binom{m-1}{r-1}/\binom{m}{r} = r/m$.

*Limiting cases:* $r = m$ gives $|1\cdots1\rangle$ (only the first term survives), and $r = 0$
gives $|0\cdots0\rangle$ (only the second).

So a circuit can **decide one qubit at a time**: qubit $m$ gets an excitation with probability
$r/m$, and the remaining qubits must then hold a smaller Dicke state. The next cell checks the
identity for every $m \le 8$. With qubit 0 most significant, appending a qubit is
`np.kron(left, ket)`.
""")
code(r"""
ket0, ket1 = np.array([1.0, 0.0]), np.array([0.0, 1.0])
for m in range(2, 9):
    for r in range(0, m + 1):
        rhs = np.zeros(2**m)
        if r >= 1:
            rhs += math.sqrt(r / m) * np.kron(dicke_vector(m - 1, r - 1), ket1)
        if r <= m - 1:
            rhs += math.sqrt((m - r) / m) * np.kron(dicke_vector(m - 1, r), ket0)
        np.testing.assert_allclose(rhs, dicke_vector(m, r), atol=1e-12)
print("[done] recursion verified for all m <= 8")
""")

# --------------------------------------------------------------------------- #
md(r"""
## 3. The building block: a Givens rotation

Everything in this construction **conserves the number of ones**. The natural gate for that is the
Givens rotation, a "partial swap" that leaves $|00\rangle$ and $|11\rangle$ alone:

$$
G(\theta) = \begin{pmatrix} 1&0&0&0\\ 0&\cos\theta&-\sin\theta&0\\ 0&\sin\theta&\cos\theta&0\\ 0&0&0&1 \end{pmatrix},
\qquad |01\rangle \mapsto \cos\theta\,|01\rangle + \sin\theta\,|10\rangle .
$$

$G(\pi/2)$ moves $|01\rangle$ fully to $|10\rangle$, a swap of the excitation. Willow only offers
CZ plus single-qubit gates, so `dp.givens_ops` compiles $G(\theta)$ into **2 CZs**:
""")
code(r"""
a, b = cirq.LineQubit.range(2)
theta = 0.6
print(np.round(cirq.unitary(cirq.givens(theta)), 3))
givens_circuit = cirq.Circuit(dp.givens_ops(a, b, theta))
print(givens_circuit)
assert cirq.equal_up_to_global_phase(cirq.unitary(givens_circuit), cirq.unitary(cirq.givens(theta)), atol=1e-10)
""")
md(r"""
🎛️ Starting from $|01\rangle$, the slider moves weight to $|10\rangle$ as $\sin^2\theta$.
""")
code(r"""
def show_givens(theta):
    psi = cirq.final_state_vector(cirq.Circuit(cirq.X(b), dp.givens_ops(a, b, theta)),
                                  qubit_order=[a, b], dtype=np.complex128)
    fig, ax = plt.subplots(figsize=(4, 2.5))
    plot_probs(ax, psi, 2, title=f"cos^2 = {math.cos(theta)**2:.3f}, sin^2 = {math.sin(theta)**2:.3f}")
    save_and_show("tutorial")

interactive(show_givens, theta=(0.0, math.pi / 2, 0.01, 0.6))
""")
md(r"""
✏️ **Exercise 3.** In the W state on 3 qubits, the first gate must send probability $2/3$ away from the
starting qubit. Which $\theta$ gives $P(|10\rangle) = 2/3$ from $|01\rangle$? Check it with the slider.

<details><summary>Solution</summary>

$\sin^2\theta = 2/3$, so $\theta = \arcsin\sqrt{2/3} \approx 0.955$.
</details>
""")

# --------------------------------------------------------------------------- #
md(r"""
## 4. Split and cyclic shift: watching the hole move

This is the nearest-neighbour version of Bärtschi & Eidenbenz,
*Deterministic Preparation of Dicke States* ([arXiv:1904.07358](https://arxiv.org/abs/1904.07358)).

Start from $|0^{N-n}1^n\rangle$ on a line and use the recursion from §2 on positions
$m-1, m-2, \dots$ (right to left). Before step $m$, positions $0..m-1$ hold $|0^{m-r}1^r\rangle$.
Call the rightmost 0 the **hole**.

* With probability $r/m$, position $m-1$ should end up 1. It already is, so in that branch nothing moves.
* With probability $(m-r)/m$ it should end up 0. Then the hole travels right through the block of
  ones to position $m-1$, and the ones end up shifted left by one (a *cyclic shift* of the window).

The hole moves by a chain of gates on neighbouring pairs $(p, p+1)$:

* **First encounter** (the hole sits at $p$): $G(\theta_r)$ with $\cos\theta_r = \sqrt{r/m}$
  splits the branch. The "stay" part keeps its hole; the "move" part now has its hole at $p+1$.
* **Hole already moving:** $G(\pi/2)$, a full swap, carries it one more step.

In superposition, different branches have their hole in different places, so a pair may need to do
*either* depending on the branch. Section 5 solves that. First, watch it work.

🎛️ `step` walks through the gates of `dp.line_gates(N, n)`. Top: the basis states present (the
weight never changes). Bottom: the line, with the active qubits boxed.
This view deliberately follows the original logical gates; the production constructor
can merge adjacent native blocks without changing these final amplitudes (see §6).
""")
code(r"""
def line_program(N, n):
    # Original logical gates for stepping; production synthesis can merge pairs.
    q = cirq.LineQubit.range(N)
    steps = [(f"prepare |0^{N-n} 1^{n}>", [cirq.X(x) for x in q[N - n:]], list(range(N - n, N)))]
    gates = dp.line_gates(N, n)
    for i, g in enumerate(gates):
        new_block = i == 0 or g.p <= gates[i - 1].p
        if g.kind == "givens":
            ops, active = dp.givens_ops(q[g.p], q[g.p + 1], g.theta), [g.p, g.p + 1]
            what = "swap G(pi/2)" if math.isclose(g.theta, math.pi / 2) else f"split G({g.theta:.3f})"
        else:
            ops, active = dp.mux_ops(q[g.p - 1], q[g.p], q[g.p + 1], g.theta), [g.p - 1, g.p, g.p + 1]
            what = f"MUX(theta={g.theta:.3f}), flag = qubit {g.p - 1}"
        steps.append((("new step | " if new_block else "") + f"{what} on ({g.p}, {g.p + 1})", ops, active))
    return q, steps


def trace_states(N, n):
    q, steps = line_program(N, n)
    psi = np.zeros(2**N, dtype=np.complex128)
    psi[0] = 1.0
    out = []
    for label, ops, active in steps:
        psi = cirq.final_state_vector(cirq.Circuit(ops), initial_state=psi, qubit_order=q,
                                      dtype=np.complex128)
        out.append((label, psi, active))
    return out


def show_trace(N, n, step):
    n = max(1, min(n, N - 1))
    trace = trace_states(N, n)
    step = min(step, len(trace) - 1)
    label, psi, active = trace[step]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 4.6), gridspec_kw={"height_ratios": [3, 1]})
    fid = abs(np.vdot(dicke_vector(N, n), psi)) ** 2
    plot_probs(ax1, psi, N, only_nonzero=True,
               title=f"step {step}/{len(trace) - 1}: {label}   (fidelity with D: {fid:.3f})")
    plot_line_occupation(ax2, psi, N, active)
    plt.tight_layout()
    save_and_show("tutorial")

TRACE_MAX_QUBITS = 7
TRACE_MAX_STEP = max(len(dp.line_gates(TRACE_MAX_QUBITS, k)) for k in range(1, TRACE_MAX_QUBITS))
interactive(show_trace, N=(2, TRACE_MAX_QUBITS, 1, 4), n=(1, 6, 1, 2), step=(0, TRACE_MAX_STEP, 1, 0))
""")
md(r"""
Things to notice for $N = 4,\ n = 2$:

* Every intermediate state has weight 2. The Givens gates never create or destroy ones.
* After the gates of the first step, position 3 is 1 with probability exactly $2/4$.
  Later gates never touch it again.
* The last step reaches fidelity 1.

✏️ **Exercise 4.** For $|D^5_1\rangle$, how many gates does `dp.line_gates(5, 1)` produce, and of what
kind? Predict first, then check with `dp.line_gates(5, 1)`.

<details><summary>Solution</summary>

4 plain Givens gates: one split per step $m = 5, 4, 3, 2$. With a single one there is never a block
of ones for the hole to cross, so it never needs to keep moving and no MUX is needed. That makes
$2(N-1) = 8$ CZs, but in a chain each gate waits for the previous one, so the depth also grows like
$N$. Section 7 fixes the depth.
</details>
""")
code(r"""
# Exercise 4: check your prediction
""")

# --------------------------------------------------------------------------- #
md(r"""
## 5. The 5-CZ multiplexed gate

Pair $(p, p+1)$ must apply $G(\theta)$ in branches where the hole meets it for the first time, and
$G(\pi/2)$ where the hole is already moving. Its **left neighbour $c = p-1$ tells which**: it is 0
if the hole has not passed yet, and 1 if the hole came from there. So we need a controlled choice
of rotation:

$$
\mathrm{MUX}(\theta) = Z_c \cdot G_{p,p+1}(\beta) \cdot \mathrm{CZ}_{c,p} \cdot G_{p,p+1}(\alpha),
\qquad \alpha = \tfrac{\theta + \pi/2}{2},\ \beta = \tfrac{\theta - \pi/2}{2}.
$$

*Derivation.*

* $c = 0$: CZ does nothing, and $G(\beta)G(\alpha) = G(\alpha+\beta) = G(\theta)$. ✓
* $c = 1$: on span$\{|01\rangle,|10\rangle\}$ the CZ acts as $-\sigma_z$ (the phase lands on $|10\rangle$,
  whose qubit $p$ is 1; the minus sign comes from $Z_c$). Since $\sigma_z G(\beta) \sigma_z = G(-\beta)$,
  we get $-G(\beta)\sigma_z G(\alpha) = -\sigma_z G(\alpha - \beta) = -\sigma_z G(\pi/2)$, which maps
  $|01\rangle \to |10\rangle$ (a swap of the excitation, up to sign).
* On $|111\rangle$ the CZ and $Z_c$ each give $-1$, so the net phase is $+1$. ✓

Cost: $2 + 1 + 2 = 5$ CZs. A numerical search found no 4-CZ version.

**The catch:** this is only right on inputs $(c, p, p+1)$ that can actually occur:
$\{000, 001, 011, 111, 101\}$. The table checks all 8, up to one global phase.
""")
code(r"""
def mux_table(theta):
    c, p, p1 = cirq.LineQubit.range(3)
    U = cirq.Circuit(dp.mux_ops(c, p, p1, theta)).unitary(qubit_order=[c, p, p1])
    want = np.zeros((8, 8), dtype=np.complex128)
    want[:4, :4] = cirq.unitary(cirq.givens(theta))     # c = 0 block
    want[4:, 4:] = cirq.unitary(cirq.givens(math.pi / 2))  # c = 1 block
    phase = want[0, 0] / U[0, 0]  # fix the global phase on |000>
    reachable = {"000", "001", "011", "111", "101"}
    print(f"theta = {theta:.3f}\n input  reachable  output correct?")
    for j in range(8):
        ok = np.allclose(phase * U[:, j], want[:, j], atol=1e-9)
        print(f"  {bits(j, 3)}     {'yes' if bits(j, 3) in reachable else ' no'}        {'yes' if ok else 'NO (don’t care)'}")

interactive(mux_table, theta=(0.0, math.pi / 2, 0.01, 0.9))
""")
md(r"""
✏️ **Exercise 5.** Why can $(c, p, p+1) = 010,\ 100,\ 110$ never occur at the moment the gate on
$(p, p+1)$ acts?

<details><summary>Solution</summary>

Gates in one step act left to right, so when pair $(p, p+1)$ acts, position $p+1$ is still untouched.
It is 0 only if it lies at or left of the hole's starting point, and *everything* there is still 0.
So the only reachable input with $p+1 = 0$ is $000$. All three listed inputs have $p+1 = 0$ with a 1
somewhere to its left.
</details>
""")

# --------------------------------------------------------------------------- #
md(r"""
## 6. Counting CZs, and pruning

A MUX costs 5 CZs, a Givens 2. Many pairs can only ever see one case. Bounding the number of ones
still to be placed, $r \in [\max(0, n-(N-m)),\ \min(n, m)]$, lets `dp.line_gates` use plain
Givens gates there. The first known-input split saves one CZ. Additionally, the optimized
constructor merges the first adjacent Givens/MUX pair of a stage with $m>n$: four CZs
replace seven on the reachable local inputs $000,001,011$, with the same positive phase.
The remaining pruned gates stay unchanged. This uses exact angle formulas and no fitted tables.
The table compares the original and optimized **line** counts. For $D(4,2)$ the full physical
constructor can instead choose a calibrated five-CZ square when its cost estimate is better.
""")
code(r"""
print(f"{'N':>3} {'n':>3} {'givens':>7} {'mux':>4} {'line old CZ':>12} {'line opt CZ':>12} {'saved':>6}")
for N in (4, 6, 8, 10, 12):
    for n in range(1, N // 2 + 1):
        g = dp.line_gates(N, n)
        n_giv = sum(x.kind == "givens" for x in g)
        n_mux = len(g) - n_giv
        ops = dp.build_line_ops(cirq.LineQubit.range(N), n)
        old_count = 2 * n_giv + 5 * n_mux - 1
        new_count = sum(len(op.qubits) == 2 for op in ops)
        assert sum(dp.line_edge_cz_counts(N, n)) == new_count
        assert sum(len(op.qubits) == 2 for op in dp.build_line_ops(cirq.LineQubit.range(N), n, construction="analytic")) == old_count
        assert new_count <= old_count
        print(f"{N:>3} {n:>3} {n_giv:>7} {n_mux:>4} {old_count:>12} {new_count:>12} {old_count-new_count:>6}")
""")
md(r"""
🎛️ CZs are not spread evenly along the line. `dp.line_edge_cz_counts` gives the load on each edge.
The layout search (§8) uses it to put the busiest edges on the best couplers.
""")
code(r"""
def show_edge_load(N, n):
    n = max(1, min(n, N - 1))
    counts = dp.line_edge_cz_counts(N, n)
    fig, ax = plt.subplots(figsize=(8, 2.5))
    ax.bar([f"{i}-{i+1}" for i in range(N - 1)], counts, color="C2")
    ax.set_ylabel("CZs on edge")
    ax.set_title(f"D^{N}_{n}: {sum(counts)} CZs in total")
    save_and_show("tutorial")

interactive(show_edge_load, N=(3, 16, 1, 10), n=(1, 8, 1, 3))
""")

# --------------------------------------------------------------------------- #
md(r"""
## 7. The W state ($n = 1$) on a tree

On a line, the single excitation walks qubit by qubit, so the depth grows like $N$. Instead,
`dp.build_tree_ops` uses a **spanning tree**. The root starts in $|1\rangle$. A node holding the
excitation with `remaining` qubits left in its subtree hands each child subtree $S_c$ its share with one
Givens rotation:

$$
\sin^2\theta_c = \frac{|S_c|}{\text{remaining}}, \qquad \text{remaining} \leftarrow \text{remaining} - |S_c| .
$$

Different branches then work in parallel, so the depth is about the tree height times the branching factor.
The first split has a known product input and uses one CZ; later splits use two-CZ Givens gates. A hand-made tree first:
""")
code(r"""
q = cirq.LineQubit.range(6)
children = {q[0]: [q[1], q[2]], q[1]: [q[3], q[4]], q[2]: [q[5]], q[3]: [], q[4]: [], q[5]: []}
ops = dp.build_tree_ops(q[0], children)
psi = cirq.final_state_vector(cirq.Circuit(ops), qubit_order=q, dtype=np.complex128)
print("fidelity with W_6:", round(abs(np.vdot(dicke_vector(6, 1), psi)) ** 2, 12))
print(cirq.Circuit(ops))
""")
md(
    "🎛️ Line vs. tree on the fake Willow calibration: number of CZ layers (time steps) for the W state."
)
code(r"""
def cz_layers(ops):
    return sum(any(len(op.qubits) == 2 for op in m) for m in dp.schedule(ops, dynamical_decoupling=False))


def compare_line_tree(N_max):
    hw = dp.Hardware(*CAL, config=FAST)
    Ns, line_d, tree_d = list(range(3, N_max + 1)), [], []
    for N in Ns:
        line = dp.find_line(hw, dp.line_edge_cz_counts(N, 1), deadline=0)
        line_d.append(cz_layers(dp.build_line_ops(line, 1)))
        root, kids = dp.find_tree(hw, N, deadline=0)
        tree_d.append(cz_layers(dp.build_tree_ops(root, kids)))
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(Ns, line_d, "o-", label="line")
    ax.plot(Ns, tree_d, "s-", label="tree")
    ax.set_xlabel("N")
    ax.set_ylabel("CZ layers")
    ax.legend()
    ax.set_title("W depth: line 2N−3 CZs; optimized tree 2N−3 CZs")
    save_and_show("tutorial")

interactive(compare_line_tree, N_max=(6, 24, 2, 16))
""")
md(r"""
✏️ **Exercise 6.** In the hand-made tree above, what angle does the root use for its first child
($q_1$, subtree size 3)? What about its second child?

<details><summary>Solution</summary>

The root starts with remaining $= 6$. First child: $\theta = \arcsin\sqrt{3/6} = \pi/4$. Then
remaining $= 3$, and the second child (size 2) gets $\arcsin\sqrt{2/3} \approx 0.955$. The root keeps
the last $1/6$ of the probability for itself.
</details>
""")

# --------------------------------------------------------------------------- #
md(r"""
## 8. Choosing qubits on the noisy chip

Willow's qubits and couplers do not all have the same error rates, and a few are dead. `dp.find_line`
runs a **beam search** over simple paths that minimises

$$
\sum_{\text{edges } i} w_i\, \varepsilon^{\mathrm{CZ}}_i \;+\; \sum_{\text{qubits}} \big(\varepsilon^{\mathrm{readout}} + 2\,\varepsilon^{1q}\big),
$$

where $w_i$ is the edge load from §6. The beam search keeps the best `beam_width` partial paths at each length.
For the W state, `dp.find_tree` grows a breadth-first tree from each candidate root instead.
For $D(4,2)$, the production constructor also evaluates calibrated square layouts and their
five-CZ load. The figure below shows the actual returned circuit's couplers.

🎛️ Couplers are coloured by CZ error (dotted ones are dead), qubits by readout + single-qubit cost
(× marks a dead qubit). The chosen layout is red. Change `seed` to get a different fake chip.
""")
code(r"""
def choose_layout(N, n, cal):
    circuit, qubits = dp.create_dicke_state(N, n, *cal, config=FAST)
    pairs = {tuple(sorted(op.qubits)) for op in circuit.all_operations() if op.gate == cirq.CZ}
    return sorted(qubits), sorted(pairs)


def show_layout(N, n, seed):
    n = min(n, N)
    cal = CAL if seed == 1234 else fake_calibration(seed)
    qs, edges = choose_layout(N, n, cal)
    fig, ax = plt.subplots(figsize=(7, 7))
    draw_willow(ax, cal, DEVICE.qubit_set, DEVICE.qubit_pairs, edges, qs)
    ax.set_title(f"D^{N}_{n}: {len(edges)} used couplers on {len(qs)} qubits")
    save_and_show("tutorial")

interactive(show_layout, N=(2, 20, 1, 8), n=(1, 10, 1, 2), seed=(1, 2000, 1, 1234))
""")
md(r"""
✏️ **Exercise 7.** How much does the beam search gain over a greedy search (`beam_width=1`)? Compute
the cost above for $D^{10}_3$ with beam widths 1, 10, 100 and 1000.

<details><summary>Solution</summary>

```python
def path_cost(hw, path, w):
    return (sum(wi * hw.edge(a, b) for wi, a, b in zip(w, path, path[1:]))
            + sum(hw.node[q] for q in path))

w = dp.line_edge_cz_counts(10, 3)
for bw in (1, 10, 100, 1000):
    hw = dp.Hardware(*CAL, config=dp.PrepConfig(beam_width=bw))
    print(bw, round(path_cost(hw, dp.find_line(hw, w, deadline=1e18), w), 4))
```
The greedy path is usually clearly worse. The gain then levels off after a few hundred.
</details>
""")
code(r"""
# Exercise 7: your code here
""")

# --------------------------------------------------------------------------- #
md(r"""
## 9. Scheduling and dynamical decoupling

`dp.schedule` turns the op list into hardware-style moments:

* **Alternating layers:** one moment of single-qubit gates, then one of CZs, and so on. Consecutive
  single-qubit gates on a qubit are merged into a single `PhasedXZGate`.
* **As late as possible (ALAP):** every CZ is pushed as late as it can go, so qubits rest in $|0\rangle$
  (which does not dephase) for as long as possible.
* **Dynamical decoupling (DD):** an idle qubit in superposition picks up phase from slow frequency
  drift. Idle single-qubit slots are filled with X/Y pulses that echo it away. The pulses' net product is
  folded into the next gate, so the ideal state is unchanged, as the check below confirms.

🎛️ Compare the two circuits.
""")
code(r"""
def show_schedule(N, n, dd):
    n = max(1, min(n, N - 1))
    q = cirq.LineQubit.range(N)
    circuit = dp.schedule([cirq.I(x) for x in q] + dp.build_line_ops(q, n), dynamical_decoupling=dd == "on")
    psi = cirq.final_state_vector(circuit, qubit_order=q, dtype=np.complex128)
    n_1q = sum(len(op.qubits) == 1 for op in circuit.all_operations())
    print(f"DD {dd}: {len(circuit)} moments, {n_1q} single-qubit gates, "
          f"fidelity {abs(np.vdot(dicke_vector(N, n), psi)) ** 2:.12f}")
    print(circuit.to_text_diagram(use_unicode_characters=True, precision=2))

interactive(show_schedule, N=(3, 6, 1, 4), n=(1, 3, 1, 2), dd=["off", "on"])
""")

# --------------------------------------------------------------------------- #
md(r"""
## 10. How the challenge scores a circuit, and what noise does

The judges run the circuit on hardware and measure in two bases:

* **Z basis:** the outcomes should be uniform over the $\binom{N}{n}$ strings of weight $n$. The
  score is a $\chi^2$ distance, divided by the fraction of shots that land in the right weight.
* **X basis:** the parity correlators $\langle X_{i_1}\cdots X_{i_k}\rangle$ averaged over all qubit
  subsets, up to size 4, are compared with their ideal values. This checks the *phases*, which Z
  measurements cannot see.

`overall_score` $= 1/(\text{Z error} + \text{X error})$, so higher is better, and finite shot noise
alone caps it. The cells below reuse the exact official functions and the noise model from
`claude/scripts/noisy_benchmark.py`: CZ and single-qubit depolarizing, $T_1$/$T_\phi$ damping, quasi-static
detuning, and readout flips.

🎛️ Press **Run** (density-matrix simulation takes a few seconds). The printed scores use 4000
sampled shots. `shot_seed` controls sampling; `noise_seed` selects an independent physical
detuning ensemble. The plot uses the same DD-on ensemble, including detuning and readout, as its score. It shows the Hamming weights of the Z-basis outcomes. Anything outside the target
weight is **leakage**, which the Z score penalises.
""")
code(r"""
from claude.scripts import noisy_benchmark as nbm

overall_score = nbm.load_scoring()  # read-only exec of the challenge notebook's scoring cell


def noisy_demo(N, n, detuning_khz, cz_error_scale, shot_seed, noise_seed=7):
    n = min(n, N)
    cal = ({p: (e * cz_error_scale, u) for p, (e, u) in CAL[0].items()}, *CAL[1:])
    noise = nbm.NoiseConfig(detuning_khz=detuning_khz, shots=4000, seed=shot_seed, noise_seed=noise_seed)
    clean_cal = tuple({key: (0.0, 0) for key in m} for m in CAL)
    rows = []
    for name, c, nz, cfg in [
        ("noiseless (shot noise only)", clean_cal,
         nbm.NoiseConfig(t1_us=1e12, tphi_us=1e12, shots=4000, seed=shot_seed, noise_seed=noise_seed), FAST),
        ("noisy, DD on", cal, noise, FAST),
        ("noisy, DD off", cal, noise, dp.PrepConfig(beam_width=300, search_time_s=2.0, use_dynamical_decoupling=False)),
    ]:
        prepared = dp.create_dicke_state(N, n, *c, config=cfg)
        probabilities = nbm.simulate_probabilities(prepared[0], sorted(prepared[1]), c, nz)
        s, moments = nbm.score_instance(N, n, c, nz, overall_score, cfg,
                                       prepared=prepared, probabilities=probabilities)
        rows.append((name, s, moments))
        if name == "noisy, DD on":
            pz = probabilities[0]
    for name, s, mom in rows:
        print(f"{name:<30} score {s:8.2f}   ({mom} moments)")

    weight = np.array([bits(i, N).count("1") for i in range(2**N)])
    fig, ax = plt.subplots(figsize=(5, 2.6))
    ax.bar(range(N + 1), [pz[weight == w].sum() for w in range(N + 1)],
           color=["C3" if w == n else "C7" for w in range(N + 1)])
    ax.set_xlabel("Hamming weight of Z outcome")
    ax.set_ylabel("probability")
    ax.set_title(f"leakage out of weight {n}: {1 - pz[weight == n].sum():.3f}")
    save_and_show("tutorial")

interactive(noisy_demo, manual=True, N=(2, 6, 1, 4), n=(1, 3, 1, 2),
            detuning_khz=(0.0, 50.0, 5.0, 20.0), cz_error_scale=(0.0, 5.0, 0.5, 1.0),
            shot_seed=(0, 20, 1, 7), noise_seed=(0, 20, 1, 7))
""")
md(r"""
✏️ **Exercise 8.** At $N = 6$, $n = 3$:

1. Keep every noise setting fixed and change only `shot_seed`. How much does the score move?
   Can you trust the difference between "DD on" and "DD off" from a single run?
2. Using the **leakage** number instead, set `cz_error_scale` to 0, 1 and 3, then try `detuning_khz` 0 and 50.
   Which noise sources cause the leakage?

<details><summary>Solution</summary>

1. Changing only `shot_seed` now holds the physical noise ensemble fixed. Scores
   still fluctuate because they are reciprocal statistics of finite samples. Compare
   paired seeds and report their spread; one sample does not establish a DD advantage.
2. The plotted leakage is exact for the finite ensemble, so it has no shot noise, but
   changing `noise_seed` can change that ensemble. Readout flips, T1, and Pauli errors
   cause leakage. Detuning can also cause leakage: the native single-qubit gates inside
   a compiled Givens rotation need not conserve excitation number, so a Z error between
   them can turn into a population error. The ideal complete Givens gate conserves weight;
   that does not imply its noisy decomposition does. The plot includes the selected detuning.
   DD adds imperfect pulses and can help or hurt, depending on the physical noise model.

Compare the same case and physical ensemble before drawing conclusions about a pulse policy.
</details>
""")

# --------------------------------------------------------------------------- #
md(r"""
## 11. What the implementation checks before submission

The construction is deliberately testable without hardware. For a generated circuit we check:

* every operation is either a CZ on a calibrated Willow coupler or a `PhasedXZGate` on a calibrated qubit;
* the circuit has no more than 1750 moments;
* a noiseless simulator has unit overlap with the target Dicke state, up to global phase;
* DD pulse products are identity, with any residual pulse folded into the next logical gate;
* layout search uses the measured error maps, while the simulation benchmark uses explicit noise and readout models.

The adaptive entry point currently uses the same exact deterministic preparation as a legal fallback.
It is benchmarked separately because the bonus rewards depth, not merely state correctness; a genuinely
measurement-and-feed-forward construction must first match the evaluator's allowed adaptive API.

The organizer's email confirms bonus grading for $2 \le N \le 15$ and fixes the original
validator to use `range(len(qubits))`. The original notebook remains unchanged. Grading
$(N,n)$ cases and `max_correlator_size` remain undisclosed; the local cutoff of four is a
simulation setting. Exact amplitudes and relative phases are validated independently of it.
""")
code(r"""
def validate_simulated_solution(N, n):
    n = max(0, min(n, N))
    circuit, qubits = dp.create_dicke_state(N, n, *CAL, config=FAST)
    order = sorted(qubits)
    psi = cirq.final_state_vector(circuit, qubit_order=order, dtype=np.complex128)
    fidelity = abs(np.vdot(dicke_vector(N, n), psi)) ** 2
    assert len(circuit) <= 1750
    assert fidelity > 1 - 1e-10
    assert all(op.gate == cirq.CZ or isinstance(op.gate, cirq.PhasedXZGate)
               for op in circuit.all_operations())
    print(f"[done] D^{N}_{n}: {len(circuit)} moments, fidelity {fidelity:.12f}")


interactive(validate_simulated_solution, N=(2, 12, 1, 6), n=(0, 6, 1, 2))
""")

# --------------------------------------------------------------------------- #
md(r"""
## 11.1 Diagnostic bundle: inspect the physics, circuit and experiment separately

The following cell saves a report with PNG/PDF figures and JSON/CSV metrics. It includes
phase-sensitive exact-state checks, observed weight distributions and X correlations,
physical layout and native schedules, resource scaling, and detuning sensitivity.
When a current raw score run is available, it adds paired differences and seed convergence.

The example is a fixed small physical-noise ensemble; its exact probabilities have no shot
noise. Approximate t intervals describe matched seed replicates in the separate score dataset.
The report records those assumptions. To generate fresh paired data explicitly, run
`python -m claude.scripts.diagnose --benchmark` from the repository root.
All saved figures go under `figs/`; reports and machine-readable tables remain under
`benchmark_outputs/`. The notebook uses each report's recorded figure directory.
""")
code(r"""
import json
import os

from IPython.display import Image, Markdown, display

from claude.scripts.analyze_benchmark_results import latest_results
from claude.scripts.diagnose import DEFAULT_OUTPUT, build_report

try:
    current_results = latest_results()
except FileNotFoundError:
    current_results = None
report_path = build_report(
    Path(os.environ.get("DUQUANTUM_DIAGNOSTICS_DIR", str(DEFAULT_OUTPUT))),
    results_path=current_results, resource_sizes=(4, 8, 16, 30, 60),
)
report_data = json.loads((report_path.parent / "diagnostics.json").read_text())
display(Markdown(report_path.read_text().split("## Figures")[0]))
for figure_name in report_data["figures"]:
    display(Image(filename=str(Path(report_data["figure_dir"]) / (figure_name + ".png")), width=950))
""")

md(r"""
## 12. Recap and where to go next

| Idea | Where in the solution cell |
| --- | --- |
| Recursion: decide one qubit at a time | §2 of this tutorial |
| Givens rotation, 2 CZs | `givens_ops` |
| Hole moving along the line, nearest-neighbour only | `line_gates`, `build_line_ops` |
| 5-CZ multiplexed gate, exact on reachable inputs | `mux_ops` |
| Range bounds to prune MUX gates | `line_gates` (`r_min`, `r_max`) |
| W state on a tree | `find_tree`, `build_tree_ops` |
| $n > N/2$ via $X^{\otimes N}$ | `create_dicke_state` (`flip`) |
| Error-weighted layout | `Hardware`, `find_line` |
| ALAP schedule + DD | `schedule`, `_add_dd` |

**Open directions** (from `claude/docs/PLAN_STATUS.md`):

* **Bonus, adaptive circuits:** mid-circuit measurement and feed-forward could cut the depth to
  roughly constant. The current bonus entry reuses the non-adaptive circuit.
* **Fewer CZs for $n \ge 2$:** a tree or divide-and-conquer Dicke construction, in the spirit of §7.

**Reference:** A. Bärtschi and S. Eidenbenz, *Deterministic Preparation of Dicke States*, FCT 2019,
[arXiv:1904.07358](https://arxiv.org/abs/1904.07358).
""")


def main() -> None:
    nb = nbformat.v4.new_notebook()
    nb.cells = [
        nbformat.v4.new_markdown_cell(s) if kind == "md" else nbformat.v4.new_code_cell(s)
        for kind, s in CELLS
    ]
    nb.metadata["kernelspec"] = {
        "name": "duquantum",
        "display_name": "duquantum",
        "language": "python",
    }
    OUT_PATH.parent.mkdir(exist_ok=True)
    nbformat.write(nb, OUT_PATH)
    print(f"[done] wrote {OUT_PATH.relative_to(ROOT)} ({len(nb.cells)} cells)")


if __name__ == "__main__":
    main()
