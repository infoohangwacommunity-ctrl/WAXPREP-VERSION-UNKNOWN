"""
Main Application - Stages 01-03
ASGI application with ordered startup, graceful shutdown, health endpoints.
NO tutor logic. NO real adapters. Foundation + core integration point.

Includes:
- Request correlation ID middleware
- Global exception handlers
- Meaningful readiness checks
- Structured logging with structlog
- Composition root for Stage 03 services (when added)
"""

import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from waxprep.config import settings
from waxprep.middleware.request_id import RequestIdMiddleware


# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
logger = structlog.get_logger()


# Global state
_app: Optional[FastAPI] = None
_shutting_down: bool = False
_registries_ready: bool = False
_channel_registry: Optional[object] = None
_model_registry: Optional[object] = None
_tool_registry: Optional[object] = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Ordered startup sequence - Stage 02
    1. Load configuration
    2. Initialize registries (explicit registration)
    3. Initialize external clients (none in Stages 01-02)
    4. Start background services (none in Stages 01-02)
    5. Log startup
    """
    global _shutting_down, _registries_ready, _channel_registry, _model_registry, _tool_registry
    _shutting_down = False

    # 1. Load configuration (already done via settings)
    logger.info("Stage 02: Configuration loaded")

    # 2. Initialize registries with explicit registration
    from waxprep.registries.channel import get_channel_registry
    from waxprep.registries.model import get_model_registry
    from waxprep.registries.tool import get_tool_registry
    
    _channel_registry = get_channel_registry()
    _model_registry = get_model_registry()
    _tool_registry = get_tool_registry()
    
    # Explicit registration - proves no import-time side effects
    _channel_registry.register_defaults()
    _model_registry.register_defaults()
    _tool_registry.register_defaults()
    
    _registries_ready = True
    
    logger.info("Stage 02: Registries initialized")
    logger.info(f"  Channels: {_channel_registry.list_all()}")
    logger.info(f"  Models: {_model_registry.list_all()}")
    logger.info(f"  Tools: {_tool_registry.list_all()}")

    # 3. External clients - none in Stages 01-02
    logger.info("Stage 02: No external clients (Stages 01-02 only)")

    # 4. Background services - none in Stages 01-02
    logger.info("Stage 02: No background services (Stages 01-02 only)")

    # 5. Log startup
    logger.info("Stage 02: Startup complete", 
                environment=settings.environment,
                host=settings.host,
                port=settings.port)

    yield

    # Shutdown sequence
    _shutting_down = True
    _registries_ready = False
    _channel_registry = None
    _model_registry = None
    _tool_registry = None
    logger.info("Stage 02: Shutdown started")
    logger.info("Stage 02: Shutdown complete")


# Create FastAPI app
_app = FastAPI(
    title="WaxPrep Foundation",
    description="Stages 01-02 ONLY - Foundation",
    version="0.1.0",
    lifespan=lifespan,
)

# Add request correlation ID middleware
_app.add_middleware(RequestIdMiddleware)


# Exception handlers
@_app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle HTTP exceptions without leaking internals."""
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail if exc.detail else "HTTP error",
            "path": request.url.path,
        },
    )


@_app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with sanitized output."""
    logger.warning(
        "Validation error",
        path=request.url.path,
        error_count=len(exc.errors()),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()],
        },
    )


@_app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions - log full details, return sanitized response."""
    logger.exception(
        "Unhandled exception",
        path=request.url.path,
        exc_type=type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": "An unexpected error occurred",
        },
    )


# Health endpoints
@_app.get("/health/liveness")
async def liveness() -> JSONResponse:
    """Liveness endpoint - Is the process alive?"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "alive"},
    )


@_app.get("/health/readiness")
async def readiness() -> JSONResponse:
    """Readiness endpoint - Is the application ready?
    
    Checks:
    - Configuration is loaded
    - Registries are initialized
    - Default adapters are registered
    
    Liveness != Readiness. This proves the distinction.
    """
    global _channel_registry, _model_registry, _tool_registry
    
    # Check configuration
    if not settings.environment:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "configuration_not_loaded"},
        )
    
    # Check registries are initialized
    if not _registries_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "registries_not_initialized"},
        )
    
    # Verify default adapters registered using stored instances
    if _channel_registry is None or not _channel_registry.is_registered("fake"):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "channel_registry_not_initialized"},
        )
    
    if _model_registry is None or not _model_registry.is_registered("fake"):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "model_registry_not_initialized"},
        )
    
    if _tool_registry is None or not _tool_registry.is_registered("fake_tool"):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "tool_registry_not_initialized"},
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ready",
            "checks": {
                "configuration": "ok",
                "channel_registry": "ok",
                "model_registry": "ok",
                "tool_registry": "ok",
                "correlation_id_middleware": "active",
            }
        },
    )


# Graceful shutdown handler
def handle_shutdown(signum: int, frame: object) -> None:
    """Handle SIGTERM for graceful shutdown."""
    global _shutting_down
    if _shutting_down:
        return
    
    _shutting_down = True
    logger.info("SIGTERM received - graceful shutdown initiated")
    
    # In a real ASGI server, this would trigger the lifespan shutdown
    # For now, we just log and exit
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


# Root endpoint
@_app.get("/")
async def root() -> JSONResponse:
    """Root endpoint - proves the app is running."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "WaxPrep Foundation - Stages 01-02 ONLY",
            "stages": ["01", "02"],
            "status": "running",
        },
    )


# Get the app (for uvicorn)
def get_app() -> FastAPI:
    """ASGI entry point for uvicorn.
    
    Uvicorn imports this as "waxprep.main:get_app" — a string reference
    that expects a callable returning the FastAPI app instance.
    """
    return _app


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "waxprep.main:get_app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_config=None,  # structlog handles logging
    )
