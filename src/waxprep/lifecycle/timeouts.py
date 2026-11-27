"""Central lifecycle timeout policy (Stage 16).

Timeouts are defined once and validated here instead of being scattered as
arbitrary literals through startup and shutdown code. Every value is a positive,
finite number of seconds.

Policy:

* ``startup_seconds`` bounds the whole mandatory initialization sequence.
* ``component_seconds`` bounds one component's initialization and one cleanup
  callback, so a hung component cannot block the rest of the lifecycle.
* ``background_stop_seconds`` bounds cooperative background-task termination.
* ``observability_seconds`` bounds the final telemetry flush/shutdown.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LifecycleTimeouts:
    """Validated, centrally defined lifecycle deadlines."""

    startup_seconds: float = 30.0
    component_seconds: float = 10.0
    background_stop_seconds: float = 10.0
    observability_seconds: float = 10.0

    def __post_init__(self) -> None:
        for name, value in (
            ("startup_seconds", self.startup_seconds),
            ("component_seconds", self.component_seconds),
            ("background_stop_seconds", self.background_stop_seconds),
            ("observability_seconds", self.observability_seconds),
        ):
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive finite number of seconds")
