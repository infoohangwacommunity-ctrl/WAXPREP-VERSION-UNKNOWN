"""
Main Application - Stage 02
ASGI application with ordered startup, graceful shutdown, health endpoints.
NO tutor logic. NO real adapters. Only foundation.
"""

import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from waxprep.config import settings
from waxprep.registries.channel import get_channel_registry
from waxprep.registries.model import get_model_registry
from waxprep.registries.tool import get_tool_registry

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Ordered startup sequence - Stage 02
    1. Load configuration
    2. Initialize registries
    3. Initialize external clients (none in Stages 01-02)
    4. Start background services (none in Stages 01-02)
    5. Log startup
    """
    global _shutting_down
    _shutting_down = False

    # 1. Load configuration (already done via settings)
    logger.info("Stage 02: Configuration loaded")

    # 2. Initialize registries
    channel_registry = get_channel_registry()
    model_registry = get_model_registry()
    tool_registry = get_tool_registry()
    
    logger.info("Stage 02: Registries initialized")
    logger.info(f"  Channels: {channel_registry.list_all()}")
    logger.info(f"  Models: {model_registry.list_all()}")
    logger.info(f"  Tools: {tool_registry.list_all()}")

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
    logger.info("Stage 02: Shutdown started")
    logger.info("Stage 02: Shutdown complete")


# Create FastAPI app
_app = FastAPI(
    title="WaxPrep Foundation",
    description="Stages 01-02 ONLY - Foundation",
    version="0.1.0",
    lifespan=lifespan,
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
    Liveness != Readiness. This proves the distinction."""
    # In Stages 01-02, we're always ready if we're alive
    # Later stages will check dependencies here
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready"},
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
    """Get the FastAPI application."""
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
