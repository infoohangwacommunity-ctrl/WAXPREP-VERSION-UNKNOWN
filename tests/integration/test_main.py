"""
Tests for main.py - Stage 02

Proves ASGI app works, health endpoints work, graceful shutdown works,
exception handlers log correctly, readiness fails gracefully, and the
__main__ block delegates to uvicorn.run.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from waxprep.main import get_app

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    app = get_app()
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Original tests (kept from the existing file)
# ---------------------------------------------------------------------------


class TestHealthEndpoints:
    """Prove health endpoints work and distinguish liveness from readiness."""

    @pytest.mark.integration
    def test_liveness_endpoint(self, client):
        """Prove liveness endpoint returns alive status."""
        response = client.get("/health/liveness")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    @pytest.mark.integration
    def test_readiness_endpoint(self, client):
        """Prove readiness endpoint returns ready status."""
        response = client.get("/health/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "checks" in data

    @pytest.mark.integration
    def test_liveness_not_equal_readiness(self, client):
        """Prove liveness != readiness conceptually."""
        liveness = client.get("/health/liveness")
        readiness = client.get("/health/readiness")
        assert liveness.status_code == 200
        assert readiness.status_code == 200
        assert liveness.json()["status"] == "alive"
        assert readiness.json()["status"] == "ready"


class TestRootEndpoint:
    """Prove root endpoint works."""

    @pytest.mark.integration
    def test_root_endpoint(self, client):
        """Prove root endpoint returns foundation info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "WaxPrep Foundation"
        assert data["version"] == "0.1.0"
        assert data["status"] == "running"


# ---------------------------------------------------------------------------
# Lines 149-154: validation_exception_handler
# ---------------------------------------------------------------------------


class TestValidationExceptionHandler:
    """Prove validation_exception_handler logs at WARNING level (lines 149-154)."""

    @pytest.mark.integration
    def test_validation_error_logs_warning(self, client):
        """Malformed JSON body on a Pydantic-validated route → warning log."""
        from pydantic import BaseModel

        class _TestBody(BaseModel):
            name: str

        async def _endpoint(body: _TestBody):  # noqa: RUF029
            return body

        get_app().add_api_route(
            "/_test-validation",
            _endpoint,
            methods=["POST"],
            response_model=None,
            status_code=200,
        )

        with patch("waxprep.main.logger") as mock_logger:
            response = client.post(
                "/_test-validation",
                content="not-json",
                headers={"Content-Type": "application/json"},
            )
            assert response.status_code == 422
            mock_logger.warning.assert_called_once()
            kwargs = mock_logger.warning.call_args.kwargs
            # The log carries the matched route template (or a fixed safe
            # label), never a raw request path.
            assert "path" not in kwargs
            assert kwargs["route"] in {"/_test-validation", "unmatched"}
            assert kwargs["error_count"] >= 1


# ---------------------------------------------------------------------------
# Lines 166-171: general_exception_handler
# ---------------------------------------------------------------------------


class TestGeneralExceptionHandler:
    """Prove general_exception_handler logs at EXCEPTION level (lines 166-171)."""

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_unhandled_exception_logs_exception(self):
        """Call the handler directly: unhandled Exception → logger.exception."""
        from waxprep.main import general_exception_handler

        async def _receive():  # noqa: RUF029
            return {"type": "http.request"}

        async def _send(_message):
            pass

        request = Request(
            scope={
                "type": "http",
                "method": "GET",
                "path": "/_test-error",
                "query_string": b"",
                "headers": [],
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("testclient", 12345),
            },
            receive=_receive,
            send=_send,
        )

        with patch("waxprep.main.logger") as mock_logger:
            response = await general_exception_handler(request, ZeroDivisionError("test"))
            assert response.status_code == 500
            mock_logger.exception.assert_called_once()
            kwargs = mock_logger.exception.call_args.kwargs
            # No matched route in this synthetic scope: the safe fallback is
            # used instead of the raw path.
            assert "path" not in kwargs
            assert kwargs["route"] == "unmatched"
            assert kwargs["exc_type"] == "ZeroDivisionError"


# ---------------------------------------------------------------------------
# Lines 205, 212, 219, 225, 231: readiness error paths
# ---------------------------------------------------------------------------


class TestReadinessErrorPaths:
    """Prove readiness endpoint fails gracefully when preconditions are not met."""

    @pytest.mark.integration
    def test_readiness_fails_when_environment_not_loaded(self, client):
        """Line 205: settings.environment falsy → 503 configuration_not_loaded."""
        with patch("waxprep.main.settings") as mock_settings:
            mock_settings.environment = ""
            response = client.get("/health/readiness")
        assert response.status_code == 503
        assert response.json()["reason"] == "configuration_not_loaded"

    @pytest.mark.integration
    def test_readiness_fails_when_registries_not_ready(self, client):
        """Verify readiness fails when registries are not ready via app state."""
        import waxprep.main as main_mod

        original = main_mod._app_state.registries_ready
        try:
            main_mod._app_state.registries_ready = False
            response = client.get("/health/readiness")
            assert response.status_code == 503
            assert response.json()["reason"] == "registries_not_initialized"
        finally:
            main_mod._app_state.registries_ready = original

    @pytest.mark.integration
    def test_readiness_fails_when_channel_registry_empty(self, client):
        """Verify readiness fails when channel registry is empty via app state."""
        import waxprep.main as main_mod
        from waxprep.registries.channel import ChannelRegistry

        channel_registry = ChannelRegistry()
        # Don't register defaults - should fail

        original_ready = main_mod._app_state.registries_ready
        original_channel = main_mod._app_state.channel_registry
        try:
            main_mod._app_state.registries_ready = True
            main_mod._app_state.channel_registry = channel_registry
            response = client.get("/health/readiness")
            assert response.status_code == 503
            assert response.json()["reason"] == "channel_registry_not_initialized"
        finally:
            main_mod._app_state.registries_ready = original_ready
            main_mod._app_state.channel_registry = original_channel

    @pytest.mark.integration
    def test_readiness_fails_when_model_registry_empty(self, client):
        """Verify readiness fails when model registry is empty via app state."""
        import waxprep.main as main_mod
        from waxprep.registries.channel import ChannelRegistry

        channel_registry = ChannelRegistry()
        channel_registry.register_defaults()  # registers "fake"

        original_ready = main_mod._app_state.registries_ready
        original_channel = main_mod._app_state.channel_registry
        original_model = main_mod._app_state.model_registry
        try:
            main_mod._app_state.registries_ready = True
            main_mod._app_state.channel_registry = channel_registry
            main_mod._app_state.model_registry = None
            response = client.get("/health/readiness")
            assert response.status_code == 503
            assert response.json()["reason"] == "model_registry_not_initialized"
        finally:
            main_mod._app_state.registries_ready = original_ready
            main_mod._app_state.channel_registry = original_channel
            main_mod._app_state.model_registry = original_model

    @pytest.mark.integration
    def test_readiness_fails_when_tool_registry_empty(self, client):
        """Verify readiness fails when tool registry is empty via app state."""
        import waxprep.main as main_mod
        from waxprep.registries.channel import ChannelRegistry
        from waxprep.registries.model import ModelRegistry

        channel_registry = ChannelRegistry()
        channel_registry.register_defaults()
        model_registry = ModelRegistry()
        model_registry.register_defaults()

        original_ready = main_mod._app_state.registries_ready
        original_channel = main_mod._app_state.channel_registry
        original_model = main_mod._app_state.model_registry
        original_tool = main_mod._app_state.tool_registry
        try:
            main_mod._app_state.registries_ready = True
            main_mod._app_state.channel_registry = channel_registry
            main_mod._app_state.model_registry = model_registry
            main_mod._app_state.tool_registry = None
            response = client.get("/health/readiness")
            assert response.status_code == 503
            assert response.json()["reason"] == "tool_registry_not_initialized"
        finally:
            main_mod._app_state.registries_ready = original_ready
            main_mod._app_state.channel_registry = original_channel
            main_mod._app_state.model_registry = original_model
            main_mod._app_state.tool_registry = original_tool


# ---------------------------------------------------------------------------
# Lines 297-300: __main__ block
# ---------------------------------------------------------------------------


class TestMainBlock:
    """Prove the __main__ block calls uvicorn.run with correct arguments."""

    @pytest.mark.integration
    def test_main_block_calls_uvicorn_run(self):
        """Executing main.py as __main__ delegates to uvicorn.run correctly."""
        import waxprep.main as main

        # Reset any lifespan side-effects so the module globals are clean
        main._shutting_down = False
        main._registries_ready = False
        main._channel_registry = None
        main._model_registry = None
        main._tool_registry = None

        mock_run = MagicMock()
        fake_uvicorn = MagicMock(run=mock_run)

        with patch.dict(sys.modules, {"uvicorn": fake_uvicorn}):
            import runpy

            # run_path executes the file with __name__ == "__main__"
            runpy.run_path(main.__file__, run_name="__main__")

        # uvicorn.run is called with the ASGI app object as the first positional
        # arg so the validated settings — not uvicorn's CLI defaults — apply.
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert isinstance(args[0], FastAPI)
        assert kwargs["host"] == main.settings.host
        assert kwargs["port"] == main.settings.port
        assert kwargs["reload"] is False
        assert kwargs["log_config"] is None
        assert kwargs["interface"] == "asgi3"
