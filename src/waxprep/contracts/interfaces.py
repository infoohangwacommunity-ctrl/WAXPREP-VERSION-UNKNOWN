"""Typed component capability protocols (Stage 17).

These are *generic* communication capabilities, not concrete Tutor, Judge or
Notebook interfaces. They deliberately do not duplicate the existing
``core.protocols`` or registry protocols, which remain authoritative for their
current boundaries. When a real component adopts a typed contract, it declares
the concrete parameter types here.

Protocols describe capabilities only. Runtime data validation belongs to
``ContractModel`` and ``validate_contract``; a structural ``isinstance`` check
is not proof that payload bytes are valid.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from waxprep.contracts.envelopes import MessageEnvelope
from waxprep.contracts.models.base import ContractModel, ContractRootModel


@runtime_checkable
class RequestHandler[
    RequestT: ContractModel | ContractRootModel[Any],
    ResponseT: ContractModel | ContractRootModel[Any],
](Protocol):
    """Handle one typed request and return one typed response."""

    async def handle(self, request: RequestT) -> ResponseT: ...


@runtime_checkable
class CommandHandler[
    CommandT: ContractModel | ContractRootModel[Any],
    ResultT: ContractModel | ContractRootModel[Any],
](Protocol):
    """Execute one typed command (an imperative request to change state)."""

    async def execute(self, command: CommandT) -> ResultT: ...


@runtime_checkable
class EventPublisher[EventT: ContractModel | ContractRootModel[Any]](Protocol):
    """Publish one typed event about something that already happened."""

    async def publish(self, event: MessageEnvelope[EventT]) -> None: ...


@runtime_checkable
class StreamingHandler[
    RequestT: ContractModel | ContractRootModel[Any],
    ChunkT: ContractModel | ContractRootModel[Any],
](Protocol):
    """Return an ordered stream of typed chunks for one request."""

    def stream(self, request: RequestT) -> AsyncIterator[ChunkT]: ...
