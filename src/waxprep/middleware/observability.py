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
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from waxprep.observability.metrics import metrics
from waxprep.observability.telemetry import (
    normalize_method,
    route_template,
    status_class,
    telemetry,
)

logger = structlog.get_logger()


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Create a request span, record duration/metrics, and bind trace context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        started = time.perf_counter()
        # Continue an inbound W3C trace when one is present; otherwise this is
        # a new root trace. One request-span boundary is created here (outside
        # routing) so the whole request, including the response, is covered.
        # Attributes come from bounded values only: method, route, status class.
        parent = telemetry.extract_context(request.headers)
        with telemetry.span(
            "http.server.request",
            {"http.request.method": normalize_method(request.method)},
            parent=parent,
        ) as span:
            trace_ids = telemetry.current_ids()
            if trace_ids:
                structlog.contextvars.bind_contextvars(**trace_ids)

            status_code = 500
            try:
                response = await call_next(request)
                status_code = response.status_code
                return response
            finally:
                if span is not None:
                    self._annotate_span(span, request, status_code)
                duration_ms = (time.perf_counter() - started) * 1000
                self._record(request, status_code, duration_ms)
                if trace_ids:
                    structlog.contextvars.unbind_contextvars(*trace_ids)

    @staticmethod
    def _safe_route(request: Request) -> str:
        """Return the matched route template, or a fixed safe label."""
        # Starlette records the matched route on the scope during routing, so
        # this is the template (``/students/{id}``), never the raw path.
        matched = request.scope.get("route")
        matched_path = getattr(matched, "path", None)
        return route_template(request.url.path, matched_path)

    def _annotate_span(self, span: Any, request: Request, status_code: int) -> None:
        """Attach bounded attributes to the request span, never raising."""
        try:
            span.set_attribute("http.response.status_class", status_class(status_code))
            span.set_attribute("http.route", self._safe_route(request))
        except Exception:  # noqa: BLE001 - observability must never break a request
            logger.warning("observability_span_failed", exc_info=True)

    @classmethod
    def _record(cls, request: Request, status_code: int, duration_ms: float) -> None:
        """Emit metrics, never raising into the request path."""
        try:
            metrics.record_request(
                method=request.method,
                route=cls._safe_route(request),
                status_code=status_code,
                duration_ms=duration_ms,
            )
        except Exception:  # noqa: BLE001 - observability must never break a request
            logger.warning("observability_metric_failed", exc_info=True)
