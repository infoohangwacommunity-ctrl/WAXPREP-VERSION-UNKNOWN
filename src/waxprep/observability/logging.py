"""
Logging Infrastructure - Stage 13

One logging contract for the whole process. Logging is configured once, from
validated settings, by an explicit call - never as an import side effect - so
CLI entry points, tests, and future workers all share the same behaviour.

Event schema (JSON in deployed environments):
    timestamp        UTC ISO-8601
    level            DEBUG | INFO | WARNING | ERROR | CRITICAL
    event            stable event name
    service.name     WaxPrep service identity
    service.version  release version
    deployment.environment
    request_id       application correlation id, when bound
    trace_id / span_id  when an active span exists
    error.code / error.category  bounded failure identity, when applicable

Redaction is a processor in the chain, so a secret is scrubbed *before* it
reaches stdout or an exporter. There is no second, unredacted path.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from waxprep.secrets.redaction import redact

_configured = False

# Third-party loggers that are noisy at INFO and add no operational value.
_NOISY_LOGGERS = ("uvicorn.access", "httpx", "httpcore")


def _add_redaction(
    _logger: Any,
    _method: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    """Scrub secrets from every event before it is rendered or exported."""
    scrubbed = redact(dict(event_dict))
    return scrubbed if isinstance(scrubbed, dict) else {}


def _add_service_context(
    service_name: str,
    service_version: str,
    environment: str,
) -> Any:
    """Build a processor that stamps stable service identity onto every event."""

    def processor(
        _logger: Any,
        _method: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        event_dict.setdefault("service.name", service_name)
        event_dict.setdefault("service.version", service_version)
        event_dict.setdefault("deployment.environment", environment)
        return event_dict

    return processor


def configure_logging(
    *,
    level: str = "INFO",
    json_output: bool = True,
    service_name: str = "waxprep",
    service_version: str = "0.1.0",
    environment: str = "development",
) -> None:
    """Configure structlog and the stdlib root logger. Safe to call repeatedly.

    Repeated calls (tests, app factories, reloads) reconfigure in place rather
    than stacking handlers, which would duplicate every event.
    """
    global _configured

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    # Route structlog through the stdlib so third-party and application logs
    # share one handler, one level, and one output stream.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=numeric_level,
        force=True,
    )
    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_service_context(service_name, service_version, environment),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _add_redaction,
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        cache_logger_on_first_use=False,
    )
    _configured = True


def is_configured() -> bool:
    """Return True once configure_logging() has run in this process."""
    return _configured
