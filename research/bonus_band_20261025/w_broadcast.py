"""Exact native alternatives for a single-excitation broadcast tree.

Children is a defaultdict(list). kinds chooses a decomposition for every edge
after the first. Both choices agree on the reachable zero/one-excitation subspace.
"""

import math
import cirq

def givens(a, b, theta):
    return [cirq.H(a), cirq.H(b), cirq.CZ(a, b), cirq.ry(-theta).on(a), cirq.ry(theta).on(b), cirq.CZ(a, b), cirq.H(a), cirq.H(b)]

def broadcast_order(root, children):
    size, btime = ({}, {})

    def visit(v):
        for c in children[v]:
            visit(c)
        size[v] = 1 + sum((size[c] for c in children[v]))
        children[v].sort(key=lambda c: -btime[c])
        btime[v] = max((i + 1 + btime[c] for i, c in enumerate(children[v])), default=0)
    visit(root)
    return (children, btime[root], size)

def operations(root, children, kinds):
    children, _, size = broadcast_order(root, children)
    start = {root: 0}
    events = []
    stack = [root]
    while stack:
        p = stack.pop()
        for i, c in enumerate(children[p]):
            events.append((start[p] + i, p, c))
            start[c] = start[p] + i + 1
            stack.append(c)
    events.sort()
    remaining = dict(size)
    ops = []
    for i, (rnd, p, c) in enumerate(events):
        t = 2 * math.asin(math.sqrt(size[c] / remaining[p]))
        remaining[p] -= size[c]
        if i == 0:
            ops += [cirq.ry(t).on(c), cirq.X(p), cirq.H(p), cirq.CZ(c, p), cirq.H(p)]
        elif kinds[i - 1]:
            ops += givens(c, p, t / 2)
        else:
            ops += [cirq.ry(-t / 2).on(c), cirq.CZ(p, c), cirq.ry(t / 2).on(c), cirq.H(p), cirq.CZ(c, p), cirq.H(p)]
    return ops
