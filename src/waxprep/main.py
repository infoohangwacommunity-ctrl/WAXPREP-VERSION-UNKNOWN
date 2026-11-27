"""
Main Application - Stages 01-16
ASGI application with an explicit, failure-safe application lifecycle.

Includes:
- One authoritative lifecycle state per application instance
- Ordered, dependency-aware component initialization
- Reverse-order cleanup with failure isolation and cancellation safety
- Owned background-task supervision
- Request correlation ID middleware
- Global exception handlers
- Lifecycle-aware health endpoints
- Structured logging with structlog

Application-instance state lives on ``app.state`` (``app_state``, ``lifecycle``,
``supervisor``). ``get_app()`` returns the default process instance used by
Uvicorn; ``create_app()`` builds independent instances for tests and embedding.
``_app_state`` is a compatibility alias to the default instance's state only; it
does not decide request handling, readiness or cleanup.
"""

from __future__ import annotations

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
from waxprep.lifecycle import (
    ApplicationLifecycle,
    BackgroundTaskSupervisor,
    LifecycleComponent,
    LifecycleState,
)
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
# and future workers share one contract. It creates no lifecycle resources.
configure_logging(
    level=settings.log_level.value,
    json_output=settings.log_json,
    service_version="0.1.0",
    environment=settings.environment.value,
)
logger = structlog.get_logger()

# Bounded readiness reasons. Named constants keep the vocabulary in one place
# and avoid a stray literal becoming a new response value.
READINESS_LIFECYCLE_NOT_READY = "lifecycle_not_ready"
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


class AppState:
    """Application-instance data owned by one ``FastAPI`` instance.

    This is not a module-global. The default application exposes a compatibility
    alias for older tests/tools, but request handling reads ``app.state``.
    """

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

    def reset(self) -> None:
        """Drop every reference owned by a finished lifecycle execution."""
        self._shutting_down = False
        self._registries_ready = False
        self._channel_registry = None
        self._model_registry = None
        self._tool_registry = None


# ── Default lifecycle components ─────────────────────────────────────────────


def _initialize_configuration() -> None:
    logger.info(
        "Configuration loaded",
        environment=settings.environment.value,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.value,
    )


def _initialize_registries(app_state: AppState) -> None:
    from waxprep.registries.channel import get_channel_registry
    from waxprep.registries.model import get_model_registry
    from waxprep.registries.tool import get_tool_registry

    app_state.channel_registry = get_channel_registry()
    app_state.model_registry = get_model_registry()
    app_state.tool_registry = get_tool_registry()
    app_state.channel_registry.register_defaults()
    app_state.model_registry.register_defaults()
    app_state.tool_registry.register_defaults()
    app_state.registries_ready = True
    logger.info(
        "registries_initialized",
        channels=app_state.channel_registry.list_all(),
        models=app_state.model_registry.list_all(),
        tools=app_state.tool_registry.list_all(),
    )


def _release_registries(app_state: AppState) -> None:
    app_state.registries_ready = False
    app_state.channel_registry = None
    app_state.model_registry = None
    app_state.tool_registry = None
    logger.info("registries_released")


def _initialize_telemetry() -> None:
    # Clear any instruments left over from a previous lifecycle before building
    # a new provider. Telemetry is optional: failures are recorded by the
    # lifecycle as degradation and never block the application.
    metrics.reset()
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
        metrics_active = metrics.configure(meter_provider=telemetry_state.meter_provider)
    logger.info(
        "telemetry_configured",
        active=telemetry_state.active,
        reason=telemetry_state.reason,
        metrics_active=metrics_active,
        metrics_reason=telemetry_state.metrics_reason,
    )


async def _shutdown_observability() -> None:  # noqa: RUF029
    """Final flush after application resources, then reset instruments."""
    telemetry.shutdown()
    metrics.reset()
    logger.info("observability_shutdown_complete")


def _register_default_components(
    lifecycle: ApplicationLifecycle,
    app_state: AppState,
) -> None:
    lifecycle.register(
        LifecycleComponent(
            name="configuration",
            initialize=_initialize_configuration,
            description="Validated settings already loaded; logs non-secret identity",
        )
    )
    lifecycle.register(
        LifecycleComponent(
            name="registries",
            initialize=lambda: _initialize_registries(app_state),
            release=lambda: _release_registries(app_state),
            depends_on=("configuration",),
            description="Channel, model and tool registries with explicit defaults",
        )
    )
    lifecycle.register(
        LifecycleComponent(
            name="telemetry",
            initialize=_initialize_telemetry,
            mandatory=False,
            depends_on=("configuration",),
            description="Optional OpenTelemetry export; degradation never blocks startup",
        )
    )
    lifecycle.set_observability_cleanup(_shutdown_observability)


def _ensure_app_resources(app: FastAPI) -> tuple[AppState, ApplicationLifecycle]:
    """Attach per-instance lifecycle resources to a FastAPI app.

    ``create_app()`` attaches them up front. A manually constructed
    ``FastAPI(lifespan=lifespan)`` (tests, embedding) gets the same defaults here,
    proving the lifespan owns its state instead of relying on module globals.
    """
    app_state = cast(AppState | None, getattr(app.state, "app_state", None))
    if app_state is None:
        app_state = AppState()
        app.state.app_state = app_state

    supervisor = cast(BackgroundTaskSupervisor | None, getattr(app.state, "supervisor", None))
    if supervisor is None:
        supervisor = BackgroundTaskSupervisor()
        app.state.supervisor = supervisor

    lifecycle = cast(ApplicationLifecycle | None, getattr(app.state, "lifecycle", None))
    if lifecycle is None:
        lifecycle = ApplicationLifecycle(background=supervisor)
        app.state.lifecycle = lifecycle
        _register_default_components(lifecycle, app_state)
    else:
        lifecycle.attach_background(supervisor)

    return app_state, lifecycle


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """ASGI lifespan: explicit startup, then failure-safe termination."""
    app_state, lifecycle = _ensure_app_resources(app)
    app_state.reset()
    try:
        await lifecycle.start()
    except BaseException:
        app_state.shutting_down = True
        app_state.reset()
        raise

    try:
        yield
    finally:
        app_state.shutting_down = True
        try:
            await lifecycle.shutdown()
        finally:
            app_state.reset()


# ── Exception handlers ───────────────────────────────────────────────────────


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:  # noqa: RUF029
    """Handle HTTP exceptions with sanitized output."""
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


async def validation_exception_handler(  # noqa: RUF029
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Handle validation errors with sanitized output (422 per RFC 9110)."""
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


async def waxprep_error_handler(request: Request, exc: WaxPrepError) -> JSONResponse:  # noqa: RUF029
    """Single authoritative reporting point for typed application failures."""
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


# ── Health endpoints ─────────────────────────────────────────────────────────


async def liveness() -> JSONResponse:  # noqa: RUF029
    """Liveness endpoint - Is the process alive?"""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "alive"},
    )


def _readiness_failure_reason(
    app_state: AppState | None,
    lifecycle: ApplicationLifecycle | None,
) -> str | None:
    """Return the first failed readiness precondition, or None when ready."""
    reason: str | None = None

    if lifecycle is None or lifecycle.state is not LifecycleState.READY:
        reason = READINESS_LIFECYCLE_NOT_READY
    elif app_state is None:
        reason = READINESS_REGISTRIES_NOT_INITIALIZED
    else:
        try:
            env_value = settings.environment.value
        except AttributeError:
            env_value = None

        if not env_value:
            reason = READINESS_CONFIGURATION_NOT_LOADED
        elif not app_state.registries_ready:
            reason = READINESS_REGISTRIES_NOT_INITIALIZED
        elif app_state.channel_registry is None or not app_state.channel_registry.is_registered(
            "fake"
        ):
            reason = READINESS_CHANNEL_NOT_INITIALIZED
        elif app_state.model_registry is None or not app_state.model_registry.is_registered("fake"):
            reason = READINESS_MODEL_NOT_INITIALIZED
        elif app_state.tool_registry is None or not app_state.tool_registry.is_registered(
            "fake_tool"
        ):
            reason = READINESS_TOOL_NOT_INITIALIZED

    return reason


async def readiness(request: Request) -> JSONResponse:  # noqa: RUF029
    """Readiness endpoint - mandatory initialization done and accepting work?"""
    app_state = cast(AppState | None, getattr(request.app.state, "app_state", None))
    lifecycle = cast(ApplicationLifecycle | None, getattr(request.app.state, "lifecycle", None))
    failure = _readiness_failure_reason(app_state, lifecycle)
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


# ── Application factory ──────────────────────────────────────────────────────


def create_app() -> FastAPI:
    """Build an independent application instance with its own lifecycle."""
    app_state = AppState()
    supervisor = BackgroundTaskSupervisor()
    lifecycle = ApplicationLifecycle(background=supervisor)
    _register_default_components(lifecycle, app_state)

    app = FastAPI(
        title="WaxPrep Foundation",
        description=(
            "WaxPrep Foundation - ASGI application with health endpoints, "
            "registries, explicit lifecycle and structured logging"
        ),
        version="0.1.0",
        lifespan=lifespan,
        # FastAPI's native telemetry would add a second request span and a
        # duplicate http.server.request.duration stream once a global provider
        # is configured. WaxPrep owns exactly one boundary and one catalogue.
        telemetry={
            "tracing": False,
            "metrics": False,
            "logs": False,
            "operation_spans": False,
        },
    )
    app.state.app_state = app_state
    app.state.supervisor = supervisor
    app.state.lifecycle = lifecycle

    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(ObservabilityMiddleware)

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(WaxPrepError, waxprep_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, general_exception_handler)

    app.add_api_route("/health/liveness", liveness, methods=["GET"])
    app.add_api_route("/health/readiness", readiness, methods=["GET"])
    app.add_api_route("/", root, methods=["GET"])
    return app


# Default process instance (Uvicorn) and a compatibility alias for tests/tools.
_app: FastAPI = create_app()
_app_state: AppState = cast(AppState, _app.state.app_state)


def _reset_default_app() -> FastAPI:  # pyright: ignore[reportUnusedFunction]
    """Replace the default app instance; used by isolated test fixtures."""
    global _app, _app_state
    _app = create_app()
    _app_state = cast(AppState, _app.state.app_state)
    return _app


def get_app() -> FastAPI:
    """ASGI entry point for Uvicorn; returns the default application instance."""
    return _app


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
