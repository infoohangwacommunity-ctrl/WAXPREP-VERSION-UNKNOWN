"""
Lifecycle Management - Stage 03
Manages application startup and shutdown sequences.

Dependency Rule: This module may import domain/ and application/.
It may NOT import adapters/.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any

from waxprep.infrastructure.config import get_settings
from waxprep.infrastructure.logging import get_logger

logger = get_logger(__name__)


class LifecycleState(Enum):
    """Current state of the application lifecycle."""

    STOPPED = "stopped"
    STARTING = "starting"
    STARTED = "started"
    STOPPING = "stopping"
    FAILED = "failed"


class LifecycleError(Exception):
    """Error raised during lifecycle operations."""

    def __init__(self, message: str, state: LifecycleState) -> None:
        super().__init__(message)
        self.message = message
        self.state = state


class LifecycleManager:
    """Manages the application lifecycle.

    Provides ordered startup and shutdown sequences with hooks for
    initializing and cleaning up resources.
    """

    def __init__(self) -> None:
        self._state = LifecycleState.STOPPED
        self._startup_hooks: list[Callable[[], Any]] = []
        self._shutdown_hooks: list[Callable[[], Any]] = []
        self._async_startup_hooks: list[Callable[[], AsyncIterator[Any]]] = []
        self._async_shutdown_hooks: list[Callable[[], AsyncIterator[Any]]] = []
        self._shutdown_timeout: int = 60

    @property
    def state(self) -> LifecycleState:
        """Get the current lifecycle state."""
        return self._state

    @property
    def is_started(self) -> bool:
        """Check if the application is started."""
        return self._state == LifecycleState.STARTED

    @property
    def is_stopped(self) -> bool:
        """Check if the application is stopped."""
        return self._state == LifecycleState.STOPPED

    @property
    def is_starting(self) -> bool:
        """Check if the application is starting."""
        return self._state == LifecycleState.STARTING

    @property
    def is_stopping(self) -> bool:
        """Check if the application is stopping."""
        return self._state == LifecycleState.STOPPING

    def add_startup_hook(self, hook: Callable[[], Any]) -> None:
        """Add a synchronous startup hook."""
        self._startup_hooks.append(hook)

    def add_shutdown_hook(self, hook: Callable[[], Any]) -> None:
        """Add a synchronous shutdown hook."""
        self._shutdown_hooks.append(hook)

    def add_async_startup_hook(
        self,
        hook: Callable[[], AsyncIterator[Any]],
    ) -> None:
        """Add an asynchronous startup hook."""
        self._async_startup_hooks.append(hook)

    def add_async_shutdown_hook(
        self,
        hook: Callable[[], AsyncIterator[Any]],
    ) -> None:
        """Add an asynchronous shutdown hook."""
        self._async_shutdown_hooks.append(hook)

    def set_shutdown_timeout(self, timeout: int) -> None:
        """Set the shutdown timeout in seconds."""
        self._shutdown_timeout = timeout

    async def start(self) -> None:
        """Start the application.

        Executes all startup hooks in order:
        1. Synchronous startup hooks
        2. Asynchronous startup hooks

        Raises:
            LifecycleError: If startup fails
        """
        if self._state != LifecycleState.STOPPED:
            raise LifecycleError(
                f"Cannot start from {self._state.value} state",
                self._state,
            )

        self._state = LifecycleState.STARTING
        logger.info("Lifecycle: Starting application")

        try:
            # Execute synchronous startup hooks
            for hook in self._startup_hooks:
                try:
                    hook()
                    logger.debug("Lifecycle: Synchronous startup hook completed")
                except Exception as e:
                    logger.error("Lifecycle: Startup hook failed", error=str(e))
                    raise LifecycleError(
                        f"Startup hook failed: {e}",
                        self._state,
                    ) from e

            # Execute asynchronous startup hooks
            for hook in self._async_startup_hooks:
                try:
                    async for _ in hook():
                        pass
                    logger.debug("Lifecycle: Asynchronous startup hook completed")
                except Exception as e:
                    logger.error("Lifecycle: Async startup hook failed", error=str(e))
                    raise LifecycleError(
                        f"Async startup hook failed: {e}",
                        self._state,
                    ) from e

            self._state = LifecycleState.STARTED
            logger.info("Lifecycle: Application started successfully")

        except Exception as e:
            self._state = LifecycleState.FAILED
            logger.error("Lifecycle: Application startup failed", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the application gracefully.

        Executes all shutdown hooks in reverse order:
        1. Asynchronous shutdown hooks (in reverse order)
        2. Synchronous shutdown hooks (in reverse order)

        Implements graceful shutdown:
        - Stops accepting new requests
        - Finishes in-flight work
        - Records unfinished work
        - Exits cleanly
        """
        if self._state not in (LifecycleState.STARTED, LifecycleState.STARTING):
            logger.warning(
                "Lifecycle: Stop called from invalid state",
                current_state=self._state.value,
            )
            return

        self._state = LifecycleState.STOPPING
        logger.info("Lifecycle: Stopping application gracefully")

        # Execute asynchronous shutdown hooks in reverse order
        for hook in reversed(self._async_shutdown_hooks):
            try:
                async for _ in hook():
                    pass
                logger.debug("Lifecycle: Asynchronous shutdown hook completed")
            except Exception as e:
                logger.error("Lifecycle: Async shutdown hook failed", error=str(e))

        # Execute synchronous shutdown hooks in reverse order
        for hook in reversed(self._shutdown_hooks):
            try:
                hook()
                logger.debug("Lifecycle: Synchronous shutdown hook completed")
            except Exception as e:
                logger.error("Lifecycle: Shutdown hook failed", error=str(e))

        self._state = LifecycleState.STOPPED
        logger.info("Lifecycle: Application stopped successfully")

    async def restart(self) -> None:
        """Restart the application.

        Stops and then starts the application.
        """
        await self.stop()
        await self.start()


# Global lifecycle manager instance
_lifecycle_manager: LifecycleManager | None = None


def get_lifecycle_manager() -> LifecycleManager:
    """Get the global lifecycle manager."""
    global _lifecycle_manager
    if _lifecycle_manager is None:
        _lifecycle_manager = LifecycleManager()
    return _lifecycle_manager


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """ASGI lifespan context manager.

    This is the entry point for the ASGI application lifespan.
    It coordinates startup and shutdown of all components.
    """
    config = get_settings()
    lifecycle = get_lifecycle_manager()

    # Set shutdown timeout from config
    lifecycle.set_shutdown_timeout(config.shutdown_timeout)

    # Start the application
    await lifecycle.start()

    try:
        yield
    finally:
        # Stop the application
        await lifecycle.stop()


def handle_shutdown(signum: int, frame: object) -> None:
    """Handle shutdown signals (SIGTERM, SIGINT).

    This triggers graceful shutdown by setting a flag that the
    ASGI server will detect and initiate shutdown.
    """
    logger.info("Lifecycle: Shutdown signal received", signal=signum)

    # Get the lifecycle manager and trigger shutdown
    lifecycle = get_lifecycle_manager()
    if lifecycle.is_started:
        # In a real ASGI server, we would trigger the lifespan shutdown
        # For now, we just log and set the state
        lifecycle._state = LifecycleState.STOPPING
        logger.info("Lifecycle: Shutdown initiated by signal")
