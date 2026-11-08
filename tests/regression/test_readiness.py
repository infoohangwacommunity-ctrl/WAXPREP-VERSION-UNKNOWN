"""
Regression Test: Readiness - Stage 05

Test for readiness endpoint behavior.
This is a known requirement from Stage 02 that must be maintained.

The contract:
- Liveness != Readiness
- Liveness: Is the process alive?
- Readiness: Is the application ready to accept requests?
- Both endpoints must exist and return distinct responses
"""

import pytest
from fastapi.testclient import TestClient

from waxprep.main import get_app


class TestReadiness:
    """Regression tests for readiness endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Test client for FastAPI app."""
        app = get_app()
        with TestClient(app) as test_client:
            yield test_client

    def test_liveness_endpoint_exists(self, client: TestClient) -> None:
        """Test that liveness endpoint exists."""
        response = client.get("/health/liveness")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "alive"

    def test_readiness_endpoint_exists(self, client: TestClient) -> None:
        """Test that readiness endpoint exists."""
        response = client.get("/health/readiness")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ready"

    def test_liveness_not_equal_readiness(self, client: TestClient) -> None:
        """Test that liveness != readiness conceptually.

        This is the key distinction from Stage 02:
        - Liveness: Is the process alive?
        - Readiness: Is the application ready?

        In Stages 01-02, both return 200, but they are distinct.
        Later stages will make readiness fail when dependencies are down.
        """
        liveness = client.get("/health/liveness")
        readiness = client.get("/health/readiness")

        # Both should succeed in current implementation
        assert liveness.status_code == 200
        assert readiness.status_code == 200

        # But they are different endpoints with different purposes
        liveness_data = liveness.json()
        readiness_data = readiness.json()

        assert liveness_data["status"] == "alive"
        assert readiness_data["status"] == "ready"

        # They should be different endpoints
        assert liveness_data != readiness_data

    def test_readiness_contract(self, client: TestClient) -> None:
        """Test the readiness contract.

        The contract states:
        - Readiness must check if the application is ready to accept requests
        - In Stage 02, it always returns ready
        - In later stages, it will check dependencies (database, external services)
        - It must NOT lie (return ready when not actually ready)
        """
        response = client.get("/health/readiness")
        data = response.json()

        # For now, it should return ready
        assert data["status"] == "ready"

        # In the future, this will check:
        # - Database connection
        # - External service availability
        # - Resource initialization
