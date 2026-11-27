"""
Observability Middleware - Stages 13-14

Times every request, binds trace/span IDs into the logging context, and records
bounded metrics. It runs *outside* the request-ID middleware's concerns and adds
no new correlation identifier of its own.

The middleware is deliberately fail-open: any telemetry problem is logged and
swallowed so an observability outage can never turn a healthy request into a
500.
"""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from waxprep.observability.metrics import metrics
from waxprep.observability.telemetry import route_template, telemetry

logger = structlog.get_logger()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Record duration/metrics and bind trace context for the request lifetime."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        trace_ids = telemetry.current_ids()
        if trace_ids:
            structlog.contextvars.bind_contextvars(**trace_ids)

        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            self._record(request, status_code, duration_ms)
            if trace_ids:
                structlog.contextvars.unbind_contextvars(*trace_ids)

    @staticmethod
    def _record(request: Request, status_code: int, duration_ms: float) -> None:
        """Emit metrics, never raising into the request path."""
        try:
            # Starlette records the matched route on the scope during routing,
            # so this is the template (``/students/{id}``), never the raw path.
            matched = request.scope.get("route")
            matched_path = getattr(matched, "path", None)
            metrics.record_request(
                method=request.method,
                route=route_template(request.url.path, matched_path),
                status_code=status_code,
                duration_ms=duration_ms,
            )
        except Exception:  # noqa: BLE001 - observability must never break a request
            logger.warning("observability_metric_failed", exc_info=True)
