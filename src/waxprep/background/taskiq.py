"""Taskiq adapter for the background execution boundary (Stage 19).

Taskiq owns task submission, broker transport and worker mechanics. WaxPrep owns
the envelope contract, validation, handler registration, composition and
lifecycle. The default broker is Taskiq's in-memory broker for foundation tests;
a deployment can supply Redis/RabbitMQ/NATS through ``CompositionRoot``
overrides without changing the application-facing interface.

The adapter registers one dispatcher task. Business handlers are registered
dynamically by task identity, so the infrastructure never contains a fixed job
catalogue.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any, cast

import structlog
from taskiq import AsyncBroker, InMemoryBroker, TaskiqMiddleware

from waxprep.background.errors import (
    BackgroundUnavailableError,
    JobSubmissionError,
)
from waxprep.background.registry import JobRegistry
from waxprep.contracts.envelopes import MessageEnvelope
from waxprep.contracts.validation import dump_contract

logger = structlog.get_logger()

DISPATCHER_TASK_NAME = "waxprep.background.execute"


class TaskiqBackgroundRuntime:
    """Taskiq-backed implementation of the application submission boundary."""

    def __init__(
        self,
        registry: JobRegistry,
        *,
        broker: AsyncBroker | None = None,
        middlewares: Sequence[TaskiqMiddleware] = (),
        worker_process: bool = False,
    ) -> None:
        self._registry = registry
        self._broker = broker or InMemoryBroker()
        self._broker.is_worker_process = worker_process
        if middlewares:
            self._broker.with_middlewares(*middlewares)

        async def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
            result = await registry.execute(payload)
            return cast(dict[str, Any], result.model_dump(mode="json"))

        self._dispatcher: Any = self._broker.task(DISPATCHER_TASK_NAME)(dispatch)
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    async def start(self) -> None:
        if self._active:
            return
        await self._broker.startup()
        self._active = True

    async def stop(self) -> None:
        if not self._active:
            return
        await self._broker.shutdown()
        self._active = False

    async def consume(self, stop_event: asyncio.Event) -> None:
        """Run the real Taskiq receiver loop until the stop event is set."""
        if not self._active:
            raise BackgroundUnavailableError(
                "Background runtime is not started; start it through the lifecycle"
            )
        if isinstance(self._broker, InMemoryBroker):
            raise BackgroundUnavailableError(
                "InMemoryBroker is test/development-only and cannot run an independent worker"
            )
        from taskiq.receiver import Receiver

        receiver = Receiver(
            self._broker,
            run_startup=False,
            propagate_exceptions=False,
            max_async_tasks=100,
        )
        await receiver.listen(stop_event)

    async def submit(self, envelope: MessageEnvelope[Any]) -> str:
        if not self._active:
            raise BackgroundUnavailableError(
                "Background runtime is not started; start it through the lifecycle"
            )
        try:
            text = dump_contract(type(envelope), envelope)
            task = await self._dispatcher.kiq(json.loads(text))
        except Exception as exc:  # noqa: BLE001 - submission boundary
            raise JobSubmissionError(
                "The background job could not be submitted",
                context={"task": envelope.message_type},
            ) from exc
        logger.info(
            "background_job_submitted",
            task=envelope.message_type,
            job_id=str(envelope.message_id),
            correlation_id=str(envelope.correlation_id),
            framework_job_id=str(task.task_id),
        )
        return str(task.task_id)
