"""Application-facing background runtime boundary (Stage 19).

Components submit work through ``BackgroundRuntime.submit`` without importing
Taskiq, a broker package or a worker implementation. The runtime adapter owns
the framework integration; the composition root selects it.
"""

from __future__ import annotations

from typing import Any, Protocol

from waxprep.background.errors import BackgroundUnavailableError
from waxprep.contracts.envelopes import MessageEnvelope


class BackgroundRuntime(Protocol):
    """Capability required by application code that submits background work."""

    @property
    def active(self) -> bool: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def submit(self, envelope: MessageEnvelope[Any]) -> str:
        """Submit a validated envelope and return the framework job id."""
        ...


class UnavailableBackgroundRuntime:
    """Fail-open stand-in used when the optional Taskiq extra is absent."""

    @property
    def active(self) -> bool:
        return False

    async def start(self) -> None:  # noqa: RUF029
        return None

    async def stop(self) -> None:  # noqa: RUF029
        return None

    async def submit(self, envelope: MessageEnvelope[Any]) -> str:  # noqa: RUF029
        del envelope
        raise BackgroundUnavailableError(
            "Background execution is unavailable; install the background extra"
        )
