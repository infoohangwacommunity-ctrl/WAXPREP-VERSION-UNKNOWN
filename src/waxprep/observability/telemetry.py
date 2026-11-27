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
from collections.abc import Generator
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
    service_name: str = "waxprep"
    service_version: str = "0.1.0"
    environment: str = "development"
    sample_ratio: float = 1.0
    export_timeout_ms: int = 5000
    extra: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Reject impossible configuration before any exporter is built."""
        if not 0.0 <= self.sample_ratio <= 1.0:
            raise ValueError("sample_ratio must be between 0 and 1")
        if self.export_timeout_ms <= 0:
            raise ValueError("export_timeout_ms must be positive")
        if self.enabled and not self.endpoint:
            raise ValueError("telemetry is enabled but no OTLP endpoint is configured")


@dataclass(slots=True)
class TelemetryState:
    """Outcome of a startup attempt, readable by readiness and diagnostics."""

    active: bool = False
    reason: str = "disabled"
    tracer_provider: Any = None
    meter_provider: Any = None

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
        provider = TracerProvider(
            resource=resource,
            sampler=ParentBased(TraceIdRatioBased(config.sample_ratio)),
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=config.endpoint,
                    timeout=config.export_timeout_ms / 1000,
                )
            )
        )
        trace.set_tracer_provider(provider)
        self._state = TelemetryState(active=True, reason="enabled", tracer_provider=provider)
        return self._state

    def shutdown(self) -> None:
        """Flush and stop exporters.

        The wait is bounded by the export timeout configured on the
        ``BatchSpanProcessor`` (``TelemetryConfig.export_timeout_ms``), so a hung
        collector cannot stall process exit. Exporter errors are logged and
        swallowed: shutdown must never raise.
        """
        provider = self._state.tracer_provider
        if provider is None:
            return
        try:
            provider.shutdown()
        except Exception:  # noqa: BLE001 - shutdown must never raise
            logger.warning("Telemetry shutdown failed; continuing")
        finally:
            self._state = TelemetryState(active=False, reason="shutdown")

    @contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Generator[Any]:
        """Start a span if telemetry is active, otherwise yield None."""
        if not self._state.active:
            yield None
            return
        from opentelemetry import trace

        tracer = trace.get_tracer("waxprep")
        with tracer.start_as_current_span(name) as current:
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
