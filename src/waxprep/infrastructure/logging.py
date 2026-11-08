"""
Logging Configuration - Stage 03
Structured logging configuration for the application.

Dependency Rule: This module may import domain/ and application/.
It may NOT import adapters/.
"""

import logging
from typing import Any

import structlog

from waxprep.infrastructure.config import get_settings


def configure_logging() -> None:
    """Configure structured logging for the application.

    This sets up structlog with the configured format and level.
    It should be called once at application startup.
    """
    config = get_settings()

    # Define processors based on format
    if config.log_format == "json":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ]
    elif config.log_format == "console":
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ]
    else:  # text
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set the log level for all loggers
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(level=log_level)

    # Configure standard logging to use structlog
    structlog.stdlib.install_logger_factory()


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger with the given name.

    Args:
        name: The logger name. If None, uses the calling module's name.

    Returns:
        A bound structlog logger
    """
    if name is None:
        # Try to get the calling module's name
        import inspect

        frame = inspect.currentframe()
        try:
            caller_frame = frame.f_back if frame else None
            if caller_frame:
                module = inspect.getmodule(caller_frame)
                name = module.__name__ if module else "waxprep"
            else:
                name = "waxprep"
        finally:
            del frame

    return structlog.get_logger(name)


class LogContext:
    """Context manager for adding structured logging context."""

    def __init__(self, logger: structlog.BoundLogger, **context: Any) -> None:
        self.logger = logger
        self.context = context

    def __enter__(self) -> structlog.BoundLogger:
        return self.logger.bind(**self.context)

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass


def with_context(logger: structlog.BoundLogger, **context: Any) -> LogContext:
    """Create a context manager for adding logging context.

    Usage:
        logger = get_logger()
        with with_context(logger, user_id="123", action="login"):
            logger.info("User logged in")
    """
    return LogContext(logger, **context)
