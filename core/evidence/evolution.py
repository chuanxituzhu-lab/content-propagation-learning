"""Reserved evolution transitions; MVP execution stops at CANDIDATE."""

from __future__ import annotations

from core.contracts.models import PatternLifecycle


class InvalidEvolutionTransition(ValueError):
    pass


EVOLUTION_TRANSITIONS: dict[PatternLifecycle, set[PatternLifecycle]] = {
    PatternLifecycle.HYPOTHESIS: {PatternLifecycle.OBSERVED, PatternLifecycle.REJECTED},
    PatternLifecycle.OBSERVED: {PatternLifecycle.CANDIDATE, PatternLifecycle.REJECTED},
    PatternLifecycle.CANDIDATE: {PatternLifecycle.TESTED, PatternLifecycle.REJECTED, PatternLifecycle.SUPERSEDED},
    PatternLifecycle.TESTED: {PatternLifecycle.VALIDATED, PatternLifecycle.REJECTED, PatternLifecycle.SUPERSEDED},
    PatternLifecycle.VALIDATED: {PatternLifecycle.CANARY, PatternLifecycle.DEPRECATED, PatternLifecycle.SUPERSEDED},
    PatternLifecycle.CANARY: {PatternLifecycle.PROMOTED, PatternLifecycle.DEPRECATED, PatternLifecycle.SUPERSEDED},
    PatternLifecycle.PROMOTED: {PatternLifecycle.DEPRECATED, PatternLifecycle.SUPERSEDED},
    PatternLifecycle.DEPRECATED: set(),
    PatternLifecycle.REJECTED: set(),
    PatternLifecycle.SUPERSEDED: set(),
}


def can_transition(current: PatternLifecycle, target: PatternLifecycle) -> bool:
    return target in EVOLUTION_TRANSITIONS[current]


def require_transition(current: PatternLifecycle, target: PatternLifecycle) -> None:
    if not can_transition(current, target):
        raise InvalidEvolutionTransition(f"{current} -> {target} is not allowed")

