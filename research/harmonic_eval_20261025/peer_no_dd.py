"""Ablation of the current peer solver; keep its layouts, weights and tables."""

from ryon.toby_sol import create_dicke_state as prepare
from ryon.toby_sol import create_dicke_state_adaptive

__all__ = ["create_dicke_state", "create_dicke_state_adaptive"]


def create_dicke_state(*args):
    return prepare(*args, dynamical_decoupling=False)
