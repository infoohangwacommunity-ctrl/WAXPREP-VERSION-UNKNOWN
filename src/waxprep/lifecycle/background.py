"""Owned background-task supervision (Stage 16).

WaxPrep has no production background services yet. This is the ownership
boundary future services must use so they never call ``asyncio.create_task``
without an owner.

Design notes:

* The supervisor is the *only* place in ``src/`` allowed to create tasks; a
  structural architecture test and a Semgrep rule enforce that.
* Tasks are independent by default. ``asyncio.TaskGroup`` is deliberately not
  used here because it is fail-fast: one service crashing would cancel unrelated
  services. A tightly coupled group, when one exists, may use ``TaskGroup``
  inside a single supervised task.
* ``stop`` cancels owned tasks and waits for them with one bounded timeout.
  A task that ignores cancellation is reported as ``timed_out`` and remains
  visible in ``active_tasks`` for leak detection; it is never silently forgotten.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger()


class TaskSupervisorError(RuntimeError):
    """An unmanaged or duplicate background task was requested."""


class TaskOutcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True, slots=True)
class TaskResult:
    """Termination outcome for one owned background task."""

    name: str
    outcome: TaskOutcome
    error_type: str | None = None

    @property
    def failed(self) -> bool:
        return self.outcome in {TaskOutcome.FAILED, TaskOutcome.TIMED_OUT}


class BackgroundTaskSupervisor:
    """Owns every long-running task started through it."""

    def __init__(
        self,
        *,
        on_error: Callable[[str, BaseException], None] | None = None,
    ) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._stopping = False
        self._last_results: tuple[TaskResult, ...] = ()
        self._on_error = on_error

    @property
    def active_tasks(self) -> tuple[str, ...]:
        """Names of tasks that have not finished yet (leak check)."""
        return tuple(sorted(self._tasks))

    @property
    def stopped(self) -> bool:
        return self._stopping

    def reset(self) -> None:
        """Re-arm a stopped supervisor for a new lifecycle execution."""
        if self._tasks:
            raise TaskSupervisorError("Cannot reset a supervisor with active tasks")
        self._stopping = False
        self._last_results = ()

    def start(self, name: str, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Start one named, owned task. Reject duplicates and shutdown races."""
        if not name.strip():
            coro.close()
            raise TaskSupervisorError("Background task name must be non-empty")
        if self._stopping:
            coro.close()
            raise TaskSupervisorError("Cannot start a task while the supervisor is stopping")
        if name in self._tasks:
            coro.close()
            raise TaskSupervisorError(f"Background task {name!r} is already running")

        task = asyncio.create_task(coro, name=f"waxprep-bg:{name}")
        self._tasks[name] = task
        task.add_done_callback(lambda finished: self._finalize(name, finished))
        return task

    def _finalize(self, name: str, task: asyncio.Task[Any]) -> None:
        if self._tasks.get(name) is task:
            self._tasks.pop(name, None)
        if task.cancelled():
            return
        error = task.exception()
        if error is None:
            return
        logger.error(
            "background_task_failed",
            task=name,
            error_type=type(error).__name__,
        )
        if self._on_error is not None:
            try:
                self._on_error(name, error)
            except Exception:  # noqa: BLE001 - error reporting must not crash the loop
                logger.warning("background_task_error_handler_failed", exc_info=True)

    async def stop(self, timeout: float) -> tuple[TaskResult, ...]:
        """Cancel and await owned tasks with one bounded timeout.

        Idempotent: repeated calls return the first outcome without re-cancelling
        tasks that may already be gone.
        """
        if self._stopping:
            return self._last_results
        self._stopping = True
        tasks = list(self._tasks.values())
        if not tasks:
            self._last_results = ()
            return self._last_results

        names = list(self._tasks)
        for task in tasks:
            task.cancel()

        done, pending = await asyncio.wait(tasks, timeout=timeout)
        results: list[TaskResult] = []
        for name, task in zip(names, tasks, strict=True):
            if task in pending:
                results.append(TaskResult(name=name, outcome=TaskOutcome.TIMED_OUT))
                continue
            if task.cancelled():
                results.append(TaskResult(name=name, outcome=TaskOutcome.CANCELLED))
                continue
            error = task.exception() if task in done else None
            if error is not None:
                results.append(
                    TaskResult(
                        name=name,
                        outcome=TaskOutcome.FAILED,
                        error_type=type(error).__name__,
                    )
                )
            else:
                results.append(TaskResult(name=name, outcome=TaskOutcome.COMPLETED))

        self._last_results = tuple(results)
        logger.info(
            "background_tasks_stopped",
            outcomes=[result.outcome.value for result in results],
        )
        return self._last_results
