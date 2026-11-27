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
            lambda self, _cfg: type(
                "S",
                (),
                {
                    "active": True,
                    "reason": "enabled",
                    "meter_provider": None,
                    "metrics_active": True,
                    "metrics_reason": "enabled",
                },
            )(),
        )
        # Re-run the lifespan body through a TestClient boot.
        with TestClient(get_app()) as client:
            assert client.get("/health/liveness").status_code == 200
        assert calls, "metrics.configure() must run when telemetry is active"
        assert metrics_module is not None

    def test_startup_passes_metrics_endpoint_and_auth_token_through(self, monkeypatch):
        """Configuration must reach the exporter wiring, not stop at Settings."""
        from pydantic import SecretStr

        token = "-".join(["telemetry", "startup", "placeholder"])
        meter_marker = object()
        captured = {}

        class FakeState:
            active = True
            reason = "enabled"
            metrics_active = True
            metrics_reason = "enabled"
            meter_provider = meter_marker

        def fake_configure(_self, config):
            captured["config"] = config
            return FakeState()

        def fake_metrics_configure(_self, **kwargs):
            captured["metrics_kwargs"] = kwargs
            return True

        monkeypatch.setattr("waxprep.observability.telemetry.Telemetry.configure", fake_configure)
        monkeypatch.setattr(
            "waxprep.observability.metrics.Metrics.configure", fake_metrics_configure
        )
        monkeypatch.setattr(
            "waxprep.main.settings.telemetry_metrics_endpoint",
            "http://collector:4318/v1/metrics",
        )
        monkeypatch.setattr("waxprep.main.settings.telemetry_auth_token", SecretStr(token))

        with TestClient(get_app()) as test_client:
            assert test_client.get("/health/liveness").status_code == 200

        assert captured["config"].metrics_endpoint == "http://collector:4318/v1/metrics"
        assert captured["config"].auth_token == token
        assert captured["metrics_kwargs"]["meter_provider"] is meter_marker

    def test_startup_does_not_claim_metrics_when_the_pipeline_degraded(self, monkeypatch):
        """No exporting meter provider means no instruments, not no-op instruments."""
        configured = []

        class DegradedState:
            active = True
            reason = "enabled"
            metrics_active = False
            metrics_reason = "metrics_exporter_unavailable"
            meter_provider = None

        monkeypatch.setattr(
            "waxprep.observability.telemetry.Telemetry.configure",
            lambda _self, _config: DegradedState(),
        )
        monkeypatch.setattr(
            "waxprep.observability.metrics.Metrics.configure",
            lambda _self, **_kwargs: configured.append(1) or True,
        )

        with TestClient(get_app()) as test_client:
            assert test_client.get("/health/liveness").status_code == 200

        assert configured == []


class _RecordingMetrics:
    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.readiness: list[bool] = []

    def record_error(self, *, category: str, code: str) -> None:
        self.errors.append((category, code))

    def record_readiness(self, *, ready: bool) -> None:
        self.readiness.append(ready)


class TestMetricWiring:
    """Prove the catalogue is used by the application, not just defined."""

    def test_typed_error_records_exactly_one_bounded_metric(self, client, monkeypatch):
        recorder = _RecordingMetrics()
        monkeypatch.setattr("waxprep.main.metrics", recorder)
        assert client.get("/probe/not-found").status_code == 404
        assert recorder.errors == [("not_found", "WAX-1005")]

    def test_cancellation_is_not_counted_as_a_failure(self, client, monkeypatch):
        from waxprep.errors import CancellationError

        app = get_app()

        @app.get("/probe/cancelled")
        async def cancelled() -> JSONResponse:  # noqa: RUF029
            raise CancellationError()

        recorder = _RecordingMetrics()
        monkeypatch.setattr("waxprep.main.metrics", recorder)
        assert client.get("/probe/cancelled").status_code == 503
        assert recorder.errors == []

    def test_unexpected_exception_records_programming_defect(self, client, monkeypatch):
        recorder = _RecordingMetrics()
        monkeypatch.setattr("waxprep.main.metrics", recorder)
        assert client.get("/probe/unexpected").status_code == 500
        assert recorder.errors == [("programming_defect", "WAX-3002")]

    def test_readiness_records_a_ready_outcome(self, client, monkeypatch):
        recorder = _RecordingMetrics()
        monkeypatch.setattr("waxprep.main.metrics", recorder)
        assert client.get("/health/readiness").status_code == 200
        assert recorder.readiness == [True]

    def test_readiness_records_a_not_ready_outcome(self, client, monkeypatch):
        import waxprep.main as main_module

        recorder = _RecordingMetrics()
        monkeypatch.setattr("waxprep.main.metrics", recorder)
        monkeypatch.setattr(main_module._app_state, "registries_ready", False)
        response = client.get("/health/readiness")
        assert response.status_code == 503
        assert recorder.readiness == [False]

    def test_error_metric_failure_never_masks_the_response(self, client, monkeypatch):
        class ExplodingMetrics:
            def record_error(self, **_kwargs):
                raise RuntimeError("metrics backend down")

            def record_readiness(self, **_kwargs):
                raise RuntimeError("metrics backend down")

        monkeypatch.setattr("waxprep.main.metrics", ExplodingMetrics())
        assert client.get("/probe/not-found").status_code == 404
        assert client.get("/probe/unexpected").status_code == 500
        assert client.get("/health/readiness").status_code == 200


class TestRawPathNeverLogged:
    def test_dynamic_url_identifiers_never_reach_logs(self, client, capsys):
        from pydantic import BaseModel
        from starlette.exceptions import HTTPException as StarletteHTTPException

        class Body(BaseModel):
            name: str

        app = get_app()

        @app.get("/students/{student_id}")
        async def student(student_id: str) -> JSONResponse:  # noqa: RUF029, ARG001
            raise NotFoundError("Student not found")

        @app.get("/students/{student_id}/explode")
        async def explode(student_id: str) -> JSONResponse:  # noqa: RUF029, ARG001
            # The exception message is generic: the only place the identifier
            # appears is the URL path, which the handler must not log.
            raise RuntimeError("provider failed")

        @app.post("/students/{student_id}/validate")
        async def validate(student_id: str, body: Body) -> JSONResponse:  # noqa: RUF029, ARG001
            return JSONResponse({"id": student_id})

        @app.get("/students/{student_id}/teapot")
        async def teapot(student_id: str) -> JSONResponse:  # noqa: RUF029, ARG001
            raise StarletteHTTPException(status_code=418, detail=student_id)

        configure_logging(level="INFO", json_output=True)
        capsys.readouterr()

        client.get(f"/students/{SENTINEL}")
        client.get(f"/students/{SENTINEL}/explode")
        client.post(f"/students/{SENTINEL}/validate", json={"name": 123})
        client.get(f"/students/{SENTINEL}/teapot")

        out = capsys.readouterr().out
        assert SENTINEL not in out
        for template in (
            "/students/{student_id}",
            "/students/{student_id}/explode",
            "/students/{student_id}/validate",
            "/students/{student_id}/teapot",
        ):
            assert template in out


class TestIncomingRequestTracing:
    def test_request_produces_one_exported_span_and_correlates_logs(
        self, client, monkeypatch, capsys
    ):
        from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
        from opentelemetry.sdk.trace.export import SpanExportResult

        from waxprep.observability.telemetry import (
            TelemetryConfig,
        )
        from waxprep.observability.telemetry import (
            telemetry as global_telemetry,
        )

        class SilentMetricExporter(MetricExporter):
            def export(self, _metrics_data, _timeout_millis=10000, **_kwargs):
                return MetricExportResult.SUCCESS

            def force_flush(self, _timeout_millis=10000):
                return True

            def shutdown(self, _timeout_millis=30000, **_kwargs):
                return None

        class RecordingSpanExporter:
            last = None

            def __init__(self, **_kwargs):
                self.spans = []
                RecordingSpanExporter.last = self

            def export(self, spans):
                self.spans.extend(spans)
                return SpanExportResult.SUCCESS

            def force_flush(self, _timeout_millis=30000):
                return True

            def shutdown(self):
                return None

        monkeypatch.setattr(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            RecordingSpanExporter,
        )
        monkeypatch.setattr(
            "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter",
            SilentMetricExporter,
        )
        state = global_telemetry.configure(
            TelemetryConfig(
                enabled=True,
                endpoint="http://127.0.0.1:9/v1/traces",
                environment="test",
                export_timeout_ms=100,
            )
        )
        try:
            assert state.active is True
            configure_logging(level="INFO", json_output=True)
            capsys.readouterr()

            parent_trace_id = "0af7651916cd43dd8448eb211c80319c"
            parent_span_id = "b7ad6b7169203331"
            traceparent = f"00-{parent_trace_id}-{parent_span_id}-01"
            response = client.get("/probe/not-found", headers={"traceparent": traceparent})
            assert response.status_code == 404

            out = capsys.readouterr().out
            payload = json.loads(
                next(line for line in out.splitlines() if "request_rejected" in line)
            )
            assert payload["trace_id"]
            assert payload["span_id"]
            assert payload["trace_id"] != payload["request_id"]

            assert state.tracer_provider.force_flush() is True
            exporter = RecordingSpanExporter.last
            assert exporter is not None
            request_spans = [s for s in exporter.spans if s.name == "http.server.request"]
            assert len(request_spans) == 1

            span = request_spans[0]
            assert span.attributes["http.request.method"] == "GET"
            assert span.attributes["http.route"] == "/probe/not-found"
            assert span.attributes["http.response.status_class"] == "4xx"
            assert format(span.context.trace_id, "032x") == payload["trace_id"]
            assert format(span.context.span_id, "016x") == payload["span_id"]
            # Inbound W3C context was continued; the span is a child, not a root.
            assert format(span.context.trace_id, "032x") == parent_trace_id
        finally:
            global_telemetry.shutdown()
