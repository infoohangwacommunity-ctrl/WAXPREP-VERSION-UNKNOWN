"""Structured lifecycle outcomes (Stage 16).

The report is the evidence a caller (or an operator reading logs) uses to answer:
what was acquired, what was released, what failed, and whether the original
startup failure survived cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from waxprep.lifecycle.background import TaskResult
from waxprep.lifecycle.states import LifecycleState


class OperationOutcome(StrEnum):
    """Bounded outcome vocabulary for one lifecycle operation."""

    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class CleanupStatus(StrEnum):
    """Aggregate cleanup quality, distinct from the final lifecycle state."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


@dataclass(frozen=True, slots=True)
class ComponentResult:
    """Outcome of initializing or releasing one named resource owner."""

    name: str
    outcome: OperationOutcome
    duration_ms: float
    mandatory: bool = True
    error_type: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.outcome is OperationOutcome.COMPLETED

    @property
    def failed(self) -> bool:
        return self.outcome in {
            OperationOutcome.FAILED,
            OperationOutcome.TIMED_OUT,
            OperationOutcome.CANCELLED,
        }


@dataclass(slots=True)
class LifecycleReport:
    """Evidence collected during one lifecycle execution."""

    final_state: LifecycleState = LifecycleState.NEW
    startup: list[ComponentResult] = field(default_factory=list[ComponentResult])
    cleanup: list[ComponentResult] = field(default_factory=list[ComponentResult])
    background: tuple[TaskResult, ...] = ()
    startup_error_type: str | None = None
    cleanup_cancelled: bool = False
    cleanup_skipped: bool = False
    leaked_tasks: tuple[str, ...] = ()
    degraded: tuple[str, ...] = ()

    @property
    def startup_succeeded(self) -> bool:
        return self.final_state in {LifecycleState.READY, LifecycleState.STOPPED} and (
            self.startup_error_type is None
        )

    @property
    def cleanup_failures(self) -> tuple[ComponentResult, ...]:
        return tuple(result for result in self.cleanup if result.failed)

    @property
    def cleanup_status(self) -> CleanupStatus:
        if self.cleanup_cancelled:
            return CleanupStatus.INTERRUPTED
        if self.cleanup_skipped:
            return CleanupStatus.FAILED
        if not self.cleanup:
            return CleanupStatus.SUCCESS
        failures = self.cleanup_failures
        if not failures:
            return CleanupStatus.SUCCESS
        completed = any(result.succeeded for result in self.cleanup)
        return CleanupStatus.PARTIAL if completed else CleanupStatus.FAILED

    @property
    def successful(self) -> bool:
        """True only for a clean start and a clean stop."""
        return (
            self.startup_error_type is None
            and self.final_state is LifecycleState.STOPPED
            and self.cleanup_status is CleanupStatus.SUCCESS
            and not self.leaked_tasks
        )
