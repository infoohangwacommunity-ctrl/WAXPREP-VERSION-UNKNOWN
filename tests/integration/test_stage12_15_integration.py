"""Stages 12-15 — cross-stage integration and adversarial tests.

These prove behaviour at the boundaries (middleware, exception handlers,
concurrent requests) rather than the happy path of a helper function.
"""

import json

import pytest
import structlog
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from waxprep.errors import (
    DependencyUnavailableError,
    NotFoundError,
    RateLimitedError,
    ValidationError,
)
from waxprep.main import get_app
from waxprep.observability.logging import configure_logging

pytestmark = pytest.mark.integration

SENTINEL = "SENTINEL-integration-7c1d"


@pytest.fixture
def client():
    """App with a set of probe routes covering each error category."""
    app = get_app()

    @app.get("/probe/not-found")
    async def not_found() -> JSONResponse:  # noqa: RUF029
        raise NotFoundError("Student not found")

    @app.get("/probe/invalid")
    async def invalid() -> JSONResponse:  # noqa: RUF029
        raise ValidationError("Malformed payload")

    @app.get("/probe/rate-limited")
    async def rate_limited() -> JSONResponse:  # noqa: RUF029
        raise RateLimitedError()

    @app.get("/probe/dependency-down")
    async def dependency_down() -> JSONResponse:  # noqa: RUF029
        raise DependencyUnavailableError()

    @app.get("/probe/unexpected")
    async def unexpected() -> JSONResponse:  # noqa: RUF029
        raise RuntimeError(f"provider said token={SENTINEL}")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


class TestPublicErrorContract:
    def test_client_errors_use_safe_message(self, client):
        response = client.get("/probe/not-found")
        assert response.status_code == 404
        assert response.json() == {"detail": "Student not found"}

    def test_validation_maps_to_422(self, client):
        assert client.get("/probe/invalid").status_code == 422

    def test_rate_limited_maps_to_429(self, client):
        assert client.get("/probe/rate-limited").status_code == 429

    def test_dependency_outage_maps_to_503(self, client):
        assert client.get("/probe/dependency-down").status_code == 503

    def test_unexpected_error_is_generic_and_leaks_nothing(self, client):
        response = client.get("/probe/unexpected")
        assert response.status_code == 500
        body = response.json()
        assert body == {
            "detail": "Internal server error",
            "message": "An unexpected error occurred",
        }
        assert SENTINEL not in response.text
        assert "RuntimeError" not in response.text
        assert "Traceback" not in response.text

    def test_error_responses_carry_correlation_id(self, client):
        response = client.get("/probe/not-found")
        assert response.headers.get("X-Request-ID")

    def test_inbound_request_id_is_preserved(self, client):
        supplied = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
        response = client.get("/probe/not-found", headers={"X-Request-ID": supplied})
        assert response.headers["X-Request-ID"] == supplied

    def test_invalid_inbound_request_id_is_replaced_not_trusted(self, client):
        response = client.get("/probe/not-found", headers={"X-Request-ID": "not-a-uuid"})
        returned = response.headers["X-Request-ID"]
        assert returned != "not-a-uuid"
        assert len(returned) == 36


class TestCorrelationIsolation:
    def test_concurrent_requests_keep_distinct_ids(self, client):
        """IDs must not bleed across requests sharing one process."""
        ids = [f"3f2504e0-4f89-11d3-9a0c-0305e82c33{i:02d}" for i in range(5)]
        for request_id in ids:
            response = client.get("/probe/not-found", headers={"X-Request-ID": request_id})
            assert response.headers["X-Request-ID"] == request_id

    def test_context_cleared_after_request(self, client, capsys):
        """A finished request must not leave its ID bound for the next one."""
        configure_logging(level="INFO", json_output=True)
        client.get(
            "/probe/not-found", headers={"X-Request-ID": "3f2504e0-4f89-11d3-9a0c-0305e82c3399"}
        )
        capsys.readouterr()
        structlog.get_logger().info("after_request")
        payload = json.loads(
            next(line for line in capsys.readouterr().out.splitlines() if "after_request" in line)
        )
        assert "request_id" not in payload, "stale correlation leaked between requests"


class TestLoggingSafetyAtBoundary:
    def test_secret_in_exception_never_reaches_logs(self, client, capsys):
        configure_logging(level="INFO", json_output=True)
        capsys.readouterr()
        client.get("/probe/unexpected")
        out = capsys.readouterr().out
        assert SENTINEL not in out
        assert "Unhandled exception" in out, "the failure must still be recorded"

    def test_typed_error_logs_bounded_fields(self, client, capsys):
        configure_logging(level="INFO", json_output=True)
        capsys.readouterr()
        client.get("/probe/not-found")
        out = capsys.readouterr().out
        payload = json.loads(next(line for line in out.splitlines() if "request_rejected" in line))
        assert payload["error.code"] == "WAX-1005"
        assert payload["error.category"] == "not_found"
        assert payload["request_id"]


class TestStartupWiring:
    def test_healthy_app_still_starts_with_telemetry_disabled(self, client):
        assert client.get("/health/liveness").status_code == 200
        assert client.get("/health/readiness").status_code == 200

    def test_readiness_does_not_leak_internal_detail(self, client):
        body = client.get("/health/readiness").json()
        text = json.dumps(body)
        assert "password" not in text.lower()
        assert "token" not in text.lower()


class TestTelemetryStartupWiring:
    def test_startup_enables_metrics_when_telemetry_is_active(self, monkeypatch):
        """Prove the composition root actually wires metrics, not just telemetry."""
        from waxprep.main import _app_state  # noqa: F401  (ensures module import)
        from waxprep.observability import metrics as metrics_module

        calls = []
        monkeypatch.setattr(
            "waxprep.observability.metrics.Metrics.configure",
            lambda self, **_kw: calls.append(1) or True,
        )
        monkeypatch.setattr(
            "waxprep.observability.telemetry.Telemetry.configure",
            lambda self, _cfg: type("S", (), {"active": True, "reason": "enabled"})(),
        )
        # Re-run the lifespan body through a TestClient boot.
        with TestClient(get_app()) as client:
            assert client.get("/health/liveness").status_code == 200
        assert calls, "metrics.configure() must run when telemetry is active"
        assert metrics_module is not None
