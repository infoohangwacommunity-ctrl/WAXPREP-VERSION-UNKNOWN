"""
Test Core Protocols - Stage 03
Verify Message, MessageHandler, and ContextProvider protocols are
runtime_checkable and that concrete implementations satisfy isinstance checks.
"""

from typing import Any

import pytest

from waxprep.core.protocols import ContextProvider, Message, MessageHandler

# ---------------------------------------------------------------------------
# Concrete implementations for testing
# ---------------------------------------------------------------------------

class ConcreteMessage:
    """Minimal concrete Message implementation."""
    def __init__(self, content: str, msg_id: str, metadata: dict[str, Any] | None = None):
        self._content = content
        self._id = msg_id
        self._metadata = metadata or {}

    def get_content(self) -> str:
        return self._content

    def get_metadata(self) -> dict[str, Any]:
        return self._metadata

    def get_id(self) -> str:
        return self._id


class ConcreteMessageHandler:
    """Minimal concrete MessageHandler implementation."""
    def __init__(self, accepted_prefix: str = ""):
        self._prefix = accepted_prefix

    def can_handle(self, message: Message) -> bool:
        return message.get_content().startswith(self._prefix)

    async def handle(self, message: Message) -> Any:
        return {"handled": message.get_id(), "content": message.get_content()}


class ConcreteContextProvider:
    """Minimal concrete ContextProvider implementation."""
    def __init__(self, initial: dict[str, Any] | None = None):
        self._store: dict[str, Any] = initial or {}

    def get_context(self, **kwargs: Any) -> dict[str, Any]:
        result = dict(self._store)
        result.update(kwargs)
        return result


# ---------------------------------------------------------------------------
# Message protocol tests
# ---------------------------------------------------------------------------

class TestMessageProtocol:
    def test_is_runtime_checkable(self):
        assert isinstance(ConcreteMessage("hello", "msg-1"), Message)

    def test_is_not_runtime_checkable_when_missing_method(self):
        class BadMessage:
            def get_content(self) -> str:
                return "x"
            # missing get_metadata and get_id

        assert not isinstance(BadMessage(), Message)

    def test_get_content_returns_str(self):
        msg = ConcreteMessage("student question", "q-1")
        assert msg.get_content() == "student question"
        assert isinstance(msg.get_content(), str)

    def test_get_metadata_returns_dict(self):
        msg = ConcreteMessage("data", "d-1", metadata={"source": "user"})
        assert msg.get_metadata() == {"source": "user"}
        assert isinstance(msg.get_metadata(), dict)

    def test_get_metadata_default_empty(self):
        msg = ConcreteMessage("plain", "p-1")
        assert msg.get_metadata() == {}

    def test_get_id_returns_str(self):
        msg = ConcreteMessage("content", "unique-id-42")
        assert msg.get_id() == "unique-id-42"
        assert isinstance(msg.get_id(), str)

    def test_multiple_messages_independent(self):
        m1 = ConcreteMessage("first", "id-1")
        m2 = ConcreteMessage("second", "id-2", metadata={"tag": "math"})
        assert m1.get_id() != m2.get_id()
        assert m1.get_content() != m2.get_content()
        assert m2.get_metadata() == {"tag": "math"}


# ---------------------------------------------------------------------------
# MessageHandler protocol tests
# ---------------------------------------------------------------------------

class TestMessageHandlerProtocol:
    def test_is_runtime_checkable(self):
        handler = ConcreteMessageHandler("user:")
        assert isinstance(handler, MessageHandler)

    def test_is_not_runtime_checkable_when_missing_method(self):
        class BadHandler:
            async def handle(self, message: Message) -> Any:
                return None

        assert not isinstance(BadHandler(), MessageHandler)

    def test_can_handle_returns_true_when_prefix_matches(self):
        handler = ConcreteMessageHandler("user:")
        msg = ConcreteMessage("user: hello", "msg-1")
        assert handler.can_handle(msg) is True

    def test_can_handle_returns_false_when_prefix_does_not_match(self):
        handler = ConcreteMessageHandler("sys:")
        msg = ConcreteMessage("user: hello", "msg-1")
        assert handler.can_handle(msg) is False

    def test_can_handle_with_empty_prefix(self):
        handler = ConcreteMessageHandler("")
        msg = ConcreteMessage("anything", "msg-1")
        assert handler.can_handle(msg) is True

    @pytest.mark.asyncio
    async def test_handle_returns_result(self):
        handler = ConcreteMessageHandler("user:")
        msg = ConcreteMessage("user: hello", "msg-1")
        result = await handler.handle(msg)
        assert result == {"handled": "msg-1", "content": "user: hello"}

    @pytest.mark.asyncio
    async def test_handle_with_different_messages(self):
        handler = ConcreteMessageHandler("bot:")
        msg = ConcreteMessage("bot: response", "bot-msg")
        result = await handler.handle(msg)
        assert result["handled"] == "bot-msg"


# ---------------------------------------------------------------------------
# ContextProvider protocol tests
# ---------------------------------------------------------------------------

class TestContextProviderProtocol:
    def test_is_runtime_checkable(self):
        provider = ConcreteContextProvider({"user": "alice"})
        assert isinstance(provider, ContextProvider)

    def test_is_not_runtime_checkable_when_missing_method(self):
        class NoMethods:
            pass

        assert not isinstance(NoMethods(), ContextProvider)

    def test_get_context_returns_dict(self):
        provider = ConcreteContextProvider({"session": "abc"})
        ctx = provider.get_context()
        assert isinstance(ctx, dict)
        assert ctx == {"session": "abc"}

    def test_get_context_with_kwargs_merges(self):
        provider = ConcreteContextProvider({"base": "value"})
        ctx = provider.get_context(extra="data", msg_id="123")
        assert ctx == {"base": "value", "extra": "data", "msg_id": "123"}

    def test_get_context_empty_store(self):
        provider = ConcreteContextProvider()
        ctx = provider.get_context()
        assert ctx == {}

    def test_get_context_kwargs_only(self):
        provider = ConcreteContextProvider()
        ctx = provider.get_context(foo="bar")
        assert ctx == {"foo": "bar"}

    def test_multiple_providers_independent(self):
        p1 = ConcreteContextProvider({"a": 1})
        p2 = ConcreteContextProvider({"b": 2})
        assert p1.get_context() == {"a": 1}
        assert p2.get_context() == {"b": 2}
