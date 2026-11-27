"""
Main Application - Stages 01-08
ASGI application with ordered startup, graceful shutdown, health endpoints.

Includes:
- Request correlation ID middleware
- Global exception handlers
- Meaningful readiness checks
- Structured logging with structlog
- Composition root for Stage 03 services (when added)

Application state is held in module-level singletons (_app_state, _app)
for the single-process ASGI deployment model. The AppState class itself
is not a module-global — it is instantiated once and referenced by name.
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
from waxprep.errors.http import public_body, status_for
from waxprep.errors.taxonomy import ErrorCategory, ProgrammingDefectError, WaxPrepError
from waxprep.middleware.observability import ObservabilityMiddleware
from waxprep.middleware.request_id import RequestIdMiddleware
from waxprep.observability.logging import configure_logging
from waxprep.observability.metrics import metrics
from waxprep.observability.telemetry import TelemetryConfig, route_template, telemetry
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry

# Logging is configured once from validated settings (Stage 13). This is an
# explicit call rather than an import side effect so CLI entry points, tests
# and future workers share one contract.
configure_logging(
    level=settings.log_level.value,
    json_output=settings.log_json,
    service_version="0.1.0",
    environment=settings.environment.value,
)
logger = structlog.get_logger()

# Bounded readiness reasons. Named constants keep the vocabulary in one place
# and avoid a stray literal becoming a new response value.
READINESS_CONFIGURATION_NOT_LOADED = "configuration_not_loaded"
READINESS_REGISTRIES_NOT_INITIALIZED = "registries_not_initialized"
READINESS_CHANNEL_NOT_INITIALIZED = "channel_registry_not_initialized"
READINESS_MODEL_NOT_INITIALIZED = "model_registry_not_initialized"
READINESS_TOOL_NOT_INITIALIZED = "tool_registry_not_initialized"


def _route_label(request: Request) -> str:
    """Return a log-safe route label: the matched template or ``unmatched``.

    Raw paths can embed identifiers (phone numbers, conversation IDs). Logs use
    the route template the application actually matched, never the raw path.
    """
    matched = request.scope.get("route")
    matched_path = getattr(matched, "path", None)
    return route_template(request.url.path, matched_path)


def _telemetry_auth_token() -> str | None:
    """Reveal the configured exporter credential at its single point of use."""
    token = settings.telemetry_auth_token
    return token.get_secret_value() if token is not None else None


def _record_error_metric(category: str, code: str) -> None:
    """Record one bounded error metric; observability never breaks a response."""
    try:
        metrics.record_error(category=category, code=code)
    except Exception:  # noqa: BLE001 - a metrics outage must not mask the error
        logger.warning("observability_metric_failed", exc_info=True)


def _record_readiness_metric(*, ready: bool) -> None:
    """Record one readiness outcome; observability never breaks a probe."""
    try:
        metrics.record_readiness(ready=ready)
    except Exception:  # noqa: BLE001 - a metrics outage must not mask readiness
        logger.warning("observability_metric_failed", exc_info=True)


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

    # 1. Load configuration (already done via settings singleton)
    logger.info(
        "Configuration loaded",
        environment=settings.environment.value,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.value,
    )

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

    # Stage 14: telemetry is optional and must never block startup. A disabled
    # or unconfigured exporter degrades to a no-op with a logged reason.
    telemetry_state = telemetry.configure(
        TelemetryConfig(
            enabled=settings.telemetry_enabled,
            endpoint=settings.telemetry_endpoint,
            metrics_endpoint=settings.telemetry_metrics_endpoint,
            service_version="0.1.0",
            environment=settings.environment.value,
            sample_ratio=settings.telemetry_sample_ratio,
            auth_token=_telemetry_auth_token(),
        )
    )
    metrics_active = False
    if telemetry_state.active and telemetry_state.metrics_active:
        # Only bind instruments when a real exporting meter provider exists;
        # otherwise they would attach to a no-op/global provider and lie.
        metrics_active = metrics.configure(meter_provider=telemetry_state.meter_provider)
    logger.info(
        "telemetry_configured",
        active=telemetry_state.active,
        reason=telemetry_state.reason,
        metrics_active=metrics_active,
        metrics_reason=telemetry_state.metrics_reason,
    )

    logger.info("Registries initialized")
    logger.info(f"  Channels: {_app_state.channel_registry.list_all()}")
    logger.info(f"  Models: {_app_state.model_registry.list_all()}")
    logger.info(f"  Tools: {_app_state.tool_registry.list_all()}")

    # 3. External clients - none in foundation stage
    logger.info("No external clients (foundation stage)")

    # 4. Background services - none in foundation stage
    logger.info("No background services (foundation stage)")

    # 5. Log startup (without exposing secrets)
    logger.info(
        "Startup complete",
        environment=settings.environment.value,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.value,
    )

    yield

    # Shutdown sequence
    _app_state.shutting_down = True
    _app_state.registries_ready = False
    _app_state.channel_registry = None
    _app_state.model_registry = None
    _app_state.tool_registry = None
    logger.info("Shutdown started")
    telemetry.shutdown()
    logger.info("Shutdown complete")


# Create FastAPI app.
# FastAPI ships its own OpenTelemetry integration that activates automatically
# once a global provider is configured. WaxPrep owns its request span and metric
# catalogue (see ObservabilityMiddleware), so the native integration is disabled:
# otherwise every request would produce two spans and a second metric stream
# named ``http.server.request.duration`` with a different unit.
_app = FastAPI(
    title="WaxPrep Foundation",
    description="WaxPrep Foundation - ASGI application with health endpoints, registries, and structured logging",
    version="0.1.0",
    lifespan=lifespan,
    telemetry={
        "tracing": False,
        "metrics": False,
        "logs": False,
        "operation_spans": False,
    },
)

# Add request correlation ID middleware
_app.add_middleware(RequestIdMiddleware)
# Observability runs outermost so it times the full request
_app.add_middleware(ObservabilityMiddleware)


# Exception handlers
@_app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:  # noqa: RUF029
    """Handle HTTP exceptions with sanitized output.

    Returns safe error responses. Does not expose internal exception details
    that may originate from services, providers, or databases.
    """
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        route=_route_label(request),
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": "HTTP error",
            "path": request.url.path,
        },
    )


@_app.exception_handler(RequestValidationError)
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
        route=_route_label(request),
        error_count=len(exc.errors()),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": "Validation error",
            "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()],
        },
    )


@_app.exception_handler(WaxPrepError)
async def waxprep_error_handler(request: Request, exc: WaxPrepError) -> JSONResponse:  # noqa: RUF029
    """Translate a typed WaxPrep error into a safe public response.

    This is the single authoritative reporting point for application failures:
    it logs once, records one bounded metric, and never leaks internals.
    """
    status_code = status_for(exc.category)
    route = _route_label(request)
    if status_code >= 500:
        logger.error("request_failed", route=route, **exc.to_fields())
    else:
        logger.warning("request_rejected", route=route, **exc.to_fields())
    # Deliberate cancellation is expected during shutdown and is not a failure.
    if exc.category is not ErrorCategory.CANCELLATION:
        _record_error_metric(str(exc.category), exc.code)
    return JSONResponse(status_code=status_code, content=public_body(exc))


@_app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: RUF029
    """Handle unexpected exceptions - log full details, return sanitized response."""
    logger.exception(
        "Unhandled exception",
        route=_route_label(request),
        exc_type=type(exc).__name__,
    )
    _record_error_metric(
        str(ProgrammingDefectError.category),
        ProgrammingDefectError.code,
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
async def liveness() -> JSONResponse:  # noqa: RUF029
    """Liveness endpoint - Is the process alive?"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "alive"},
    )


def _readiness_failure_reason() -> str | None:
    """Return the first failed readiness precondition, or None when ready.

    Kept separate from the endpoint so the metric records exactly one outcome
    per probe with the same decision that produced the HTTP response.
    """
    # Accumulate into one variable rather than returning literals: a single
    # exit point keeps the metric and the HTTP response using the same decision.
    reason: str | None = None

    # Check configuration exists and has a recognised environment
    try:
        env_value = settings.environment.value
    except AttributeError:
        env_value = None

    if not env_value:
        reason = READINESS_CONFIGURATION_NOT_LOADED
    elif not _app_state.registries_ready:
        # Check registries are initialized via app state
        reason = READINESS_REGISTRIES_NOT_INITIALIZED
    elif _app_state.channel_registry is None or not _app_state.channel_registry.is_registered(
        "fake"
    ):
        # Verify default adapters registered using stored instances
        reason = READINESS_CHANNEL_NOT_INITIALIZED
    elif _app_state.model_registry is None or not _app_state.model_registry.is_registered("fake"):
        reason = READINESS_MODEL_NOT_INITIALIZED
    elif _app_state.tool_registry is None or not _app_state.tool_registry.is_registered(
        "fake_tool"
    ):
        reason = READINESS_TOOL_NOT_INITIALIZED

    return reason


@_app.get("/health/readiness")
async def readiness() -> JSONResponse:
    """Readiness endpoint - Is the application ready?

    Checks:
    - Configuration is loaded
    - Registries are initialized
    - Default adapters are registered

    Liveness != Readiness. This proves the distinction.
    """
    failure = _readiness_failure_reason()
    if failure is not None:
        _record_readiness_metric(ready=False)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": failure},
        )

    _record_readiness_metric(ready=True)
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
@_app.get("/")
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


def run() -> None:
    """Canonical application entrypoint.

    Starts Uvicorn on the validated ``settings.host`` and ``settings.port`` so
    that ``WAXPREP_HOST`` and ``WAXPREP_PORT`` always control the actual
    listening address. Prefer this entrypoint (``python -m waxprep.main`` or
    the ``waxprep`` console script) over invoking ``uvicorn`` directly.
    """
    import uvicorn

    uvicorn.run(
        get_app(),
        host=settings.host,
        port=settings.port,
        reload=False,
        log_config=None,  # structlog handles logging
        interface="asgi3",
    )


if __name__ == "__main__":
    run()
