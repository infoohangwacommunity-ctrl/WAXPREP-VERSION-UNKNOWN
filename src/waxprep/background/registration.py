"""Generic job-contributor extension point (Stage 19).

A component contributes its handlers to the worker/application registry through
this interface. The background infrastructure never contains a hardcoded
business-job catalogue, and no filesystem/plugin discovery is introduced.
"""

from __future__ import annotations

from typing import Protocol

from waxprep.background.registry import JobRegistry


class JobContributor(Protocol):
    """A component that contributes one or more background handlers."""

    def register_jobs(self, registry: JobRegistry) -> None: ...
