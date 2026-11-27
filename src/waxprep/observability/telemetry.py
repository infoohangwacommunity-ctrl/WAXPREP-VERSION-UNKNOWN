"""
Observability and Metrics - Stage 14

Portable telemetry: OpenTelemetry API/SDK with OTLP export. The application
emits standard signals and stays vendor-neutral; the backend is a deployment
choice, not an architectural one.

Two hard rules:
1. Telemetry is optional. If it is disabled, unconfigured, or the SDK is
   absent, the application still serves requests. Instrumentation never
   becomes a startup dependency.
2. Metric labels are low-cardinality by construction. Route *templates* are
   used instead of raw paths, and error *categories* instead of messages.
   Request IDs, user IDs, and prompts belong in logs/traces, never labels.
"""

from __future__ import annotations

import logging
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Bounded label vocabularies. Anything outside these is coerced, so a rogue
# caller cannot silently create unbounded cardinality.
METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})
STATUS_CLASSES = frozenset({"1xx", "2xx", "3xx", "4xx", "5xx"})
OUTCOMES = frozenset({"success", "failure", "timeout", "cancelled"})

# Fixed label values. Kept as named constants so every emission site shares one
# definition and a stray literal cannot silently create a new label value.
UNMATCHED_ROUTE = "unmatched"
OTHER_METHOD = "OTHER"
UNKNOWN_STATUS_CLASS = "5xx"
# Paths that are genuinely static and therefore safe to use verbatim.
STATIC_ROUTES = frozenset({"/", "/health/liveness", "/health/readiness"})


def status_class(status_code: int) -> str:
    """Map an HTTP status code to its bounded class label (``2xx``...)."""
    bucket = status_code // 100
    label = f"{bucket}xx"
    return label if label in STATUS_CLASSES else UNKNOWN_STATUS_CLASS


def normalize_method(method: str) -> str:
    """Return a bounded HTTP method label; unknown methods collapse to OTHER."""
    upper = (method or "").upper()
    return upper if upper in METHODS else OTHER_METHOD


def route_template(path: str | None, matched_route: str | None = None) -> str:
    """Return a low-cardinality route label for a request.

    Prefers the route *template* Starlette actually matched (e.g.
    ``/students/{student_id}``) over the request path, because raw paths embed
    identifiers, explode metric cardinality, and leak data into telemetry.

    Falls back to a fixed label for anything unmatched, so an unknown path can
    never become a new label value.
    """
    if matched_route:
        return matched_route
    label = UNMATCHED_ROUTE
    if path in STATIC_ROUTES:
        label = str(path)
    return label


@dataclass(slots=True)
class TelemetryConfig:
    """Validated telemetry configuration derived from application settings."""

    enabled: bool = False
    endpoint: str | None = None
    metrics_endpoint: str | None = None
    service_name: str = "waxprep"
    service_version: str = "0.1.0"
    environment: str = "development"
    sample_ratio: float = 1.0
    export_timeout_ms: int = 5000
    # An exporter credential is never rendered in repr()/logs. ``field(repr=False)``
    # keeps a misdirected debug print from leaking it; the raw value is only used
    # to build the OTLP Authorization header.
    auth_token: str | None = field(default=None, repr=False)
    extra: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Reject impossible configuration before any exporter is built."""
        if not 0.0 <= self.sample_ratio <= 1.0:
            raise ValueError("sample_ratio must be between 0 and 1")
        if self.export_timeout_ms <= 0:
            raise ValueError("export_timeout_ms must be positive")
        if self.enabled and not self.endpoint:
            raise ValueError("telemetry is enabled but no OTLP endpoint is configured")

    def resolved_metrics_endpoint(self) -> str | None:
        """Return the OTLP/HTTP metrics endpoint for this configuration.

        An explicit metrics endpoint always wins. Otherwise the trace endpoint is
        reused: if it is a full ``/v1/traces`` URL the signal suffix is swapped,
        and a bare base URL is passed through so the exporter appends
        ``/v1/metrics`` itself.
        """
        if self.metrics_endpoint:
            return self.metrics_endpoint
        if self.endpoint:
            cleaned = self.endpoint.rstrip("/")
            if cleaned.endswith("/v1/traces"):
                return f"{cleaned.removesuffix('/v1/traces')}/v1/metrics"
        return self.endpoint

    def exporter_headers(self) -> dict[str, str] | None:
        """Build OTLP authentication headers, or None when no token is set."""
        if not self.auth_token:
            return None
        return {"Authorization": f"Bearer {self.auth_token}"}


@dataclass(slots=True)
class TelemetryState:
    """Outcome of a startup attempt, readable by readiness and diagnostics."""

    active: bool = False
    reason: str = "disabled"
    tracer_provider: Any = None
    meter_provider: Any = None
    metrics_active: bool = False
    metrics_reason: str = "disabled"

    @property
    def enabled(self) -> bool:
        return self.active


class Telemetry:
    """Holds the process-wide telemetry state.

    All methods are safe to call when telemetry is off; they become no-ops.
    """

    def __init__(self) -> None:
        self._state = TelemetryState()

    @property
    def state(self) -> TelemetryState:
        return self._state

    def configure(self, config: TelemetryConfig) -> TelemetryState:
        """Start telemetry if enabled. Never raises for a missing backend.

        A misconfigured *enabled* exporter is a configuration error and raises
        ValueError from ``config.validate()``; an *unavailable SDK* is not, and
        degrades to a documented "unavailable" state instead of blocking boot.
        """
        if not config.enabled:
            self._state = TelemetryState(active=False, reason="disabled")
            return self._state

        config.validate()

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
        except ImportError:
            logger.warning("Telemetry enabled but OpenTelemetry SDK is unavailable")
            self._state = TelemetryState(active=False, reason="sdk_unavailable")
            return self._state

        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )
        except ImportError:
            logger.warning("Telemetry enabled but OTLP HTTP exporter is unavailable")
            self._state = TelemetryState(active=False, reason="exporter_unavailable")
            return self._state

        resource = Resource.create({
            "service.name": config.service_name,
            "service.version": config.service_version,
            "deployment.environment": config.environment,
        })

        try:
            span_exporter = OTLPSpanExporter(
                endpoint=config.endpoint,
                timeout=config.export_timeout_ms / 1000,
                headers=config.exporter_headers(),
            )
        except Exception:  # noqa: BLE001 - exporter construction must fail open
            logger.warning("Telemetry enabled but the span exporter could not be created")
            self._state = TelemetryState(active=False, reason="exporter_unavailable")
            return self._state

        provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(TraceIdRatioBased(config.sample_ratio)),
        )
        provider.add_span_processor(BatchSpanProcessor(span_exporter))
        trace.set_tracer_provider(provider)

        meter_provider, metrics_reason = self._configure_metrics(config, resource)
        self._state = TelemetryState(
            active=True,
            reason="enabled",
            tracer_provider=provider,
            meter_provider=meter_provider,
            metrics_active=meter_provider is not None,
            metrics_reason=metrics_reason,
        )
        return self._state

    @staticmethod
    def _configure_metrics(config: TelemetryConfig, resource: Any) -> tuple[Any | None, str]:
        """Build the OTLP metrics pipeline, degrading independently of traces.

        A missing metrics exporter package or an exporter that refuses to
        construct must not disable tracing or block startup. The returned reason
        is logged and exposed on ``TelemetryState`` so "metrics are active" is
        only claimed when a real reader is attached.
        """
        try:
            from opentelemetry import metrics as metrics_api
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                OTLPMetricExporter,
            )
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        except ImportError:
            logger.warning("Telemetry enabled but the OTLP metrics SDK is unavailable")
            return None, "metrics_sdk_unavailable"

        try:
            exporter = OTLPMetricExporter(
                endpoint=config.resolved_metrics_endpoint(),
                timeout=config.export_timeout_ms / 1000,
                headers=config.exporter_headers(),
            )
            reader = PeriodicExportingMetricReader(
                exporter,
                export_timeout_millis=config.export_timeout_ms,
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        except Exception:  # noqa: BLE001 - a metrics failure must not block startup
            logger.warning("Telemetry enabled but the metrics exporter could not be created")
            return None, "metrics_exporter_unavailable"

        metrics_api.set_meter_provider(meter_provider)
        return meter_provider, "enabled"

    def shutdown(self) -> None:
        """Flush and stop every exporter.

        The wait is bounded by the export timeout configured on each exporter
        (``TelemetryConfig.export_timeout_ms``), so a hung collector cannot stall
        process exit. Exporter errors are logged and swallowed: shutdown must
        never raise.
        """
        providers = (self._state.tracer_provider, self._state.meter_provider)
        for provider in providers:
            if provider is None:
                continue
            try:
                provider.shutdown()
            except Exception:  # noqa: BLE001 - shutdown must never raise
                logger.warning("Telemetry shutdown failed; continuing")
        self._state = TelemetryState(active=False, reason="shutdown")

    @staticmethod
    def extract_context(carrier: Mapping[str, str]) -> Any:
        """Extract W3C trace context from inbound headers, or None without the SDK.

        Propagation is best-effort: a malformed or absent ``traceparent`` simply
        produces a new root trace, and a missing OpenTelemetry install must not
        affect the request.
        """
        try:
            from opentelemetry import propagate
        except ImportError:
            return None
        return propagate.extract(carrier)

    @contextmanager
    def span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        *,
        parent: Any = None,
    ) -> Generator[Any]:
        """Start a span if telemetry is active, otherwise yield None.

        The provider is read from ``TelemetryState`` rather than the process-wide
        global. OpenTelemetry only allows the global tracer provider to be set
        once, which makes repeated ``configure()`` calls (tests, app factories,
        autoreload) silently attach to a stale provider. Using the instance we
        just built keeps spans on the provider whose exporter and shutdown
        lifecycle we own.
        """
        provider = self._state.tracer_provider
        if not self._state.active or provider is None:
            yield None
            return

        tracer = provider.get_tracer("waxprep")
        with tracer.start_as_current_span(name, context=parent) as current:
            for key, value in (attributes or {}).items():
                current.set_attribute(key, value)
            yield current

    @staticmethod
    def current_ids() -> dict[str, str]:
        """Return ``trace_id``/``span_id`` for log correlation, if any."""
        try:
            from opentelemetry import trace
        except ImportError:
            return {}
        span = trace.get_current_span()
        context = span.get_span_context()
        if not context or not context.is_valid:
            return {}
        return {
            "trace_id": format(context.trace_id, "032x"),
            "span_id": format(context.span_id, "016x"),
        }


# Process-wide telemetry handle. Wiring happens once in the composition root.
telemetry = Telemetry()
