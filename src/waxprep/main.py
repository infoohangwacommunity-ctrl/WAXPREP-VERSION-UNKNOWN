"""
Main Application - Stages 01-07
ASGI application with ordered startup, graceful shutdown, health endpoints.

Includes:
- Request correlation ID middleware
- Global exception handlers
- Meaningful readiness checks
- Structured logging with structlog
- Composition root for Stage 03 services (when added)
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import cast

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from waxprep.config import settings
from waxprep.middleware.request_id import RequestIdMiddleware
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry

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


# Application state container - isolates lifecycle state per app instance
class AppState:
    """Application lifecycle state - not module-global."""

    def __init__(self) -> None:
        self._shutting_down: bool = False
        self._registries_ready: bool = False
        self._channel_registry: ChannelRegistry | None = None
        self._model_registry: ModelRegistry | None = None
        self._tool_registry: ToolRegistry | None = None

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down

    @shutting_down.setter
    def shutting_down(self, value: bool) -> None:
        self._shutting_down = value

    @property
    def registries_ready(self) -> bool:
        return self._registries_ready

    @registries_ready.setter
    def registries_ready(self, value: bool) -> None:
        self._registries_ready = value

    @property
    def channel_registry(self) -> ChannelRegistry | None:
        return self._channel_registry

    @channel_registry.setter
    def channel_registry(self, value: ChannelRegistry | None) -> None:
        self._channel_registry = value

    @property
    def model_registry(self) -> ModelRegistry | None:
        return self._model_registry

    @model_registry.setter
    def model_registry(self, value: ModelRegistry | None) -> None:
        self._model_registry = value

    @property
    def tool_registry(self) -> ToolRegistry | None:
        return self._tool_registry

    @tool_registry.setter
    def tool_registry(self, value: ToolRegistry | None) -> None:
        self._tool_registry = value


# Single application instance state
_app_state = AppState()
_app: FastAPI | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:  # noqa: V107
    """
    Ordered startup sequence - Stages 01-04
    1. Load configuration
    2. Initialize registries (explicit registration)
    3. Initialize external clients (none in foundation stage)
    4. Start background services (none in foundation stage)
    5. Log startup
    """
    _app_state.shutting_down = False

    # 1. Load configuration (already done via settings)
    logger.info("Configuration loaded")

    # 2. Initialize registries with explicit registration
    from waxprep.registries.channel import get_channel_registry
    from waxprep.registries.model import get_model_registry
    from waxprep.registries.tool import get_tool_registry

    _app_state.channel_registry = get_channel_registry()
    _app_state.model_registry = get_model_registry()
    _app_state.tool_registry = get_tool_registry()

    # Explicit registration - proves no import-time side effects
    _app_state.channel_registry.register_defaults()
    _app_state.model_registry.register_defaults()
    _app_state.tool_registry.register_defaults()

    _app_state.registries_ready = True

    logger.info("Registries initialized")
    logger.info(f"  Channels: {_app_state.channel_registry.list_all()}")
    logger.info(f"  Models: {_app_state.model_registry.list_all()}")
    logger.info(f"  Tools: {_app_state.tool_registry.list_all()}")

    # 3. External clients - none in foundation stage
    logger.info("No external clients (foundation stage)")

    # 4. Background services - none in foundation stage
    logger.info("No background services (foundation stage)")

    # 5. Log startup
    logger.info(
        "Startup complete", environment=settings.environment, host=settings.host, port=settings.port
    )

    yield

    # Shutdown sequence
    _app_state.shutting_down = True
    _app_state.registries_ready = False
    _app_state.channel_registry = None
    _app_state.model_registry = None
    _app_state.tool_registry = None
    logger.info("Shutdown started")
    logger.info("Shutdown complete")


# Create FastAPI app
_app = FastAPI(
    title="WaxPrep Foundation",
    description="WaxPrep Foundation - ASGI application with health endpoints, registries, and structured logging",
    version="0.1.0",
    lifespan=lifespan,
)

# Add request correlation ID middleware
_app.add_middleware(RequestIdMiddleware)


# Exception handlers
@_app.exception_handler(StarletteHTTPException)  # type: ignore[untyped-decorator]
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:  # noqa: RUF029
    """Handle HTTP exceptions with sanitized output.

    Returns safe error responses. Does not expose internal exception details
    that may originate from services, providers, or databases.
    """
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        path=request.url.path,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": "HTTP error",
            "path": request.url.path,
        },
    )


@_app.exception_handler(RequestValidationError)  # type: ignore[untyped-decorator]
async def validation_exception_handler(  # noqa: RUF029
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with sanitized output.

    Uses 422 (Unprocessable Content) per RFC 9110 — signals semantic/
    validation failure rather than generic bad request (400). This is the
    standard status for Pydantic/FastAPI validation errors.
    """
    logger.warning(
        "Validation error",
        path=request.url.path,
        error_count=len(exc.errors()),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "Validation error",
            "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()],
        },
    )


@_app.exception_handler(Exception)  # type: ignore[untyped-decorator]
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: RUF029
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
@_app.get("/health/liveness")  # type: ignore[untyped-decorator]
async def liveness() -> JSONResponse:  # noqa: RUF029
    """Liveness endpoint - Is the process alive?"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "alive"},
    )


@_app.get("/health/readiness")  # type: ignore[untyped-decorator]
async def readiness() -> JSONResponse:
    """Readiness endpoint - Is the application ready?

    Checks:
    - Configuration is loaded
    - Registries are initialized
    - Default adapters are registered

    Liveness != Readiness. This proves the distinction.
    """
    # Check configuration exists and has a non-empty environment field
    if not settings.environment:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "configuration_not_loaded"},
        )

    # Check registries are initialized via app state
    if not _app_state.registries_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "registries_not_initialized"},
        )

    # Verify default adapters registered using stored instances
    if _app_state.channel_registry is None or not _app_state.channel_registry.is_registered("fake"):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "channel_registry_not_initialized"},
        )

    if _app_state.model_registry is None or not _app_state.model_registry.is_registered("fake"):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "model_registry_not_initialized"},
        )

    if _app_state.tool_registry is None or not _app_state.tool_registry.is_registered("fake_tool"):
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
            },
        },
    )


# Root endpoint
@_app.get("/")  # type: ignore[untyped-decorator]
async def root() -> JSONResponse:  # noqa: RUF029
    """Root endpoint - proves the app is running."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": "WaxPrep Foundation",
            "version": "0.1.0",
            "status": "running",
        },
    )


# Get the app (for uvicorn)
def get_app() -> FastAPI:
    """ASGI entry point for uvicorn.

    Uvicorn imports this as "waxprep.main:get_app" — a string reference
    that expects a callable returning the FastAPI app instance.
    """
    return cast(FastAPI, _app)


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "waxprep.main:get_app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_config=None,  # structlog handles logging
        interface="asgi3",
    )
