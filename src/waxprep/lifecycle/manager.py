"""Explicit application lifecycle orchestration (Stage 16).

The manager owns one lifecycle execution at a time for one application instance.
It coordinates four phases:

1. **Startup** — validate order, initialize mandatory components, record optional
   degradation.
2. **Readiness** — only ``READY`` is accepted by the health boundary.
3. **Termination** — ``READY -> DRAINING -> STOPPING``, stopping owned
   background work before releasing resources.
4. **Cleanup** — reverse acquisition order via ``AsyncExitStack``, then the
   observability finalizer (telemetry flush/exporters), then final state.

Failure rules:

* A mandatory startup failure rolls back everything acquired so far and re-raises
  the original exception unchanged.
* Cleanup failures are isolated: every remaining resource still receives its
  release attempt, and the failures are recorded in ``LifecycleReport``.
* Cancellation is recorded distinctly, cleanup still runs, and
  ``CancelledError`` propagates afterwards. It is never reclassified as an
  ordinary application failure.
* A stopped/failed lifecycle is idempotent: a second ``shutdown`` does not run
  cleanup twice.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable
from contextlib import AsyncExitStack
from typing import Any

import structlog

from waxprep.lifecycle.background import BackgroundTaskSupervisor, TaskOutcome, TaskResult
from waxprep.lifecycle.components import LifecycleComponent
from waxprep.lifecycle.errors import (
    LifecycleError,
    LifecycleTransitionError,
    ResourceOwnershipError,
)
from waxprep.lifecycle.report import (
    ComponentResult,
    LifecycleReport,
    OperationOutcome,
)
from waxprep.lifecycle.states import LifecycleState, LifecycleStateMachine
from waxprep.lifecycle.timeouts import LifecycleTimeouts

logger = structlog.get_logger()

_STARTABLE = frozenset({LifecycleState.NEW, LifecycleState.STOPPED, LifecycleState.FAILED})
_TERMINAL = frozenset({LifecycleState.STOPPED, LifecycleState.FAILED})

ResourceCallable = Callable[[], Any]


class ApplicationLifecycle:
    """Owns one application instance's lifecycle state and resources."""

    def __init__(
        self,
        *,
        timeouts: LifecycleTimeouts | None = None,
        background: BackgroundTaskSupervisor | None = None,
    ) -> None:
        self._state_machine = LifecycleStateMachine()
        self._timeouts = timeouts or LifecycleTimeouts()
        self._background = background
        self._observability_cleanup: ResourceCallable | None = None
        self._components: list[LifecycleComponent] = []
        self._by_name: dict[str, LifecycleComponent] = {}
        self._stack: AsyncExitStack | None = None
        self._lock = asyncio.Lock()
        self._report = LifecycleReport()
        self._cleanup_started = False
        self._cleanup_completed = False
        self._cleanup_cancelled = False

    # ── Observation ─────────────────────────────────────────────────────────

    @property
    def state(self) -> LifecycleState:
        return self._state_machine.state

    @property
    def report(self) -> LifecycleReport:
        return self._report

    @property
    def components(self) -> tuple[LifecycleComponent, ...]:
        return tuple(self._components)

    @property
    def is_ready(self) -> bool:
        return self._state_machine.state is LifecycleState.READY

    # ── Composition ─────────────────────────────────────────────────────────

    def register(self, component: LifecycleComponent) -> None:
        """Register a component before the first startup.

        Dependencies must already be registered, which makes the initialization
        order explicit and rejects accidental forward references.
        """
        if self._state_machine.state is not LifecycleState.NEW:
            raise LifecycleError("Components can only be registered before startup begins")
        if component.name in self._by_name:
            raise ResourceOwnershipError(
                "A component with this owner identity is already registered",
                context={"component": component.name},
            )
        for dependency in component.depends_on:
            if dependency not in self._by_name:
                raise ResourceOwnershipError(
                    "Component dependency must be registered before its dependant",
                    context={"component": component.name, "dependency": dependency},
                )
        self._components.append(component)
        self._by_name[component.name] = component

    def attach_background(self, supervisor: BackgroundTaskSupervisor) -> None:
        self._background = supervisor

    def set_observability_cleanup(self, cleanup: ResourceCallable) -> None:
        """Register the final flush/exporters release (runs after resources)."""
        self._observability_cleanup = cleanup

    # ── Startup ─────────────────────────────────────────────────────────────

    async def start(self) -> LifecycleReport:
        """Initialize mandatory components or roll everything back."""
        async with self._lock:
            if self._state_machine.state not in _STARTABLE:
                raise LifecycleTransitionError(
                    "Startup is not allowed from the current state",
                    context={"state": str(self._state_machine.state)},
                )
            self._prepare_start()

            failure: BaseException | None = None
            total_timeout = asyncio.timeout(self._timeouts.startup_seconds)
            try:
                async with total_timeout:
                    for component in self._components:
                        await self._initialize(component)
            except BaseException as exc:  # noqa: BLE001 - rollback must cover cancellation
                failure = exc
                self._report.startup_error_type = type(exc).__name__
                logger.error(
                    "lifecycle_startup_failed",
                    state=str(self._state_machine.state),
                    error_type=type(exc).__name__,
                )

            if failure is not None:
                await self._rollback()
                raise failure

            self._state_machine.transition_to(LifecycleState.READY)
            self._report.final_state = LifecycleState.READY
            logger.info(
                "lifecycle_ready",
                components=[component.name for component in self._components],
            )
            return self._report

    def _prepare_start(self) -> None:
        self._state_machine.transition_to(LifecycleState.STARTING)
        self._report = LifecycleReport(final_state=LifecycleState.STARTING)
        self._stack = AsyncExitStack()
        self._cleanup_started = False
        self._cleanup_completed = False
        self._cleanup_cancelled = False
        if self._background is not None:
            self._background.reset()
        logger.info(
            "lifecycle_starting",
            components=[component.name for component in self._components],
        )

    async def _initialize(self, component: LifecycleComponent) -> None:
        started = time.perf_counter()
        timeout = asyncio.timeout(self._timeouts.component_seconds)
        try:
            async with timeout:
                result = component.initialize() if component.initialize is not None else None
                if inspect.isawaitable(result):
                    await result
        except asyncio.CancelledError:
            self._record_startup(component, OperationOutcome.CANCELLED, started)
            logger.warning("lifecycle_component_cancelled", component=component.name)
            raise
        except TimeoutError:
            outcome = OperationOutcome.TIMED_OUT if timeout.expired() else OperationOutcome.FAILED
            self._record_startup(component, outcome, started)
            logger.error(
                "lifecycle_component_failed",
                component=component.name,
                outcome=str(outcome),
                mandatory=component.mandatory,
            )
            if component.mandatory:
                raise
            self._mark_degraded(component)
        except Exception as exc:
            self._record_startup(component, OperationOutcome.FAILED, started, exc)
            logger.error(
                "lifecycle_component_failed",
                component=component.name,
                error_type=type(exc).__name__,
                mandatory=component.mandatory,
            )
            if component.mandatory:
                raise
            self._mark_degraded(component)
        else:
            self._record_startup(component, OperationOutcome.COMPLETED, started)
            logger.info("lifecycle_component_ready", component=component.name)
            if component.release is not None:
                assert self._stack is not None
                self._stack.push_async_callback(self._release_component, component)

    def _record_startup(
        self,
        component: LifecycleComponent,
        outcome: OperationOutcome,
        started: float,
        error: BaseException | None = None,
    ) -> None:
        self._report.startup.append(
            ComponentResult(
                name=component.name,
                outcome=outcome,
                duration_ms=(time.perf_counter() - started) * 1000,
                mandatory=component.mandatory,
                error_type=type(error).__name__ if error is not None else None,
            )
        )

    def _mark_degraded(self, component: LifecycleComponent) -> None:
        self._report.degraded = (*self._report.degraded, component.name)
        logger.warning("lifecycle_component_degraded", component=component.name)

    # ── Shutdown ────────────────────────────────────────────────────────────

    async def shutdown(self) -> LifecycleReport:
        """Drain, stop background work, release resources, finalize telemetry."""
        async with self._lock:
            state = self._state_machine.state
            if state in _TERMINAL and self._cleanup_completed:
                return self._report
            if state is LifecycleState.READY:
                self._state_machine.transition_to(LifecycleState.DRAINING)
                self._report.final_state = LifecycleState.DRAINING
                logger.info("lifecycle_draining")
            elif state is not LifecycleState.NEW:
                raise LifecycleTransitionError(
                    "Shutdown is not allowed from the current state",
                    context={"state": str(state)},
                )

            self._state_machine.transition_to(LifecycleState.STOPPING)
            self._report.final_state = LifecycleState.STOPPING
            cancelled = await self._cleanup()
            final = (
                LifecycleState.FAILED
                if cancelled or self._report.cleanup_failures or self._report.leaked_tasks
                else LifecycleState.STOPPED
            )
            self._state_machine.transition_to(final)
            self._report.final_state = final
            logger.info(
                "lifecycle_stopped",
                state=str(final),
                cleanup_status=str(self._report.cleanup_status),
            )
            if cancelled:
                raise asyncio.CancelledError
            return self._report

    async def _rollback(self) -> None:
        self._state_machine.transition_to(LifecycleState.STOPPING)
        self._report.final_state = LifecycleState.STOPPING
        logger.warning("lifecycle_rollback_started")
        await self._cleanup()
        self._state_machine.transition_to(LifecycleState.FAILED)
        self._report.final_state = LifecycleState.FAILED
        logger.info(
            "lifecycle_rollback_completed",
            cleanup_status=str(self._report.cleanup_status),
        )

    async def _cleanup(self) -> bool:
        if self._cleanup_started:
            return self._cleanup_cancelled
        self._cleanup_started = True
        logger.info("lifecycle_cleanup_started")

        await self._stop_background()

        if self._report.leaked_tasks:
            # A supervised task may still be using application resources. Closing
            # them now would risk use-after-close. The safe policy is to stop
            # releasing, record the leak and fail shutdown; process termination
            # (or a supervisor restart) is the final backstop.
            self._cleanup_completed = True
            self._report.cleanup_cancelled = self._cleanup_cancelled
            logger.error(
                "lifecycle_cleanup_skipped_due_to_leaked_tasks",
                tasks=list(self._report.leaked_tasks),
            )
            return self._cleanup_cancelled

        stack = self._stack
        self._stack = None
        if stack is not None:
            await stack.aclose()

        if self._observability_cleanup is not None:
            await self._release_named(
                "observability",
                self._observability_cleanup,
                timeout_seconds=self._timeouts.observability_seconds,
            )

        self._cleanup_completed = True
        self._report.cleanup_cancelled = self._cleanup_cancelled
        if self._cleanup_cancelled:
            logger.warning("lifecycle_cleanup_interrupted")
        else:
            logger.info("lifecycle_cleanup_completed")
        return self._cleanup_cancelled

    async def _stop_background(self) -> None:
        if self._background is None:
            return
        try:
            results: tuple[TaskResult, ...] = await self._background.stop(
                self._timeouts.background_stop_seconds
            )
        except asyncio.CancelledError:
            self._cleanup_cancelled = True
            self._report.cleanup_cancelled = True
            logger.warning("lifecycle_background_stop_cancelled")
            return
        self._report.background = results
        leaked = tuple(result.name for result in results if result.outcome is TaskOutcome.TIMED_OUT)
        if leaked:
            self._report.leaked_tasks = leaked
            self._report.cleanup_skipped = True
            logger.error("lifecycle_background_tasks_leaked", tasks=list(leaked))

    async def _release_component(self, component: LifecycleComponent) -> None:
        assert component.release is not None  # only registered after success
        await self._release_named(component.name, component.release, component.mandatory)

    async def _release_named(
        self,
        name: str,
        release: ResourceCallable,
        mandatory: bool = True,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        started = time.perf_counter()
        timeout = asyncio.timeout(
            self._timeouts.component_seconds if timeout_seconds is None else timeout_seconds
        )
        try:
            async with timeout:
                result = release()
                if inspect.isawaitable(result):
                    await result
        except asyncio.CancelledError:
            self._cleanup_cancelled = True
            self._report.cleanup_cancelled = True
            self._record_cleanup(name, OperationOutcome.CANCELLED, started, mandatory)
            logger.warning("lifecycle_cleanup_cancelled", component=name)
        except TimeoutError:
            outcome = OperationOutcome.TIMED_OUT if timeout.expired() else OperationOutcome.FAILED
            self._record_cleanup(name, outcome, started, mandatory)
            logger.error("lifecycle_cleanup_failed", component=name, outcome=str(outcome))
        except Exception as exc:
            self._record_cleanup(name, OperationOutcome.FAILED, started, mandatory, exc)
            logger.error(
                "lifecycle_cleanup_failed",
                component=name,
                error_type=type(exc).__name__,
            )
        else:
            self._record_cleanup(name, OperationOutcome.COMPLETED, started, mandatory)
            logger.info("lifecycle_resource_released", component=name)

    def _record_cleanup(
        self,
        name: str,
        outcome: OperationOutcome,
        started: float,
        mandatory: bool,
        error: BaseException | None = None,
    ) -> None:
        self._report.cleanup.append(
            ComponentResult(
                name=name,
                outcome=outcome,
                duration_ms=(time.perf_counter() - started) * 1000,
                mandatory=mandatory,
                error_type=type(error).__name__ if error is not None else None,
            )
        )
