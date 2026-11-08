"""
Main Application - Composition Root - Stage 03

This is the ONLY module that wires all layers together.
It imports from domain/, application/, adapters/, and infrastructure/.

Dependency Rule: This is the composition root.
It may import ANY module. No other module may import across all layers.

The composition root:
1. Configures the application
2. Wires up all dependencies
3. Registers adapters with ports
4. Sets up the ASGI application
5. Manages lifecycle
"""

import signal
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

# Import from adapters (existing Stage 02)
from waxprep.adapters.fake_channel import FakeChannelAdapter
from waxprep.adapters.fake_model import FakeModelAdapter
from waxprep.adapters.fake_tool import FakeTool

# Import from application (ports)
from waxprep.domain.exceptions import DomainError

# Import from domain (models, exceptions)
# Import from infrastructure first (config, logging)
from waxprep.infrastructure.config import get_settings
from waxprep.infrastructure.di import get_service_locator
from waxprep.infrastructure.lifecycle import LifecycleManager, LifecycleState, get_lifecycle_manager
from waxprep.infrastructure.logging import configure_logging, get_logger

# Import from registries (existing Stage 02)
from waxprep.registries.channel import ChannelRegistry, get_channel_registry
from waxprep.registries.model import ModelRegistry, get_model_registry
from waxprep.registries.tool import ToolRegistry, get_tool_registry

# Configure logging first
configure_logging()
logger = get_logger(__name__)

# Global state
_app: FastAPI | None = None
_lifecycle: LifecycleManager | None = None


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    This is the composition root where all layers are wired together.
    """
    global _app, _lifecycle

    config = get_settings()

    # Initialize lifecycle manager
    _lifecycle = get_lifecycle_manager()

    # Initialize service locator
    service_locator = get_service_locator()

    # Initialize registries (from Stage 02)
    channel_registry = get_channel_registry()
    model_registry = get_model_registry()
    tool_registry = get_tool_registry()

    # Register existing fake adapters with registries
    # These are from Stage 02 and prove the architecture works
    try:
        channel_registry.register("fake", FakeChannelAdapter())
        logger.debug("Composition: Registered fake channel adapter")
    except Exception as e:
        logger.warning("Composition: Failed to register fake channel adapter", error=str(e))

    try:
        model_registry.register("fake", FakeModelAdapter())
        logger.debug("Composition: Registered fake model adapter")
    except Exception as e:
        logger.warning("Composition: Failed to register fake model adapter", error=str(e))

    try:
        tool_registry.register("fake_tool", FakeTool())
        logger.debug("Composition: Registered fake tool adapter")
    except Exception as e:
        logger.warning("Composition: Failed to register fake tool adapter", error=str(e))

    # Register registries with service locator
    service_locator.register(ChannelRegistry, channel_registry)
    service_locator.register(ModelRegistry, model_registry)
    service_locator.register(ToolRegistry, tool_registry)

    logger.info(
        "Composition: Registries initialized",
        channels=channel_registry.list_all(),
        models=model_registry.list_all(),
        tools=tool_registry.list_all(),
    )

    # Create FastAPI app
    _app = FastAPI(
        title="WaxPrep Foundation",
        description="WaxPrep - Personalized AI Learning Companion (Stages 01-03)",
        version="0.3.0",
        # Use the lifespan from lifecycle manager
        lifespan=lifespan,
    )

    # Add exception handlers
    setup_exception_handlers(_app)

    # Add routes
    setup_routes(_app)

    return _app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    ASGI lifespan context manager - Stage 03

    Ordered startup sequence:
    1. Load configuration (already done via get_settings())
    2. Initialize registries (done in create_app)
    3. Initialize external clients (none in Stage 03)
    4. Start background services (none in Stage 03)
    5. Log startup

    Ordered shutdown sequence:
    1. Stop accepting new requests
    2. Finish in-flight work
    3. Record unfinished work
    4. Clean up resources
    5. Exit 0
    """
    config = get_settings()
    lifecycle = get_lifecycle_manager()

    # Startup sequence
    logger.info("Stage 03: Lifespan startup initiated")

    try:
        # Start the lifecycle
        await lifecycle.start()

        logger.info(
            "Stage 03: Startup complete",
            environment=config.environment,
            host=config.host,
            port=config.port,
            debug=config.debug,
        )

        yield

    except Exception as e:
        logger.error("Stage 03: Startup failed", error=str(e))
        raise
    finally:
        # Shutdown sequence
        logger.info("Stage 03: Lifespan shutdown initiated")

        try:
            await lifecycle.stop()
            logger.info("Stage 03: Shutdown complete - exit 0")
        except Exception as e:
            logger.error("Stage 03: Shutdown failed", error=str(e))
            # Still exit 0 - we tried our best
            logger.info("Stage 03: Shutdown complete (with errors) - exit 0")


def setup_exception_handlers(app: FastAPI) -> None:
    """Setup exception handlers for the application."""

    @app.exception_handler(DomainError)
    async def domain_error_handler(
        request: Request,
        exc: DomainError,
    ) -> JSONResponse:
        """Handle domain errors."""
        logger.error(
            "Domain error",
            error=exc.message,
            context=exc.context,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "domain_error",
                "message": exc.message,
                "context": exc.context,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request,
        exc: ValueError,
    ) -> JSONResponse:
        """Handle value errors."""
        logger.warning(
            "Value error",
            error=str(exc),
            path=str(request.url),
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": str(exc),
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Handle unexpected errors."""
        logger.error(
            "Unexpected error",
            error=str(exc),
            type=type(exc).__name__,
            path=str(request.url),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred",
            },
        )


def setup_routes(app: FastAPI) -> None:
    """Setup all routes for the application."""

    # Health endpoints
    @app.get("/health/liveness")
    async def liveness() -> JSONResponse:
        """Liveness endpoint - Is the process alive?"""
        lifecycle = get_lifecycle_manager()
        if lifecycle.state == LifecycleState.STOPPED:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "not_alive"},
            )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "alive"},
        )

    @app.get("/health/readiness")
    async def readiness() -> JSONResponse:
        """Readiness endpoint - Is the application ready?

        Liveness != Readiness.
        This proves the distinction from Stage 02.
        In Stage 03, we check if the application is fully started.
        """
        lifecycle = get_lifecycle_manager()
        if lifecycle.state != LifecycleState.STARTED:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "not_ready",
                    "current_state": lifecycle.state.value,
                },
            )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready"},
        )

    # Root endpoint
    @app.get("/")
    async def root() -> JSONResponse:
        """Root endpoint - proves the app is running."""
        config = get_settings()
        lifecycle = get_lifecycle_manager()

        # Get registry counts
        channel_registry = get_channel_registry()
        model_registry = get_model_registry()
        tool_registry = get_tool_registry()

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "WaxPrep Foundation - Stages 01-03",
                "stages": ["01", "02", "03"],
                "status": "running",
                "environment": config.environment,
                "lifecycle_state": lifecycle.state.value,
                "registries": {
                    "channels": channel_registry.list_all(),
                    "models": model_registry.list_all(),
                    "tools": tool_registry.list_all(),
                },
            },
        )

    # Architecture endpoint - proves hexagonal architecture
    @app.get("/architecture")
    async def architecture() -> JSONResponse:
        """Endpoint to verify hexagonal architecture.

        This endpoint demonstrates that:
        - Domain layer is pure (no external imports)
        - Application layer defines ports
        - Adapters implement ports
        - Infrastructure handles runtime concerns
        - Only main.py wires everything together
        """
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "architecture": "hexagonal",
                "layers": [
                    {
                        "name": "domain",
                        "responsibility": "Pure business logic",
                        "dependencies": ["stdlib", "domain"],
                    },
                    {
                        "name": "application",
                        "responsibility": "Use case orchestration + ports",
                        "dependencies": ["domain"],
                    },
                    {
                        "name": "adapters",
                        "responsibility": "Implement ports",
                        "dependencies": ["application/ports", "domain"],
                    },
                    {
                        "name": "infrastructure",
                        "responsibility": "Runtime concerns",
                        "dependencies": ["domain", "application"],
                    },
                    {
                        "name": "main",
                        "responsibility": "Composition root",
                        "dependencies": ["ALL"],
                    },
                ],
                "dependency_rule": "Strict one-directional dependencies enforced by import-linter",
                "composition_root": "main.py",
            },
        )


# Graceful shutdown handler
def handle_shutdown(signum: int, frame: object) -> None:
    """Handle SIGTERM/SIGINT for graceful shutdown.

    This cooperates with the ASGI server's shutdown mechanism.
    It does NOT call sys.exit(0) directly inside the signal handler.
    """
    logger.info("SIGTERM/SIGINT received - graceful shutdown initiated", signal=signum)

    # Set the lifecycle state to stopping
    # The ASGI server will detect this and initiate proper shutdown
    lifecycle = get_lifecycle_manager()
    if lifecycle.is_started:
        lifecycle._state = LifecycleState.STOPPING


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)


# Create the application
_app = create_app()


# Get the app (for uvicorn)
def get_app() -> FastAPI:
    """Get the FastAPI application."""
    return _app


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    config = get_settings()
    uvicorn.run(
        "waxprep.main:get_app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_config=None,  # structlog handles logging
    )
