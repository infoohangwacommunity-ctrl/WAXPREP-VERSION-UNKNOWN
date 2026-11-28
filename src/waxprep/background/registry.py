"""Open-world background job registration and dispatch (Stage 19).

A component registers a typed handler under a stable task identity. The
background infrastructure dispatches by ``MessageEnvelope.message_type`` and
validates the complete Stage 17 envelope before invoking the handler; it never
contains a fixed list of WaxPrep business jobs.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, cast

import structlog
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from waxprep.background.errors import (
    JobExecutionError,
    JobRegistrationError,
    JobValidationError,
)
from waxprep.contracts.envelopes import MessageEnvelope
from waxprep.contracts.errors import ContractValidationError
from waxprep.contracts.models.base import ContractModel, ContractRootModel
from waxprep.contracts.models.result import (
    ErrorDetail,
    OperationFailure,
    OperationResult,
    OperationStatus,
)
from waxprep.contracts.validation import validate_contract
from waxprep.errors.taxonomy import CancellationError, WaxPrepError

logger = structlog.get_logger()

_TASK_NAME = re.compile(r"^[a-z][a-z0-9]*(\.[a-z0-9]+)+$")


class _JobHeader(BaseModel):
    """Internal header extraction; not a published communication contract."""

    model_config = ConfigDict(extra="ignore", strict=True)

    message_type: str = Field(pattern=r"^[a-z][a-z0-9]*(\.[a-z0-9]+)+$")


@dataclass(frozen=True, slots=True)
class JobHandler[PayloadT: ContractModel | ContractRootModel[Any]]:
    """One typed background capability registered by a component."""

    task_name: str
    payload_type: type[PayloadT]
    handler: Callable[[MessageEnvelope[PayloadT]], Awaitable[OperationResult]]

    def __post_init__(self) -> None:
        if _TASK_NAME.fullmatch(self.task_name) is None:
            raise JobRegistrationError(
                "Task name must be a lower-case dot-separated identity",
                context={"task": self.task_name},
            )
        if not isinstance(self.payload_type, type) or not issubclass(  # pyright: ignore[reportUnnecessaryIsInstance]
            self.payload_type, (ContractModel, ContractRootModel)
        ):
            raise JobRegistrationError(
                "Task payload type must be a strict contract model",
                context={"task": self.task_name},
            )
        if not callable(self.handler):
            raise JobRegistrationError(
                "Task handler must be callable",
                context={"task": self.task_name},
            )
        try:
            signature = inspect.signature(self.handler)
        except TypeError, ValueError:
            return
        keyword_only = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind is inspect.Parameter.KEYWORD_ONLY
            and parameter.default is inspect.Parameter.empty
        ]
        if keyword_only:
            raise JobRegistrationError(
                "Task handler must accept the envelope positionally",
                context={"task": self.task_name},
            )
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind
            in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        required = [
            parameter for parameter in positional if parameter.default is inspect.Parameter.empty
        ]
        has_varargs = any(
            parameter.kind is inspect.Parameter.VAR_POSITIONAL
            for parameter in signature.parameters.values()
        )
        if len(required) > 1 or (not has_varargs and len(positional) < 1):
            raise JobRegistrationError(
                "Task handler must accept one envelope argument",
                context={"task": self.task_name},
            )

    @property
    def envelope_adapter(self) -> TypeAdapter[Any]:
        return TypeAdapter(cast(Any, MessageEnvelope)[self.payload_type])


class JobRegistry:
    """Registry of task identities; no fixed business catalogue."""

    def __init__(self) -> None:
        self._handlers: dict[str, JobHandler[Any]] = {}

    @property
    def task_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._handlers))

    def register(self, handler: JobHandler[Any]) -> None:
        if handler.task_name in self._handlers:
            raise JobRegistrationError(
                "A handler with this task identity is already registered",
                context={"task": handler.task_name},
            )
        self._handlers[handler.task_name] = handler

    def resolve(self, task_name: str) -> JobHandler[Any]:
        try:
            return self._handlers[task_name]
        except KeyError as exc:
            raise JobRegistrationError(
                "No handler is registered for this background task",
                context={"task": task_name},
            ) from exc

    async def execute(self, raw_envelope: dict[str, Any]) -> OperationResult:
        """Validate and execute one incoming job message."""
        try:
            header = _JobHeader.model_validate(raw_envelope)
        except ValidationError as exc:
            raise JobValidationError("Background job has no valid task identity") from exc
        handler = self.resolve(header.message_type)
        try:
            text = json.dumps(raw_envelope, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise JobValidationError("Background job is not serializable") from exc
        try:
            envelope = validate_contract(handler.envelope_adapter, text)
        except ContractValidationError as exc:
            raise JobValidationError("Background job envelope is invalid") from exc

        started = time.perf_counter()
        logger.info(
            "background_job_started",
            task=handler.task_name,
            job_id=str(envelope.message_id),
            correlation_id=str(envelope.correlation_id),
        )
        try:
            result = await handler.handler(envelope)
        except CancellationError:
            raise
        except WaxPrepError as exc:
            result = OperationResult(
                OperationFailure(
                    status=OperationStatus.FAILED,
                    error=ErrorDetail.from_error(exc),
                )
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Preserve the original exception type so the selected execution
            # framework/middleware can classify and retry it. WaxPrep does not
            # maintain a hardcoded retryable-exception catalogue here.
            logger.error(
                "background_job_failed",
                task=handler.task_name,
                job_id=str(envelope.message_id),
                error_type=type(exc).__name__,
            )
            raise
        if not isinstance(result, OperationResult):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise JobExecutionError(
                "The background job handler did not return an OperationResult",
                context={"task": handler.task_name},
            )
        logger.info(
            "background_job_completed",
            task=handler.task_name,
            job_id=str(envelope.message_id),
            outcome=str(result.status),
            duration_ms=(time.perf_counter() - started) * 1000,
        )
        return result
