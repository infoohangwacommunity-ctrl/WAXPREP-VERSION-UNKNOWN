"""Explicit lifecycle state model and transition contract (Stage 16).

There is exactly one authoritative state per application instance. Booleans such
as ``shutting_down`` no longer decide readiness or cleanup; they may be derived
for compatibility, but the state machine is the source of truth.

Allowed transitions::

    NEW ──► STARTING ──► READY ──► DRAINING ──► STOPPING ──► STOPPED
              │                                    ▲
              └────────────► STOPPING ─────────────┘
                                 │
                                 └──► FAILED◄──► STARTING (explicit retry)

``STOPPED`` and ``FAILED`` are terminal for a single lifecycle execution but may
be used to start a new execution on the same application instance. Every other
transition is rejected.
"""

from __future__ import annotations

from enum import StrEnum


class LifecycleState(StrEnum):
    """One authoritative application lifecycle state."""

    NEW = "new"
    STARTING = "starting"
    READY = "ready"
    DRAINING = "draining"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


ALLOWED_TRANSITIONS: dict[LifecycleState, frozenset[LifecycleState]] = {
    LifecycleState.NEW: frozenset({LifecycleState.STARTING, LifecycleState.STOPPING}),
    LifecycleState.STARTING: frozenset({
        LifecycleState.READY,
        LifecycleState.STOPPING,
        LifecycleState.FAILED,
    }),
    LifecycleState.READY: frozenset({LifecycleState.DRAINING, LifecycleState.STOPPING}),
    LifecycleState.DRAINING: frozenset({LifecycleState.STOPPING}),
    LifecycleState.STOPPING: frozenset({LifecycleState.STOPPED, LifecycleState.FAILED}),
    LifecycleState.STOPPED: frozenset({LifecycleState.STARTING}),
    LifecycleState.FAILED: frozenset({LifecycleState.STARTING, LifecycleState.STOPPING}),
}


class LifecycleStateMachine:
    """Guarded holder for one ``LifecycleState``.

    ``transition_to`` is the only way to mutate the state; an invalid transition
    raises before any side effect can run. The manager owns the machine, so
    request handlers and components can only observe the state.
    """

    def __init__(self, initial: LifecycleState = LifecycleState.NEW) -> None:
        self._state = initial

    @property
    def state(self) -> LifecycleState:
        return self._state

    def can_transition_to(self, target: LifecycleState) -> bool:
        return target in ALLOWED_TRANSITIONS[self._state]

    def transition_to(self, target: LifecycleState) -> LifecycleState:
        if not self.can_transition_to(target):
            from waxprep.lifecycle.errors import LifecycleTransitionError

            raise LifecycleTransitionError(
                "Invalid lifecycle transition",
                context={"from": str(self._state), "to": str(target)},
            )
        self._state = target
        return self._state
