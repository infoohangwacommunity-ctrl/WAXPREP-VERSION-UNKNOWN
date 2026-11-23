"""
Test Foundation - Stages 02-03
Prove foundation stability: no import pollution, registry behavior, health endpoints, middleware.
"""

import pytest
from fastapi.testclient import TestClient

from waxprep.main import get_app
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry


class TestNoImportSideEffects:
    """Prove registries are NOT populated at import time."""

    @pytest.mark.integration
    def test_channel_registry_empty_at_import(self):
        """Prove channel registry is empty when created - no auto-registration."""
        registry = ChannelRegistry()
        assert len(registry.list_all()) == 0
        assert not registry.is_registered("fake")

    @pytest.mark.integration
    def test_model_registry_empty_at_import(self):
        """Prove model registry is empty when created - no auto-registration."""
        registry = ModelRegistry()
        assert len(registry.list_all()) == 0
        assert not registry.is_registered("fake")

    @pytest.mark.integration
    def test_tool_registry_empty_at_import(self):
        """Prove tool registry is empty when created - no auto-registration."""
        registry = ToolRegistry()
        assert len(registry.list_all()) == 0
        assert not registry.is_registered("fake_tool")

    @pytest.mark.integration
    def test_register_defaults_populates_channel_registry(self):
        """Prove explicit registration works for channel registry."""
        registry = ChannelRegistry()
        assert len(registry.list_all()) == 0

        registry.register_defaults()

        assert len(registry.list_all()) == 1
        assert registry.is_registered("fake")

    @pytest.mark.integration
    def test_register_defaults_populates_model_registry(self):
        """Prove explicit registration works for model registry."""
        registry = ModelRegistry()
        assert len(registry.list_all()) == 0

        registry.register_defaults()

        assert len(registry.list_all()) == 1
        assert registry.is_registered("fake")

    @pytest.mark.integration
    def test_register_defaults_populates_tool_registry(self):
        """Prove explicit registration works for tool registry."""
        registry = ToolRegistry()
        assert len(registry.list_all()) == 0

        registry.register_defaults()

        assert len(registry.list_all()) == 1
        assert registry.is_registered("fake_tool")


class TestAppCreation:
    """Prove app can be created and accessed."""

    @pytest.mark.integration
    def test_get_app_returns_fastapi_instance(self):
        """Prove get_app returns a FastAPI application."""
        app = get_app()
        assert app is not None
        assert app.title == "WaxPrep Foundation"
        assert app.version == "0.1.0"

    @pytest.mark.integration
    def test_app_has_expected_routes(self):
        """Prove app has expected routes."""
        app = get_app()
        routes = [route.path for route in app.routes]
        assert "/health/liveness" in routes
        assert "/health/readiness" in routes
        assert "/" in routes


class TestHealthEndpoints:
    """Prove health endpoints work correctly."""

    @pytest.fixture
    def client(self):
        app = get_app()
        with TestClient(app) as test_client:
            yield test_client

    @pytest.mark.integration
    def test_liveness_returns_alive(self, client):
        """Prove liveness endpoint returns alive status."""
        response = client.get("/health/liveness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"

    @pytest.mark.integration
    def test_readiness_returns_ready(self, client):
        """Prove readiness endpoint returns ready status after lifespan init."""
        response = client.get("/health/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        # Readiness should include checks
        assert "checks" in data

    @pytest.mark.integration
    def test_readiness_does_not_include_middleware_check(self, client):
        """Verify readiness does NOT report unverified middleware status.

        The middleware status was previously reported without independent
        verification. Now readiness only reports what the application can
        honestly verify.
        """
        response = client.get("/health/readiness")
        data = response.json()
        checks = data.get("checks", {})
        # Middleware status should not be included
        assert "correlation_id_middleware" not in checks

    @pytest.mark.integration
    def test_liveness_and_readiness_are_different_endpoints(self, client):
        """Prove liveness and readiness are distinct endpoints."""
        liveness = client.get("/health/liveness")
        readiness = client.get("/health/readiness")

        assert liveness.status_code == 200
        assert readiness.status_code == 200

        # Different response structures
        liveness_data = liveness.json()
        readiness_data = readiness.json()

        assert liveness_data["status"] == "alive"
        assert readiness_data["status"] == "ready"
        assert "checks" in readiness_data
        assert "checks" not in liveness_data


class TestCorrelationIdMiddleware:
    """Prove correlation ID middleware works."""

    @pytest.fixture
    def client(self):
        app = get_app()
        with TestClient(app) as test_client:
            yield test_client

    @pytest.mark.integration
    def test_response_includes_correlation_id_header(self, client):
        """Prove every response includes X-Request-ID header."""
        response = client.get("/")
        assert "X-Request-ID" in response.headers
        correlation_id = response.headers["X-Request-ID"]
        assert len(correlation_id) > 0

    @pytest.mark.integration
    def test_each_request_gets_unique_correlation_id(self, client):
        """Prove each request receives a different correlation ID."""
        response1 = client.get("/")
        response2 = client.get("/")

        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]

        assert id1 != id2  # Unique per request

    @pytest.mark.integration
    def test_correlation_id_propagated_to_health_endpoint(self, client):
        """Prove correlation ID is present on health endpoint responses."""
        response = client.get("/health/liveness")
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0


class TestRootEndpoint:
    """Prove root endpoint works."""

    @pytest.fixture
    def client(self):
        app = get_app()
        with TestClient(app) as test_client:
            yield test_client

    @pytest.mark.integration
    def test_root_returns_foundation_info(self, client):
        """Prove root endpoint returns foundation info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "WaxPrep Foundation"
        assert data["version"] == "0.1.0"
        assert data["status"] == "running"

    @pytest.mark.integration
    def test_root_includes_correlation_id(self, client):
        """Prove root endpoint response includes correlation ID header."""
        response = client.get("/")
        assert "X-Request-ID" in response.headers


class TestExceptionHandling:
    """Prove exception handlers don't leak internals."""

    @pytest.fixture
    def client(self):
        app = get_app()
        with TestClient(app) as test_client:
            yield test_client

    @pytest.mark.integration
    def test_unknown_route_returns_404(self, client):
        """Prove 404 returns clean JSON, not traceback."""
        response = client.get("/nonexistent/path")
        assert response.status_code == 404
        data = response.json()
        # Should have detail, NOT traceback
        assert "detail" in data
        assert "Traceback" not in str(data)
        assert "File" not in str(data)

    @pytest.mark.integration
    def test_404_includes_correlation_id(self, client):
        """Prove 404 responses include correlation ID."""
        response = client.get("/nonexistent")
        assert "X-Request-ID" in response.headers

    @pytest.mark.integration
    def test_invalid_correlation_id_rejected(self, client):
        """Prove invalid X-Request-ID values are replaced with generated UUIDs."""
        # Send an invalid request ID
        response = client.get("/", headers={"X-Request-ID": "not-a-valid-uuid"})
        assert "X-Request-ID" in response.headers
        # Should have generated a new valid UUID
        returned_id = response.headers["X-Request-ID"]
        import uuid

        try:
            uuid.UUID(returned_id)
        except ValueError:
            pytest.fail(f"Returned ID is not a valid UUID: {returned_id}")

    @pytest.mark.integration
    def test_valid_correlation_id_preserved(self, client):
        """Prove valid X-Request-ID values are preserved."""
        valid_uuid = "550e8400-e29b-41d4-a716-446655440000"
        response = client.get("/", headers={"X-Request-ID": valid_uuid})
        assert response.headers["X-Request-ID"] == valid_uuid

    @pytest.mark.integration
    def test_validate_request_id_rejects_none(self):
        """_validate_request_id must not crash on None — returns False."""
        from waxprep.middleware.request_id import _validate_request_id

        assert not _validate_request_id(None)

    @pytest.mark.integration
    def test_validate_request_id_rejects_integer(self):
        """_validate_request_id must not crash on non-string — returns False."""
        from waxprep.middleware.request_id import _validate_request_id

        assert not _validate_request_id(123)

    @pytest.mark.integration
    def test_validate_request_id_rejects_float(self):
        """_validate_request_id must not crash on float — returns False."""
        from waxprep.middleware.request_id import _validate_request_id

        assert not _validate_request_id(3.14)
