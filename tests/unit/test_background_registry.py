"""Stage 19 — open-world job registration and dispatch."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from pydantic import TypeAdapter

from waxprep.background.errors import (
    JobExecutionError,
    JobRegistrationError,
    JobValidationError,
)
from waxprep.background.registry import JobHandler, JobRegistry
from waxprep.contracts.envelopes import MessageEnvelope, MessageKind
from waxprep.contracts.models.result import OperationResult, OperationStatus, OperationSuccess
from waxprep.errors.taxonomy import NotFoundError

pytestmark = pytest.mark.unit


def envelope(**overrides) -> MessageEnvelope[OperationSuccess]:
    values: dict[str, Any] = {
        "message_id": uuid4(),
        "message_kind": MessageKind.REQUEST,
        "message_type": "waxprep.test.job",
        "contract_version": "1.0.0",
        "correlation_id": uuid4(),
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        "producer": "waxprep.test",
        "payload": OperationSuccess(status=OperationStatus.SUCCESS, detail="payload"),
    }
    values.update(overrides)
    return MessageEnvelope[OperationSuccess](**values)


async def success_handler(_envelope: MessageEnvelope[OperationSuccess]) -> OperationResult:  # noqa: RUF029
    return OperationResult(OperationSuccess(status=OperationStatus.SUCCESS, detail="done"))


def handler() -> JobHandler[OperationSuccess]:
    return JobHandler(
        task_name="waxprep.test.job",
        payload_type=OperationSuccess,
        handler=success_handler,
    )


class TestJobHandler:
    @pytest.mark.parametrize("task_name", ["Bad", "single", "waxprep..job", ""])
    def test_invalid_task_name_rejected(self, task_name):
        with pytest.raises(JobRegistrationError, match="Task name"):
            JobHandler(task_name=task_name, payload_type=OperationSuccess, handler=success_handler)

    def test_non_contract_payload_type_rejected(self):
        with pytest.raises(JobRegistrationError, match="payload type"):
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=dict,  # type: ignore[arg-type]
                handler=success_handler,
            )

    def test_non_callable_handler_rejected(self):
        with pytest.raises(JobRegistrationError, match="callable"):
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler="nope",  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        "bad_handler",
        [
            lambda: None,
            lambda a, b: None,
        ],
    )
    def test_handler_signature_must_accept_one_argument(self, bad_handler):
        with pytest.raises(JobRegistrationError, match="one envelope"):
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=bad_handler,  # type: ignore[arg-type]
            )

    def test_uninspectable_handler_is_accepted_for_construction(self):
        class Uninspectable:
            __signature__ = "not a signature"

            def __call__(self, _envelope):
                return None

        assert (
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=Uninspectable(),
            ).task_name
            == "waxprep.test.job"
        )

    def test_required_keyword_only_handler_rejected(self):
        async def keyword_only(*, envelope):  # noqa: RUF029
            return OperationResult(OperationSuccess(status=OperationStatus.SUCCESS))

        with pytest.raises(JobRegistrationError, match="positionally"):
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=keyword_only,
            )

    def test_varargs_handler_is_accepted(self):
        async def varargs(*_args):  # noqa: RUF029
            return OperationResult(OperationSuccess(status=OperationStatus.SUCCESS))

        assert (
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=varargs,
            ).task_name
            == "waxprep.test.job"
        )

    def test_envelope_adapter(self):
        assert isinstance(handler().envelope_adapter, TypeAdapter)


class TestJobRegistry:
    def test_register_resolve_and_task_names(self):
        registry = JobRegistry()
        registry.register(handler())
        assert registry.task_names == ("waxprep.test.job",)
        assert registry.resolve("waxprep.test.job").task_name == "waxprep.test.job"

    def test_duplicate_registration_rejected(self):
        registry = JobRegistry()
        registry.register(handler())
        with pytest.raises(JobRegistrationError, match="already registered"):
            registry.register(handler())

    def test_unknown_task_rejected(self):
        with pytest.raises(JobRegistrationError, match="No handler"):
            JobRegistry().resolve("waxprep.missing.job")

    def test_execute_valid_envelope(self):
        registry = JobRegistry()
        registry.register(handler())
        result = asyncio.run(registry.execute(envelope().model_dump(mode="json")))
        assert result.successful is True
        assert result.status is OperationStatus.SUCCESS

    def test_execute_missing_task_identity(self):
        registry = JobRegistry()
        registry.register(handler())
        with pytest.raises(JobValidationError, match="task identity"):
            asyncio.run(registry.execute({"payload": {}}))

    def test_execute_unknown_task(self):
        registry = JobRegistry()
        with pytest.raises(JobRegistrationError, match="No handler"):
            asyncio.run(
                registry.execute(
                    envelope(message_type="waxprep.unknown.job").model_dump(mode="json")
                )
            )

    def test_execute_invalid_envelope(self):
        registry = JobRegistry()
        registry.register(handler())
        raw = envelope().model_dump(mode="json")
        raw["payload"] = {"status": "missing-required-fields"}
        with pytest.raises(JobValidationError, match="envelope is invalid"):
            asyncio.run(registry.execute(raw))

    def test_execute_non_serializable_raw(self):
        registry = JobRegistry()
        registry.register(handler())
        raw = envelope().model_dump(mode="json")
        raw["payload"]["detail"] = float("nan")
        with pytest.raises(JobValidationError, match="not serializable"):
            asyncio.run(registry.execute(raw))

    def test_typed_handler_error_becomes_failure_result(self):
        async def failing(_envelope):  # noqa: RUF029
            raise NotFoundError("missing")

        registry = JobRegistry()
        registry.register(
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=failing,
            )
        )
        result = asyncio.run(registry.execute(envelope().model_dump(mode="json")))
        assert result.status is OperationStatus.FAILED
        assert result.error is not None
        assert result.error.code == "WAX-1005"

    def test_unexpected_handler_error_propagates_for_framework_policy(self):
        async def exploding(_envelope):  # noqa: RUF029
            raise RuntimeError("boom")

        registry = JobRegistry()
        registry.register(
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=exploding,
            )
        )
        with pytest.raises(RuntimeError, match="boom"):
            asyncio.run(registry.execute(envelope().model_dump(mode="json")))

    def test_handler_must_return_operation_result(self):
        async def wrong(_envelope):  # noqa: RUF029
            return {"status": "success"}

        registry = JobRegistry()
        registry.register(
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=wrong,  # type: ignore[arg-type]
            )
        )
        with pytest.raises(JobExecutionError, match="OperationResult"):
            asyncio.run(registry.execute(envelope().model_dump(mode="json")))

    def test_cancellation_propagates(self):
        from waxprep.errors.taxonomy import CancellationError

        async def cancelled(_envelope):  # noqa: RUF029
            raise CancellationError()

        registry = JobRegistry()
        registry.register(
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=cancelled,
            )
        )
        with pytest.raises(CancellationError):
            asyncio.run(registry.execute(envelope().model_dump(mode="json")))

    def test_asyncio_cancellation_propagates(self):
        async def cancelled(_envelope):  # noqa: RUF029
            raise asyncio.CancelledError

        registry = JobRegistry()
        registry.register(
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=cancelled,
            )
        )
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(registry.execute(envelope().model_dump(mode="json")))
