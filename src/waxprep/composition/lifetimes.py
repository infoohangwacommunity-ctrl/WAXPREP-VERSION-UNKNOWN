"""Dependency lifetime policy (Stage 18).

Lifetimes are ordered from longest to shortest. A consumer may depend on a
provider with the same or a longer lifetime, never a shorter one:

* PROCESS can depend only on PROCESS.
* APPLICATION can depend on PROCESS or APPLICATION.
* REQUEST can depend on PROCESS, APPLICATION or REQUEST.
* OPERATION can depend on any lifetime.

This prevents an application singleton from retaining a request-scoped object.
Request/operation scopes are policy + validation today; no request-scoped
product component exists yet.
"""

from __future__ import annotations

from enum import StrEnum


class Lifetime(StrEnum):
    PROCESS = "process"
    APPLICATION = "application"
    REQUEST = "request"
    OPERATION = "operation"

    @property
    def rank(self) -> int:
        return _RANK[self]


_RANK: dict[Lifetime, int] = {
    Lifetime.PROCESS: 0,
    Lifetime.APPLICATION: 1,
    Lifetime.REQUEST: 2,
    Lifetime.OPERATION: 3,
}


def is_compatible(consumer: Lifetime, dependency: Lifetime) -> bool:
    """True when a dependency may be injected into a consumer of this lifetime."""
    return dependency.rank <= consumer.rank
