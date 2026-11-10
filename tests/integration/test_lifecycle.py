"""
Integration Test: Application Lifecycle - Stage 05

Integration tests for application lifecycle.
Tests startup sequence, shutdown sequence, and health checks.
"""

import pytest
from fastapi.testclient import TestClient

from waxprep.infrastructure.lifecycle import LifecycleState
from waxprep.main import get_app


class TestApplicationLifecycle:
    """Integration tests for application lifecycle."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Test client for FastAPI app."""
        app = get_app()
        with TestClient(app) as test_client:
            yield test_client

    def test_application_starts_successfully(self, client: TestClient) -> None:
        """Test that the application starts successfully."""
        # If we can make requests, the app started
        response = client.get("/")
        assert response.status_code == 200

    def test_root_endpoint_returns_foundation_info(self, client: TestClient) -> None:
        """Test that root endpoint returns foundation information."""
        response = client.get("/")
        data = response.json()

        assert "message" in data
        assert "WaxPrep" in data["message"]
        assert "stages" in data
        assert "07" in data["stages"]
        assert data["status"] == "running"

    def test_architecture_endpoint_exists(self, client: TestClient) -> None:
        """Test that architecture endpoint exists and returns correct info."""
        response = client.get("/architecture")
        assert response.status_code == 200

        data = response.json()
        assert data["architecture"] == "hexagonal"
        assert "layers" in data
        assert len(data["layers"]) > 0

    def test_lifecycle_state_in_root_response(self, client: TestClient) -> None:
        """Test that lifecycle state is included in root response."""
        response = client.get("/")
        data = response.json()

        assert "lifecycle_state" in data
        # The state should be one of the valid states
        valid_states = [s.value for s in LifecycleState]
        assert data["lifecycle_state"] in valid_states

    def test_registries_in_root_response(self, client: TestClient) -> None:
        """Test that registries are included in root response."""
        response = client.get("/")
        data = response.json()

        assert "registries" in data
        assert "channels" in data["registries"]
        assert "models" in data["registries"]
        assert "tools" in data["registries"]

    def test_health_endpoints_are_distinct(self, client: TestClient) -> None:
        """Test that health endpoints are distinct and both work."""
        liveness = client.get("/health/liveness")
        readiness = client.get("/health/readiness")

        assert liveness.status_code == 200
        assert readiness.status_code == 200

        liveness_data = liveness.json()
        readiness_data = readiness.json()

        assert liveness_data["status"] == "alive"
        assert readiness_data["status"] == "ready"

    def test_application_version(self, client: TestClient) -> None:
        """Test that the application version is correct."""
        response = client.get("/")
        data = response.json()

        # Version should be 0.4.0 for Stage 07
        assert "07" in data.get("message", "") or "0.4" in data.get("message", "")
