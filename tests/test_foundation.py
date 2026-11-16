"""
Test Foundation - Stage 02
Prove foundation stability: no import pollution, registry behavior, health endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from waxprep.main import get_app
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry


class TestNoImportSideEffects:
    """Prove registries are NOT populated at import time."""
    
    def test_channel_registry_empty_at_import(self):
        """Prove channel registry is empty when created - no auto-registration."""
        registry = ChannelRegistry()
        assert len(registry.list_all()) == 0
        assert not registry.is_registered("fake")
    
    def test_model_registry_empty_at_import(self):
        """Prove model registry is empty when created - no auto-registration."""
        registry = ModelRegistry()
        assert len(registry.list_all()) == 0
        assert not registry.is_registered("fake")
    
    def test_tool_registry_empty_at_import(self):
        """Prove tool registry is empty when created - no auto-registration."""
        registry = ToolRegistry()
        assert len(registry.list_all()) == 0
        assert not registry.is_registered("fake_tool")
    
    def test_register_defaults_populates_channel_registry(self):
        """Prove explicit registration works for channel registry."""
        registry = ChannelRegistry()
        assert len(registry.list_all()) == 0
        
        registry.register_defaults()
        
        assert len(registry.list_all()) == 1
        assert registry.is_registered("fake")
    
    def test_register_defaults_populates_model_registry(self):
        """Prove explicit registration works for model registry."""
        registry = ModelRegistry()
        assert len(registry.list_all()) == 0
        
        registry.register_defaults()
        
        assert len(registry.list_all()) == 1
        assert registry.is_registered("fake")
    
    def test_register_defaults_populates_tool_registry(self):
        """Prove explicit registration works for tool registry."""
        registry = ToolRegistry()
        assert len(registry.list_all()) == 0
        
        registry.register_defaults()
        
        assert len(registry.list_all()) == 1
        assert registry.is_registered("fake_tool")


class TestAppCreation:
    """Prove app can be created and accessed."""
    
    def test_get_app_returns_fastapi_instance(self):
        """Prove get_app returns a FastAPI application."""
        app = get_app()
        assert app is not None
        assert app.title == "WaxPrep Foundation"
        assert app.version == "0.1.0"
    
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
    
    def test_liveness_returns_alive(self, client):
        """Prove liveness endpoint returns alive status."""
        response = client.get("/health/liveness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
    
    def test_readiness_returns_ready(self, client):
        """Prove readiness endpoint returns ready status after lifespan init."""
        response = client.get("/health/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        # Readiness should include checks
        assert "checks" in data
    
    def test_readiness_includes_correlation_id_check(self, client):
        """Prove readiness reports correlation ID middleware status."""
        response = client.get("/health/readiness")
        data = response.json()
        checks = data.get("checks", {})
        assert "correlation_id_middleware" in checks
    
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
    
    def test_response_includes_correlation_id_header(self, client):
        """Prove every response includes X-Request-ID header."""
        response = client.get("/")
        assert "X-Request-ID" in response.headers
        correlation_id = response.headers["X-Request-ID"]
        assert len(correlation_id) > 0
    
    def test_each_request_gets_unique_correlation_id(self, client):
        """Prove each request receives a different correlation ID."""
        response1 = client.get("/")
        response2 = client.get("/")
        
        id1 = response1.headers["X-Request-ID"]
        id2 = response2.headers["X-Request-ID"]
        
        assert id1 != id2  # Unique per request
    
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
    
    def test_root_returns_foundation_info(self, client):
        """Prove root endpoint returns foundation info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "WaxPrep Foundation - Stages 01-02 ONLY"
        assert data["stages"] == ["01", "02"]
        assert data["status"] == "running"
    
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
    
    def test_unknown_route_returns_404(self, client):
        """Prove 404 returns clean JSON, not traceback."""
        response = client.get("/nonexistent/path")
        assert response.status_code == 404
        data = response.json()
        # Should have detail, NOT traceback
        assert "detail" in data
        assert "Traceback" not in str(data)
        assert "File" not in str(data)
    
    def test_404_includes_correlation_id(self, client):
        """Prove 404 responses include correlation ID."""
        response = client.get("/nonexistent")
        assert "X-Request-ID" in response.headers
