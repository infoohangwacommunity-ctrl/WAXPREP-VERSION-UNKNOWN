"""Stage 14 — telemetry, metrics, and middleware tests.

No network, no vendor account, no live collector: every case here runs offline
and asserts the documented failure policy instead.
"""

from typing import ClassVar

import pytest
from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult

from waxprep.observability.metrics import Metrics, null_instrument
from waxprep.observability.metrics import metrics as metrics_singleton
from waxprep.observability.telemetry import (
    Telemetry,
    TelemetryConfig,
    normalize_method,
    route_template,
    status_class,
)

pytestmark = pytest.mark.unit


class TestBoundedLabels:
    @pytest.mark.parametrize(
        ("code", "expected"),
        [(200, "2xx"), (301, "3xx"), (404, "4xx"), (500, "5xx"), (102, "1xx")],
    )
    def test_status_class(self, code, expected):
        assert status_class(code) == expected

    def test_unexpected_status_coerced_to_5xx(self):
        """A nonsense code must not create a new label value."""
        assert status_class(999) == "5xx"

    @pytest.mark.parametrize("method", ["GET", "post", "Delete"])
    def test_known_methods_normalised(self, method):
        assert normalize_method(method) in {"GET", "POST", "DELETE"}

    def test_unknown_method_collapses(self):
        assert normalize_method("PROPFIND") == "OTHER"
        assert normalize_method("") == "OTHER"

    def test_route_template_prefers_matched_template(self):
        """The template, not the raw path, becomes the metric label."""
        assert (
            route_template("/students/9f3a1c", "/students/{student_id}") == "/students/{student_id}"
        )

    def test_route_template_never_uses_raw_path(self):
        """A raw identifier must never become a label value."""
        label = route_template("/students/9f3a1c/notes")
        assert label == "unmatched"
        assert "9f3a1c" not in label

    def test_known_static_paths_pass_through(self):
        assert route_template("/") == "/"
        assert route_template("/health/readiness") == "/health/readiness"


class TestTelemetryConfigValidation:
    def test_sample_ratio_bounds(self):
        with pytest.raises(ValueError):
            TelemetryConfig(sample_ratio=1.5).validate()
        with pytest.raises(ValueError):
            TelemetryConfig(sample_ratio=-0.1).validate()

    def test_export_timeout_must_be_positive(self):
        with pytest.raises(ValueError):
            TelemetryConfig(export_timeout_ms=0).validate()

    def test_enabled_without_endpoint_is_rejected(self):
        with pytest.raises(ValueError, match="no OTLP endpoint"):
            TelemetryConfig(enabled=True, endpoint=None).validate()


class TestTelemetryLifecycle:
    def test_disabled_by_default_and_fully_inert(self):
        instance = Telemetry()
        state = instance.configure(TelemetryConfig(enabled=False))
        assert state.active is False
        assert state.reason == "disabled"
        assert instance.state.enabled is False

    def test_missing_sdk_degrades_instead_of_crashing(self, monkeypatch):
        """Telemetry is optional: an absent SDK must not break startup."""
        import builtins
        import sys

        # Drop any partially imported opentelemetry modules so this test sees a
        # genuinely absent SDK rather than a cached half-initialised package.
        for name in [m for m in sys.modules if m.startswith("opentelemetry")]:
            monkeypatch.delitem(sys.modules, name)

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("opentelemetry"):
                raise ImportError("simulated missing SDK")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        instance = Telemetry()
        state = instance.configure(TelemetryConfig(enabled=True, endpoint="http://collector:4318"))
        assert state.active is False
        assert state.reason == "sdk_unavailable"

    def test_missing_exporter_degrades(self, monkeypatch):
        import builtins
        import sys

        for name in [m for m in sys.modules if "otlp" in m]:
            monkeypatch.delitem(sys.modules, name)

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if "otlp" in name:
                raise ImportError("simulated missing exporter")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        instance = Telemetry()
        state = instance.configure(TelemetryConfig(enabled=True, endpoint="http://collector:4318"))
        assert state.active is False
        assert state.reason == "exporter_unavailable"

    def test_shutdown_is_safe_when_never_enabled(self):
        """Shutdown must not raise for a process that never enabled telemetry."""
        instance = Telemetry()
        instance.shutdown()
        assert instance.state.active is False

    def test_shutdown_swallows_exporter_errors(self):
        """A hung/exploding exporter must not delay process exit."""

        class ExplodingProvider:
            def shutdown(self):
                raise RuntimeError("collector unreachable")

        instance = Telemetry()
        instance._state.tracer_provider = ExplodingProvider()  # noqa: SLF001
        instance._state.active = True  # noqa: SLF001
        instance.shutdown()
        assert instance.state.active is False

    def test_span_is_noop_when_inactive(self):
        instance = Telemetry()
        with instance.span("test_span") as span:
            assert span is None

    def test_current_ids_empty_without_active_span(self):
        assert Telemetry.current_ids() == {}

    def test_extract_context_returns_none_without_the_sdk(self, monkeypatch):
        """Inbound propagation must degrade quietly, never break a request."""
        import builtins

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("opentelemetry"):
                raise ImportError("simulated missing SDK")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        carrier = {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
        assert Telemetry.extract_context(carrier) is None

    def test_current_ids_returns_empty_when_sdk_absent(self, monkeypatch):
        """Log correlation must degrade quietly, never raise."""
        import builtins
        import sys

        for name in [m for m in sys.modules if m.startswith("opentelemetry")]:
            monkeypatch.delitem(sys.modules, name)

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("opentelemetry"):
                raise ImportError("simulated missing SDK")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        assert Telemetry.current_ids() == {}


class TestMetrics:
    def test_noop_when_never_configured(self):
        instance = Metrics()
        assert instance.active is False
        instance.record_request(method="GET", route="/", status_code=200, duration_ms=1.0)
        instance.record_error(category="validation", code="WAX-1001")
        instance.record_readiness(ready=True)

    def test_configure_returns_false_without_sdk(self, monkeypatch):
        import builtins
        import sys

        for name in [m for m in sys.modules if m.startswith("opentelemetry")]:
            monkeypatch.delitem(sys.modules, name)

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("opentelemetry"):
                raise ImportError("simulated missing SDK")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        assert Metrics().configure() is False

    def test_recording_uses_bounded_attributes(self):
        """Every attribute emitted must come from a bounded vocabulary."""
        recorded = []

        class Spy:
            def add(self, amount, attributes=None):
                recorded.append(attributes)

            def record(self, value, attributes=None):
                recorded.append(attributes)

        instance = Metrics()
        instance.request_count = Spy()
        instance.request_duration = Spy()
        instance.record_request(
            method="get", route="/health/liveness", status_code=200, duration_ms=5.0
        )
        assert recorded[0] == {
            "http.request.method": "GET",
            "http.route": "/health/liveness",
            "http.response.status_class": "2xx",
        }

    def test_global_metrics_instance_starts_inactive(self):
        """The process-wide handle must not silently be active before startup."""
        assert metrics_singleton.active is False

    def test_reset_drops_instruments_after_provider_shutdown(self):
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader

        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        instance = Metrics()
        instance.configure(meter_provider=provider)
        assert instance.active is True

        instance.reset()
        assert instance.active is False
        assert instance.request_count is null_instrument
        assert instance.request_duration is null_instrument
        assert instance.error_count is null_instrument
        assert instance.readiness_checks is null_instrument
        instance.record_request(method="GET", route="/", status_code=200, duration_ms=1.0)

    def test_package_does_not_shadow_submodule(self):
        """A module and an instance sharing a name would hide the module."""
        import waxprep.observability.metrics as metrics_module

        assert hasattr(metrics_module, "Metrics")


class TestInstrumentWiring:
    def test_configure_creates_all_instruments(self):
        """Exercise the real SDK path: builds every instrument once."""
        instance = Metrics()
        assert instance.configure(service_name="waxprep-test") is True
        assert instance.active is True
        for name in ("request_count", "request_duration", "error_count", "readiness_checks"):
            assert getattr(instance, name) is not None

    def test_recording_after_configure_is_safe(self):
        instance = Metrics()
        instance.configure(service_name="waxprep-test")
        instance.record_request(method="GET", route="/", status_code=200, duration_ms=1.5)
        instance.record_error(category="not_found", code="WAX-1005")
        instance.record_readiness(ready=True)
        instance.record_readiness(ready=False)


class TestObservabilityMiddleware:
    def test_binds_and_unbinds_trace_ids(self, monkeypatch):
        """Span context must be bound for the request and cleared afterwards."""
        import structlog

        from waxprep.middleware.observability import ObservabilityMiddleware

        bound, unbound = [], []
        monkeypatch.setattr(
            structlog.contextvars, "bind_contextvars", lambda **kw: bound.append(kw)
        )
        monkeypatch.setattr(
            structlog.contextvars, "unbind_contextvars", lambda *a: unbound.append(a)
        )
        monkeypatch.setattr(
            "waxprep.middleware.observability.telemetry.current_ids",
            lambda: {"trace_id": "abc", "span_id": "def"},
        )

        middleware = ObservabilityMiddleware(app=None)  # type: ignore[arg-type]

        async def call_next(_request):  # noqa: RUF029
            from starlette.responses import Response

            return Response(status_code=204)

        class FakeRequest:
            method = "GET"
            url = type("U", (), {"path": "/health/liveness"})()
            app = type("A", (), {"routes": []})()
            headers: ClassVar[dict[str, str]] = {}

        import asyncio

        asyncio.run(middleware.dispatch(FakeRequest(), call_next))
        assert bound == [{"trace_id": "abc", "span_id": "def"}]
        assert unbound == [("trace_id", "span_id")]

    def test_metric_failure_never_breaks_the_request(self, monkeypatch):
        """An observability outage must not surface as a request error."""
        from waxprep.middleware.observability import ObservabilityMiddleware

        class ExplodingMetrics:
            def record_request(self, **_kwargs):
                raise RuntimeError("metrics backend down")

        monkeypatch.setattr("waxprep.middleware.observability.metrics", ExplodingMetrics())

        class FakeRequest:
            method = "GET"
            url = type("U", (), {"path": "/"})()
            app = type("A", (), {"routes": []})()

        ObservabilityMiddleware._record(FakeRequest(), 200, 1.0)  # must not raise

    def test_span_attribute_failure_never_breaks_the_request(self):
        """A broken span implementation must not turn a request into a 500."""
        from waxprep.middleware.observability import ObservabilityMiddleware

        class ExplodingSpan:
            def set_attribute(self, _key, _value):
                raise RuntimeError("span backend down")

        class FakeRequest:
            method = "GET"
            url = type("U", (), {"path": "/"})()
            app = type("A", (), {"routes": []})()

        middleware = ObservabilityMiddleware(app=None)  # type: ignore[arg-type]
        # Must swallow the failure instead of raising into the request path.
        middleware._annotate_span(ExplodingSpan(), FakeRequest(), 500)


class TestRealExporterPath:
    """Exercise the installed-SDK path without contacting a real collector.

    The OTLP exporter connects lazily, so construction + span + bounded
    shutdown can be verified offline. The endpoint is a closed local port with a
    short timeout, which proves the failure policy rather than a live backend.
    """

    def test_configure_span_and_shutdown_offline(self):
        instance = Telemetry()
        state = instance.configure(
            TelemetryConfig(
                enabled=True,
                endpoint="http://127.0.0.1:9/v1/traces",
                environment="test",
                sample_ratio=1.0,
                export_timeout_ms=100,
            )
        )
        assert state.active is True
        assert state.reason == "enabled"
        assert state.tracer_provider is not None

        with instance.span("probe_span", {"custom.attr": "value"}) as span:
            assert span is not None
            ids = Telemetry.current_ids()
            assert set(ids) == {"trace_id", "span_id"}
            assert len(ids["trace_id"]) == 32
            assert len(ids["span_id"]) == 16

        instance.shutdown()
        assert instance.state.active is False

    def test_span_without_attributes_still_works(self):
        instance = Telemetry()
        instance.configure(
            TelemetryConfig(
                enabled=True,
                endpoint="http://127.0.0.1:9/v1/traces",
                environment="test",
                export_timeout_ms=50,
            )
        )
        with instance.span("no_attrs") as span:
            assert span is not None
        instance.shutdown()


class TestRouteLabelEndToEnd:
    def test_parameterised_route_uses_template_not_raw_path(self, monkeypatch):
        """A real request to /items/{item_id} must not label metrics with the id."""
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        from fastapi.testclient import TestClient

        from waxprep.middleware.observability import ObservabilityMiddleware

        captured = []

        class Spy:
            def add(self, _amount, attributes=None):
                captured.append(attributes)

            def record(self, _value, attributes=None):
                captured.append(attributes)

        spy = Spy()
        monkeypatch.setattr("waxprep.middleware.observability.metrics.request_count", spy)
        monkeypatch.setattr("waxprep.middleware.observability.metrics.request_duration", spy)

        app = FastAPI(
            telemetry={
                "tracing": False,
                "metrics": False,
                "logs": False,
                "operation_spans": False,
            }
        )
        app.add_middleware(ObservabilityMiddleware)

        @app.get("/items/{item_id}")
        async def get_item(item_id: str) -> JSONResponse:  # noqa: RUF029
            return JSONResponse({"id": item_id})

        with TestClient(app) as client:
            assert client.get("/items/SECRET-IDENTIFIER-42").status_code == 200

        labels = [attrs.get("http.route") for attrs in captured if attrs]
        assert "/items/{item_id}" in labels
        assert all("SECRET-IDENTIFIER-42" not in str(label) for label in labels)


FAKE_TELEMETRY_TOKEN = "-".join(["telemetry", "auth", "placeholder"])


class TestExportEndpointAndAuth:
    """Exporter destination and credential wiring (never rendered)."""

    def test_metrics_endpoint_swaps_the_trace_signal_suffix(self):
        config = TelemetryConfig(endpoint="http://collector:4318/v1/traces/")
        assert config.resolved_metrics_endpoint() == "http://collector:4318/v1/metrics"

    def test_explicit_metrics_endpoint_wins(self):
        config = TelemetryConfig(
            endpoint="http://collector:4318/v1/traces",
            metrics_endpoint="http://metrics:4318/custom",
        )
        assert config.resolved_metrics_endpoint() == "http://metrics:4318/custom"

    def test_bare_base_endpoint_is_passed_through(self):
        config = TelemetryConfig(endpoint="http://collector:4318")
        assert config.resolved_metrics_endpoint() == "http://collector:4318"

    def test_no_endpoint_means_no_metrics_endpoint(self):
        assert TelemetryConfig().resolved_metrics_endpoint() is None

    def test_headers_are_absent_without_a_token(self):
        assert TelemetryConfig().exporter_headers() is None

    def test_headers_use_bearer_and_token_is_not_in_repr(self):
        config = TelemetryConfig(auth_token=FAKE_TELEMETRY_TOKEN)
        assert config.exporter_headers() == {"Authorization": f"Bearer {FAKE_TELEMETRY_TOKEN}"}
        assert FAKE_TELEMETRY_TOKEN not in repr(config)


class _FakeSpanExporter:
    instances: ClassVar[list] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.spans = []
        self.shutdown_called = False
        _FakeSpanExporter.instances.append(self)

    def export(self, spans):
        from opentelemetry.sdk.trace.export import SpanExportResult

        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def force_flush(self, _timeout_millis=30000):
        return True

    def shutdown(self):
        self.shutdown_called = True


class _FakeMetricExporter(MetricExporter):
    instances: ClassVar[list] = []

    def __init__(self, **kwargs):
        # Inherit the default temporality/aggregation contract the reader reads.
        super().__init__()
        self.kwargs = kwargs
        self.shutdown_called = False
        _FakeMetricExporter.instances.append(self)

    def export(self, _metrics_data, _timeout_millis=10000, **_kwargs):
        return MetricExportResult.SUCCESS

    def force_flush(self, _timeout_millis=10000):
        return True

    def shutdown(self, _timeout_millis=30000, **_kwargs):
        self.shutdown_called = True


class TestMetricsExportPipeline:
    def test_in_memory_reader_receives_real_measurements(self):
        """Instruments must be attached to a reader that actually collects."""
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import InMemoryMetricReader

        reader = InMemoryMetricReader()
        provider = MeterProvider(metric_readers=[reader])
        instance = Metrics()
        assert instance.configure(service_name="waxprep-test", meter_provider=provider) is True

        instance.record_request(
            method="GET", route="/items/{item_id}", status_code=200, duration_ms=3.5
        )
        instance.record_error(category="not_found", code="WAX-1005")
        instance.record_readiness(ready=False)

        data = reader.get_metrics_data()
        assert data is not None
        metrics_by_name = {
            metric.name: metric
            for resource_metrics in data.resource_metrics
            for scope_metrics in resource_metrics.scope_metrics
            for metric in scope_metrics.metrics
        }
        assert {
            "http.server.request.count",
            "http.server.request.duration",
            "waxprep.error.count",
            "waxprep.readiness.count",
        } <= set(metrics_by_name)

        attributes = [
            dict(point.attributes)
            for metric in metrics_by_name.values()
            for point in metric.data.data_points
        ]
        assert any(attrs.get("http.route") == "/items/{item_id}" for attrs in attributes)
        assert any(attrs.get("error.code") == "WAX-1005" for attrs in attributes)
        assert any(attrs.get("outcome") == "not_ready" for attrs in attributes)


class TestMetricProviderWiring:
    def test_configure_builds_an_exporting_meter_provider(self, monkeypatch, caplog):
        monkeypatch.setattr(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            _FakeSpanExporter,
        )
        monkeypatch.setattr(
            "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter",
            _FakeMetricExporter,
        )
        _FakeSpanExporter.instances.clear()
        _FakeMetricExporter.instances.clear()

        config = TelemetryConfig(
            enabled=True,
            endpoint="http://collector:4318/v1/traces",
            auth_token=FAKE_TELEMETRY_TOKEN,
            environment="test",
            export_timeout_ms=100,
        )
        instance = Telemetry()
        state = instance.configure(config)
        try:
            assert state.active is True
            assert state.metrics_active is True
            assert state.reason == "enabled"
            assert state.metrics_reason == "enabled"

            span_exporter = _FakeSpanExporter.instances[-1]
            metric_exporter = _FakeMetricExporter.instances[-1]
            expected_headers = {"Authorization": f"Bearer {FAKE_TELEMETRY_TOKEN}"}
            assert span_exporter.kwargs["headers"] == expected_headers
            assert metric_exporter.kwargs["headers"] == expected_headers
            assert metric_exporter.kwargs["endpoint"] == "http://collector:4318/v1/metrics"
            assert FAKE_TELEMETRY_TOKEN not in caplog.text
        finally:
            instance.shutdown()

        assert span_exporter.shutdown_called is True
        assert metric_exporter.shutdown_called is True

    def test_span_exporter_construction_failure_degrades(self, monkeypatch):
        def explode(**_kwargs):
            raise RuntimeError("bad exporter configuration")

        monkeypatch.setattr(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            explode,
        )
        instance = Telemetry()
        state = instance.configure(
            TelemetryConfig(enabled=True, endpoint="http://collector:4318/v1/traces")
        )
        assert state.active is False
        assert state.reason == "exporter_unavailable"

    def test_metrics_sdk_absent_does_not_disable_traces(self, monkeypatch):
        import builtins

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name.startswith("opentelemetry.sdk.metrics") or "metric_exporter" in name:
                raise ImportError("simulated missing metrics SDK")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        instance = Telemetry()
        state = instance.configure(
            TelemetryConfig(enabled=True, endpoint="http://127.0.0.1:9/v1/traces")
        )
        try:
            assert state.active is True
            assert state.metrics_active is False
            assert state.metrics_reason == "metrics_sdk_unavailable"
        finally:
            instance.shutdown()

    def test_metrics_exporter_failure_degrades_independently(self, monkeypatch):
        monkeypatch.setattr(
            "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
            _FakeSpanExporter,
        )

        def explode(**_kwargs):
            raise RuntimeError("bad metrics exporter configuration")

        monkeypatch.setattr(
            "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter",
            explode,
        )
        instance = Telemetry()
        state = instance.configure(
            TelemetryConfig(enabled=True, endpoint="http://collector:4318/v1/traces")
        )
        try:
            assert state.active is True
            assert state.metrics_active is False
            assert state.metrics_reason == "metrics_exporter_unavailable"
        finally:
            instance.shutdown()

    def test_shutdown_swallows_meter_provider_errors(self):
        class ExplodingMeterProvider:
            def shutdown(self):
                raise RuntimeError("metrics collector unreachable")

        instance = Telemetry()
        instance._state.meter_provider = ExplodingMeterProvider()  # noqa: SLF001
        instance._state.active = True  # noqa: SLF001
        instance.shutdown()
        assert instance.state.active is False

    def test_span_is_noop_when_active_without_a_provider(self):
        instance = Telemetry()
        instance._state.active = True  # noqa: SLF001
        with instance.span("test_span") as span:
            assert span is None
