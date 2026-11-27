"""
Metrics - Stage 14

A small catalogue built on the four golden signals, limited to operations that
actually exist today: HTTP request count/duration, bounded error counts, and
readiness outcomes.

Instrument selection is lazy: if OpenTelemetry is unavailable the recorders
become no-ops rather than crashing a request. Labels are bounded by the
normalisers in ``telemetry.py``.
"""

from __future__ import annotations

from typing import Any

from waxprep.observability.telemetry import normalize_method, status_class


class _NullInstrument:
    """Stand-in used when telemetry is inactive; every call is a no-op."""

    def add(self, _amount: float, _attributes: dict[str, Any] | None = None) -> None:
        return None

    def record(self, _value: float, _attributes: dict[str, Any] | None = None) -> None:
        return None


null_instrument = _NullInstrument()


class Metrics:
    """Holds the instrument handles resolved at startup."""

    def __init__(self) -> None:
        self.request_count: Any = null_instrument
        self.request_duration: Any = null_instrument
        self.error_count: Any = null_instrument
        self.readiness_checks: Any = null_instrument
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def reset(self) -> None:
        """Drop instrument handles after their provider has shut down.

        OpenTelemetry instruments are bound to a provider. Keeping references to
        a shut-down provider after lifecycle shutdown would make later recording
        silently fail (or, worse, look active while exporting nowhere). Resetting
        restores the documented no-op state until the next successful configure.
        """
        self.request_count = null_instrument
        self.request_duration = null_instrument
        self.error_count = null_instrument
        self.readiness_checks = null_instrument
        self._active = False

    def configure(self, *, service_name: str = "waxprep", meter_provider: Any = None) -> bool:
        """Resolve instruments from an exporting meter provider.

        ``meter_provider`` is the provider built by ``Telemetry.configure()``.
        Passing it explicitly guarantees the instruments are attached to the
        reader that will actually export them; the global meter provider is only
        a fallback for callers that built their own pipeline.

        Returns False (and stays no-op) when the SDK is not installed.
        """
        try:
            from opentelemetry import metrics as otel_metrics
        except ImportError:
            self._active = False
            return False

        meter = (
            meter_provider.get_meter(service_name)
            if meter_provider is not None
            else otel_metrics.get_meter(service_name)
        )
        self.request_count = meter.create_counter(
            name="http.server.request.count",
            description="Number of HTTP requests handled",
            unit="1",
        )
        self.request_duration = meter.create_histogram(
            name="http.server.request.duration",
            description="HTTP request duration",
            unit="ms",
        )
        self.error_count = meter.create_counter(
            name="waxprep.error.count",
            description="Failures by bounded error category",
            unit="1",
        )
        self.readiness_checks = meter.create_counter(
            name="waxprep.readiness.count",
            description="Readiness probe outcomes",
            unit="1",
        )
        self._active = True
        return True

    def record_request(
        self,
        *,
        method: str,
        route: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        """Record one finished request using bounded labels only."""
        attributes = {
            "http.request.method": normalize_method(method),
            "http.route": route,
            "http.response.status_class": status_class(status_code),
        }
        self.request_count.add(1, attributes)
        self.request_duration.record(duration_ms, attributes)

    def record_error(self, *, category: str, code: str) -> None:
        """Record one failure by category and stable code."""
        self.error_count.add(1, {"error.category": category, "error.code": code})

    def record_readiness(self, *, ready: bool) -> None:
        """Record a readiness outcome."""
        self.readiness_checks.add(1, {"outcome": "ready" if ready else "not_ready"})


metrics = Metrics()
