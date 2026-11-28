"""Stage 17 — generic capability Protocol compliance."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from waxprep.contracts.envelopes import MessageEnvelope, MessageKind
from waxprep.contracts.interfaces import (
    CommandHandler,
    EventPublisher,
    RequestHandler,
    StreamingHandler,
)
from waxprep.contracts.models.result import OperationResult, OperationSuccess

pytestmark = pytest.mark.contract


class SuccessHandler:
    async def handle(self, request: OperationSuccess) -> OperationSuccess:  # noqa: ARG002
        return OperationSuccess(detail="handled")


class SuccessCommand:
    async def execute(self, command: OperationSuccess) -> OperationSuccess:  # noqa: ARG002
        return OperationSuccess(detail="executed")


class SuccessPublisher:
    def __init__(self) -> None:
        self.published: list[MessageEnvelope[OperationResult]] = []

    async def publish(self, event: MessageEnvelope[OperationResult]) -> None:
        self.published.append(event)


class ChunkStream:
    async def stream(self, request: OperationSuccess) -> AsyncIterator[OperationSuccess]:  # noqa: ARG002
        for index in range(2):
            yield OperationSuccess(detail=str(index))


class MissingEverything:
    pass


def envelope() -> MessageEnvelope[OperationResult]:
    return MessageEnvelope[OperationResult](
        message_id=uuid4(),
        message_kind=MessageKind.EVENT,
        message_type="waxprep.operation.result",
        contract_version="1.0.0",
        correlation_id=uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        producer="waxprep.test",
        payload=OperationResult(OperationSuccess(detail="event")),
    )


@pytest.mark.asyncio
class TestProtocolCompliance:
    async def test_request_handler(self):
        handler = SuccessHandler()
        assert isinstance(handler, RequestHandler)
        assert (await handler.handle(OperationSuccess())).detail == "handled"

    async def test_command_handler(self):
        handler = SuccessCommand()
        assert isinstance(handler, CommandHandler)
        assert (await handler.execute(OperationSuccess())).detail == "executed"

    async def test_event_publisher(self):
        publisher = SuccessPublisher()
        assert isinstance(publisher, EventPublisher)
        event = envelope()
        await publisher.publish(event)
        assert publisher.published == [event]

    async def test_streaming_handler(self):
        handler = ChunkStream()
        assert isinstance(handler, StreamingHandler)
        chunks = [chunk async for chunk in handler.stream(OperationSuccess())]
        assert [chunk.detail for chunk in chunks] == ["0", "1"]

    async def test_missing_methods_are_not_compliant(self):
        assert not isinstance(MissingEverything(), RequestHandler)
        assert not isinstance(MissingEverything(), CommandHandler)
        assert not isinstance(MissingEverything(), EventPublisher)
        assert not isinstance(MissingEverything(), StreamingHandler)
