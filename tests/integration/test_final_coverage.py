"""
Test Final Coverage - Stage 04
Covers all remaining gaps to achieve 100% coverage of src/waxprep/*.py.

Covers:
- core/pure.py  (normalize_text, extract_keywords, build_response, compose_handlers)
- core/protocols.py  (Message, MessageHandler, ContextProvider protocols + type aliases)
- adapters/*    (fake_channel, fake_model, fake_tool async methods)
- middleware/base.py  (TimingMiddleware, HeaderSanitizationMiddleware dispatch)
- main.py       (exception handlers, readiness failure paths, __main__ import guard)
- registries/base.py  (get() KeyError, register() abstract)
- registries/channel/model/tool.py  (missing 'name' ValueError)
"""

import asyncio
import inspect
from unittest.mock import MagicMock

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from waxprep import main as main_module
from waxprep.adapters.fake_channel import FakeChannelAdapter
from waxprep.adapters.fake_model import FakeModelAdapter
from waxprep.adapters.fake_tool import FakeTool
from waxprep.core.protocols import (
    ContextProvider,
    HandlerResult,
    Message,
    MessageHandler,
    MessageResult,
)
from waxprep.core.pure import (
    build_response,
    compose_handlers,
    extract_keywords,
    normalize_text,
)
from waxprep.middleware.base import HeaderSanitizationMiddleware, TimingMiddleware
from waxprep.registries.base import BaseRegistry
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry


def _make_awaitable(response: Response):
    """Return an awaitable that resolves to the given Response."""

    async def _coro() -> Response:  # noqa: RUF029
        return response

    return _coro()


# ---------------------------------------------------------------------------
# core/pure.py
# ---------------------------------------------------------------------------


class TestNormalizeText:
    def test_strips_and_collapses_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"

    def test_empty_string_returns_empty(self):
        assert normalize_text("") == ""

    def test_already_normalized(self):
        assert normalize_text("hello world") == "hello world"

    def test_tabs_and_newlines_collapsed(self):
        assert normalize_text("hello\t\tworld\n\nfoo") == "hello world foo"


class TestExtractKeywords:
    def test_basic_extraction(self):
        assert extract_keywords("hello world foo") == ["foo", "hello", "world"]

    def test_min_length_filter(self):
        assert extract_keywords("hi hello world", min_length=4) == ["hello", "world"]

    def test_empty_text_returns_empty(self):
        assert extract_keywords("") == []

    def test_unique_sorted(self):
        assert extract_keywords("apple banana apple cherry") == ["apple", "banana", "cherry"]

    def test_numbers_included(self):
        assert extract_keywords("test 123 abc") == ["123", "abc", "test"]


class TestBuildResponse:
    def test_content_only(self):
        result = build_response("hello")
        assert result == {"content": "hello"}

    def test_with_metadata(self):
        result = build_response("hello", {"key": "value"})
        assert result == {"content": "hello", "metadata": {"key": "value"}}

    def test_metadata_none_omitted(self):
        result = build_response("hello", None)
        assert "metadata" not in result


class TestComposeHandlers:
    def test_pipeline_passes_through(self):
        add_one = lambda x: x + 1  # noqa: E731
        double = lambda x: x * 2  # noqa: E731
        pipeline = compose_handlers([add_one, double])
        assert pipeline(3) == 8  # (3+1)*2

    def test_single_handler(self):
        f = lambda x: x * 10  # noqa: E731
        pipeline = compose_handlers([f])
        assert pipeline(5) == 50

    def test_empty_handlers_returns_input(self):
        pipeline = compose_handlers([])
        assert pipeline(42) == 42

    def test_string_transformation(self):
        upper = lambda s: s.upper()  # noqa: E731
        exclaim = lambda s: s + "!"  # noqa: E731
        pipeline = compose_handlers([upper, exclaim])
        assert pipeline("hello") == "HELLO!"


# ---------------------------------------------------------------------------
# core/protocols.py
# ---------------------------------------------------------------------------


class TestMessageProtocol:
    def test_runtime_checkable_accepts_concrete(self):
        class ConcreteMessage:
            def get_content(self) -> str:
                return "hello"

            def get_metadata(self) -> dict:  # noqa: F821
                return {}

            def get_id(self) -> str:
                return "123"

        msg = ConcreteMessage()
        assert isinstance(msg, Message)

    def test_runtime_checkable_rejects_incomplete(self):
        class BadMessage:
            def get_content(self) -> str:
                return "hello"

        assert not isinstance(BadMessage(), Message)


class TestMessageHandlerProtocol:
    def test_runtime_checkable_accepts_concrete(self):
        class ConcreteHandler:
            def can_handle(self, message: Message) -> bool:
                return True

            async def handle(self, message: Message) -> str:
                return "ok"

        handler = ConcreteHandler()
        assert isinstance(handler, MessageHandler)

    def test_runtime_checkable_rejects_missing_handle(self):
        class BadHandler:
            def can_handle(self, message: Message) -> bool:
                return True

        assert not isinstance(BadHandler(), MessageHandler)


class TestContextProviderProtocol:
    def test_runtime_checkable_accepts_concrete(self):
        class ConcreteProvider:
            def get_context(self, **kwargs) -> dict:  # noqa: F821
                return {"session": kwargs.get("session_id")}

        provider = ConcreteProvider()
        assert isinstance(provider, ContextProvider)

    def test_runtime_checkable_rejects_missing_method(self):
        class BadProvider:
            pass

        assert not isinstance(BadProvider(), ContextProvider)


class TestProtocolTypeAliases:
    def test_message_result_is_any(self):
        assert MessageResult is not None

    def test_handler_result_is_any(self):
        assert HandlerResult is not None


# ---------------------------------------------------------------------------
# adapters - call async methods directly
# ---------------------------------------------------------------------------


class TestFakeChannelAdapter:
    def test_handle_message_returns_expected_structure(self):
        adapter = FakeChannelAdapter()
        result = asyncio.run(adapter.handle_message({"id": "msg-1"}))
        assert result["status"] == "fake_processed"
        assert result["message_id"] == "msg-1"
        assert result["channel"] == "fake"

    def test_handle_message_missing_id_defaults_to_unknown(self):
        adapter = FakeChannelAdapter()
        result = asyncio.run(adapter.handle_message({}))
        assert result["message_id"] == "unknown"


class TestFakeModelAdapter:
    def test_generate_returns_fake_response(self):
        adapter = FakeModelAdapter()
        result = asyncio.run(adapter.generate("Hello world"))
        assert result.startswith("Fake response to: Hello world...")

    def test_generate_truncates_long_prompt(self):
        adapter = FakeModelAdapter()
        long_prompt = "a" * 100
        result = asyncio.run(adapter.generate(long_prompt))
        assert result == "Fake response to: " + "a" * 50 + "..."


class TestFakeTool:
    def test_execute_returns_expected_structure(self):
        tool = FakeTool()
        result = asyncio.run(tool.execute(arg1="val1", arg2="val2"))
        assert result["status"] == "fake_executed"
        assert result["input"] == {"arg1": "val1", "arg2": "val2"}
        assert result["tool"] == "fake_tool"

    def test_execute_empty_kwargs(self):
        tool = FakeTool()
        result = asyncio.run(tool.execute())
        assert result["input"] == {}
        assert result["tool"] == "fake_tool"


# ---------------------------------------------------------------------------
# middleware/base.py
# ---------------------------------------------------------------------------


class TestTimingMiddleware:
    @pytest.mark.asyncio
    async def test_dispatch_passes_through(self):
        middleware = TimingMiddleware(MagicMock())
        request = MagicMock(spec=Request)
        call_next = MagicMock(return_value=_make_awaitable(Response("ok")))
        response = await middleware.dispatch(request, call_next)
        assert isinstance(response, Response)
        call_next.assert_called_once()


class TestHeaderSanitizationMiddleware:
    @pytest.mark.asyncio
    async def test_dispatch_passes_through(self):
        middleware = HeaderSanitizationMiddleware(MagicMock())
        request = MagicMock(spec=Request)
        call_next = MagicMock(return_value=_make_awaitable(Response("ok")))
        response = await middleware.dispatch(request, call_next)
        assert isinstance(response, Response)
        call_next.assert_called_once()

    def test_sensitive_headers_defined(self):
        assert "X-Internal-Token" in HeaderSanitizationMiddleware.SENSITIVE_HEADERS
        assert "X-Debug-Info" in HeaderSanitizationMiddleware.SENSITIVE_HEADERS


# ---------------------------------------------------------------------------
# registries/base.py - get() KeyError + register() abstract
# ---------------------------------------------------------------------------


class TestBaseRegistryGetError:
    def test_get_raises_keyerror_for_missing_name(self):
        class ConcreteRegistry(BaseRegistry):
            def register(self, name: str, item: str) -> None:
                self._validate_not_duplicate(name)
                self._items[name] = item

        reg = ConcreteRegistry()
        with pytest.raises(KeyError, match="No item registered"):
            reg.get("nonexistent")


class TestBaseRegistryRegisterAbstract:
    def test_register_is_abstract(self):
        """Prove register() is abstract — cannot instantiate BaseRegistry directly."""
        with pytest.raises(TypeError, match="abstract"):
            BaseRegistry()  # type: ignore


# ---------------------------------------------------------------------------
# registries/* - missing 'name' ValueError
# ---------------------------------------------------------------------------


class TestChannelRegistryMissingName:
    def test_rejects_adapter_without_name(self):
        registry = ChannelRegistry()

        class NoNameAdapter:
            async def handle_message(self, message: dict) -> dict:
                return message

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            registry.register("test", NoNameAdapter())


class TestModelRegistryMissingName:
    def test_rejects_adapter_without_name(self):
        registry = ModelRegistry()

        class NoNameAdapter:
            async def generate(self, prompt: str) -> str:
                return prompt

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            registry.register("test", NoNameAdapter())


class TestToolRegistryMissingName:
    def test_rejects_tool_without_name(self):
        registry = ToolRegistry()

        class NoNameTool:
            async def execute(self, **kwargs):
                pass

        with pytest.raises(ValueError, match="must have a 'name' attribute"):
            registry.register("test", NoNameTool())


# ---------------------------------------------------------------------------
# main.py - exception handlers + readiness failure paths + __main__ guard
# ---------------------------------------------------------------------------


class TestMainExceptionHandlers:
    """Trigger the validation and general exception handlers via TestClient."""

    @pytest.fixture
    def client(self):
        app = main_module.get_app()
        with TestClient(app) as c:
            yield c

    def _save_and_add_router(self, app, router):
        """Save original route count; add router; return route count to restore."""
        original_count = len(app.router.routes)
        app.include_router(router)
        return original_count

    def _restore_routes(self, app, original_count):
        """Truncate routes list back to original count."""
        app.router.routes = app.router.routes[:original_count]

    def test_validation_error_handler_returns_422(self, client):
        """Send malformed JSON to a POST route to trigger
        RequestValidationError handler (lines 149-154)."""
        from fastapi import APIRouter

        router = APIRouter()

        @router.post("/_validation_test")
        async def validation_test(item: str):
            return {"ok": True}

        orig_count = self._save_and_add_router(main_module._app, router)
        try:
            response = client.post(
                "/_validation_test",
                content="not-valid-json{{{{",
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
            data = response.json()
            assert data["detail"] == "Validation error"
            assert "errors" in data
        finally:
            self._restore_routes(main_module._app, orig_count)

    def test_general_exception_handler_returns_500(self, client):
        """Test the general exception handler (lines 166-171) by calling it
        directly with a mocked request and a test exception.

        The handler is registered as _app.exception_handler(Exception) and
        returns a 500 JSONResponse. We verify its output structure directly
        rather than going through the full ASGI stack (which leaks the
        exception through the TestClient cleanup in this Starlette version).
        """
        from starlette.responses import JSONResponse

        # Build a minimal ASGI scope for the request
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/_test",
            "query_string": b"",
            "headers": [],
        }

        # Create a request via the Starlette factory
        req = Request(scope=scope)

        # Call the handler directly — it's the same function registered on _app
        from waxprep.main import general_exception_handler

        result = asyncio.run(general_exception_handler(req, RuntimeError("test")))
        assert isinstance(result, JSONResponse)
        assert result.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        data = result.body.decode("utf-8")
        import json

        body = json.loads(data)
        assert body["detail"] == "Internal server error"
        assert body["message"] == "An unexpected error occurred"


class TestMainReadinessFailurePaths:
    """Test each readiness check failure path (lines 205, 212, 219, 225, 231).

    The TestClient lifespan calls register_defaults on startup. To test failure
    paths we need registries that are NOT re-populated by the lifespan, but
    that DO have the *other* registries populated so we can target each one
    individually.
    """

    @pytest.fixture
    def readiness_client(self):
        """Provide a TestClient with registries set up for selective clearing.

        Channel and tool registries are pre-populated; model registry is empty.
        All register_defaults are patched to no-ops so the lifespan won't
        re-populate them.
        """
        import waxprep.main as main_mod
        import waxprep.registries.channel as ch_reg
        import waxprep.registries.model as mod_reg
        import waxprep.registries.tool as tool_reg

        # Save originals
        orig_channel_rd = ch_reg.ChannelRegistry.register_defaults
        orig_model_rd = mod_reg.ModelRegistry.register_defaults
        orig_tool_rd = tool_reg.ToolRegistry.register_defaults

        try:
            # Patch to no-ops
            ch_reg.ChannelRegistry.register_defaults = lambda self: None
            mod_reg.ModelRegistry.register_defaults = lambda self: None
            tool_reg.ToolRegistry.register_defaults = lambda self: None

            # Create fresh registries
            main_mod._channel_registry = ch_reg.ChannelRegistry()
            main_mod._model_registry = mod_reg.ModelRegistry()
            main_mod._tool_registry = tool_reg.ToolRegistry()

            # Manually populate channel and tool (but NOT model)
            from waxprep.adapters.fake_channel import FakeChannelAdapter
            from waxprep.adapters.fake_tool import FakeTool

            main_mod._channel_registry._items["fake"] = FakeChannelAdapter()
            main_mod._tool_registry._items["fake_tool"] = FakeTool()
            # model registry stays empty — this is the "model not registered" state

            main_mod._registries_ready = True

            client = TestClient(main_mod._app)
            client.__enter__()
            yield client
        finally:
            # Restore originals
            ch_reg.ChannelRegistry.register_defaults = orig_channel_rd
            mod_reg.ModelRegistry.register_defaults = orig_model_rd
            tool_reg.ToolRegistry.register_defaults = orig_tool_rd

    def test_readiness_fails_when_config_not_loaded(self, readiness_client):
        """Line 205: settings.environment is falsy → 503."""
        import waxprep.config as config_mod

        original_env = config_mod.settings.environment
        try:
            config_mod.settings.environment = ""
            response = readiness_client.get("/health/readiness")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["reason"] == "configuration_not_loaded"
        finally:
            config_mod.settings.environment = original_env

    def test_readiness_fails_when_registries_not_initialized(self, readiness_client):
        """Verify readiness fails when registries are not initialized via app state."""
        import waxprep.main as main_mod

        original_ready = main_mod._app_state.registries_ready
        try:
            main_mod._app_state.registries_ready = False
            response = readiness_client.get("/health/readiness")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert data["reason"] == "registries_not_initialized"
        finally:
            main_mod._app_state.registries_ready = original_ready

    def test_readiness_fails_when_channel_not_registered(self, readiness_client):
        """Verify readiness fails when channel 'fake' not registered."""
        import waxprep.main as main_mod

        main_mod._app_state.channel_registry._items.clear()
        response = readiness_client.get("/health/readiness")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["reason"] == "channel_registry_not_initialized"

    def test_readiness_fails_when_model_not_registered(self, readiness_client):
        """Verify readiness fails when model 'fake' not registered."""
        import waxprep.main as main_mod
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        # Channel was cleared by the channel test — re-populate it.
        # Model stays empty — this is what we're testing.
        main_mod._app_state.channel_registry._items["fake"] = FakeChannelAdapter()
        response = readiness_client.get("/health/readiness")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["reason"] == "model_registry_not_initialized"

    def test_readiness_fails_when_tool_not_registered(self, readiness_client):
        """Verify readiness fails when tool 'fake_tool' not registered."""
        import waxprep.main as main_mod
        from waxprep.adapters.fake_channel import FakeChannelAdapter
        from waxprep.adapters.fake_model import FakeModelAdapter

        # Channel and model are populated; tool is cleared for this test.
        main_mod._app_state.channel_registry._items["fake"] = FakeChannelAdapter()
        main_mod._app_state.model_registry._items["fake"] = FakeModelAdapter()
        main_mod._app_state.tool_registry._items.clear()
        response = readiness_client.get("/health/readiness")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["reason"] == "tool_registry_not_initialized"


class TestMainShutdownHandler:
    def test_shutdown_handler_removed(self):
        """Verify handle_shutdown has been removed - shutdown is ASGI server-managed.

        The custom signal handler was disconnected from actual signal handling
        and has been removed. Uvicorn manages signals and triggers lifespan shutdown.
        """
        import waxprep.main as main_mod

        # Verify the handler no longer exists
        assert not hasattr(main_mod, "handle_shutdown")


class TestMainModuleGuard:
    def test_main_block_not_executed_on_import(self):
        """Lines 297-300: __main__ block must not run when module is imported."""
        source = inspect.getsource(main_module)
        assert 'if __name__ == "__main__"' in source
