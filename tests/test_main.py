"""
Test Main Application - Stage 02
Prove ASGI app works, health endpoints work, graceful shutdown works.
"""

import pytest
from fastapi.testclient import TestClient

from waxprep.main import get_app


@pytest.fixture
def client():
    """Test client for FastAPI app."""
    app = get_app()
    with TestClient(app) as test_client:
        yield test_client


class TestHealthEndpoints:
    """Prove health endpoints work and distinguish liveness from readiness."""

    def test_liveness_endpoint(self, client):
        """Prove liveness endpoint returns alive status."""
        response = client.get("/health/liveness")
        assert response.status_code == 200
        assert response.json() == {"status": "alive"}

    def test_readiness_endpoint(self, client):
        """Prove readiness endpoint returns ready status."""
        response = client.get("/health/readiness")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}

    def test_liveness_not_equal_readiness(self, client):
        """Prove liveness != readiness conceptually.

        In Stages 01-02, both return 200, but the endpoints are distinct.
        Later stages will make readiness fail when dependencies are down.
        """
        liveness = client.get("/health/liveness")
        readiness = client.get("/health/readiness")

        # Both should succeed in Stages 01-02
        assert liveness.status_code == 200
        assert readiness.status_code == 200

        # But they are different endpoints with different purposes
        assert liveness.json()["status"] == "alive"
        assert readiness.json()["status"] == "ready"


class TestRootEndpoint:
    """Prove root endpoint works."""

    def test_root_endpoint(self, client):
        """Prove root endpoint returns foundation info."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "WaxPrep Foundation - Stages 01-02 ONLY"
        assert data["stages"] == ["01", "02"]
        assert data["status"] == "running"
