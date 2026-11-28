"""Independent background worker entrypoint (Stage 19).

This module is an outer entrypoint, like ``main.py``. It may import composition;
the background infrastructure package does not depend on composition.

The worker is not a second FastAPI application and does not create a second
lifecycle/DI system. It:

1. loads validated settings;
2. assembles a worker-specific bundle through the Stage 18 composition root;
3. starts the selected Taskiq broker/runtime through a Stage 16 lifecycle component;
4. waits for termination and shuts down in reverse order.

The selected execution framework owns worker consumption mechanics for a real
broker deployment. The in-memory foundation adapter executes submitted tasks in
the process that submits them; a durable broker deployment supplies its broker
implementation through composition. No product job handlers are registered here.
"""

from __future__ import annotations

import asyncio
import signal
from dataclasses import dataclass

import structlog

from waxprep.background.registry import JobRegistry
from waxprep.composition import CompositionRoot, WorkerDependencies
from waxprep.config import settings
from waxprep.lifecycle import (
    ApplicationLifecycle,
    BackgroundTaskSupervisor,
    LifecycleComponent,
)

logger = structlog.get_logger()


@dataclass(slots=True)
class _WorkerState:
    dependencies: WorkerDependencies | None = None


def _initialize_configuration() -> None:
    logger.info(
        "worker_configuration_loaded",
        environment=settings.environment.value,
        log_level=settings.log_level.value,
    )


def _compose_worker(
    lifecycle: ApplicationLifecycle,
    supervisor: BackgroundTaskSupervisor,
    root: CompositionRoot,
    registry: JobRegistry | None,
    state: _WorkerState,
) -> None:
    state.dependencies = root.build_worker(
        lifecycle=lifecycle,
        supervisor=supervisor,
        registry=registry,
    )
    logger.info(
        "worker_composition_assembled",
        tasks=list(state.dependencies.job_registry.task_names),
    )


def _release_worker(state: _WorkerState) -> None:
    state.dependencies = None


async def _start_background(state: _WorkerState) -> None:
    if state.dependencies is None:
        raise RuntimeError("Worker dependencies are not composed")
    await state.dependencies.background.start()


async def _stop_background(state: _WorkerState) -> None:
    if state.dependencies is not None:
        await state.dependencies.background.stop()


class BackgroundWorker:
    """Run one worker lifecycle without importing FastAPI."""

    def __init__(
        self,
        *,
        composition_root: CompositionRoot | None = None,
        registry: JobRegistry | None = None,
    ) -> None:
        self._root = composition_root or CompositionRoot(settings)
        self._registry = registry

    async def run(self, stop_event: asyncio.Event) -> None:
        supervisor = BackgroundTaskSupervisor()
        lifecycle = ApplicationLifecycle(background=supervisor)
        state = _WorkerState()

        lifecycle.register(
            LifecycleComponent(
                name="configuration",
                initialize=_initialize_configuration,
                description="Validated worker settings",
            )
        )
        lifecycle.register(
            LifecycleComponent(
                name="composition",
                initialize=lambda: _compose_worker(
                    lifecycle, supervisor, self._root, self._registry, state
                ),
                release=lambda: _release_worker(state),
                depends_on=("configuration",),
                description="Worker-specific typed dependency bundle",
            )
        )
        lifecycle.register(
            LifecycleComponent(
                name="background",
                initialize=lambda: _start_background(state),
                release=lambda: _stop_background(state),
                depends_on=("composition",),
                description="Taskiq runtime startup and graceful shutdown",
            )
        )

        await lifecycle.start()
        logger.info("background_worker_started")
        try:
            await stop_event.wait()
        finally:
            logger.info("background_worker_stopping")
            await lifecycle.shutdown()
            state.dependencies = None
            logger.info("background_worker_stopped")


async def _run_until_signal() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            continue
    worker = BackgroundWorker()
    await worker.run(stop_event)


def run() -> None:
    """Console entrypoint: ``python -m waxprep.background.worker``."""
    asyncio.run(_run_until_signal())


if __name__ == "__main__":
    run()
