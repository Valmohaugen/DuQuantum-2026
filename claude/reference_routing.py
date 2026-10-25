"""Local compatibility guard for the pinned Cirq router used by a reference solver.

Cirq 1.8.0.dev20261023221525's RouteCQC can pass an empty list of disjoint
swap pairs to _choose_optimal_swap, which indexes sigma[0]. A star graph is
a concrete example: every edge shares the center. Returning None for that
empty candidate set lets RouteCQC use its existing fallback routing strategy.

Only the reference function's private globals receive the guarded router.
The installed Cirq module and verbatim reference source are never modified.
No logical gates, graph-selection rules or compilation passes are replaced.

References
----------
https://quantumai.google/reference/python/cirq/RouteCQC
Installed source: cirq/transformers/routing/route_circuit_cqc.py,
_choose_pair_of_swaps, _choose_optimal_swap and _route. This private override
is covered by an actual five-qubit-star regression against the pinned version.
"""

from __future__ import annotations

from functools import update_wrapper
from types import FunctionType, ModuleType
from typing import TYPE_CHECKING, Sequence

import cirq

if TYPE_CHECKING:
    from cirq.transformers.routing.mapping_manager import MappingManager

QubitPair = tuple[int, int]


class _EmptyCandidateSafeRouter(cirq.RouteCQC):
    """Use the existing fallback when no candidate swap tuple exists."""

    @classmethod
    def _choose_optimal_swap(
        cls,
        mm: MappingManager,
        two_qubit_ops_ints: Sequence[Sequence[QubitPair]],
        timestep: int,
        lookahead_radius: int,
        sigma: Sequence[tuple[QubitPair, ...]],
    ) -> tuple[QubitPair, ...] | None:
        if not sigma:
            return None
        return super()._choose_optimal_swap(
            mm, two_qubit_ops_ints, timestep, lookahead_radius, sigma
        )


def with_safe_reference_routing(function: FunctionType) -> FunctionType:
    """Return the reference function with a private, guarded Cirq namespace.

    Parameters
    ----------
    function : types.FunctionType
        Reference constructor importing the project's Cirq module as ``cirq``.
        Its bytecode, defaults, closure and other globals are retained unchanged.

    Returns
    -------
    types.FunctionType
        The same constructor body with a copied globals dictionary. Its local
        Cirq namespace differs only in RouteCQC's empty-candidate guard. The
        original reference function and process-wide Cirq state remain untouched.

    Raises
    ------
    ValueError
        If the reference does not use the expected Cirq module global. Routing,
        construction and validation errors otherwise propagate normally.
    """
    if function.__globals__.get("cirq") is not cirq:
        raise ValueError("reference constructor must use the project Cirq module as cirq")
    namespace = ModuleType(cirq.__name__)
    namespace.__dict__.update(vars(cirq))
    namespace.RouteCQC = _EmptyCandidateSafeRouter
    adapted = FunctionType(
        function.__code__,
        {**function.__globals__, "cirq": namespace},
        name=function.__name__,
        argdefs=function.__defaults__,
        closure=function.__closure__,
    )
    adapted.__kwdefaults__ = function.__kwdefaults__
    return update_wrapper(adapted, function)
