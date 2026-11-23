"""
Lifecycle tests - startup, shutdown, and signal handling behavior.

Extracted from test_main.py per Stage 05 Phase 5.
Tests lifespan startup/shutdown globals management and handle_shutdown
idempotency.
"""

import asyncio
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from waxprep.main import lifespan

# ---------------------------------------------------------------------------
# Lifespan startup/shutdown globals management
# ---------------------------------------------------------------------------


class TestLifespan:
    """Prove lifespan startup sets globals and shutdown resets them."""

    @pytest.mark.lifecycle
    def test_startup_sets_state(self):
        """After lifespan startup: _registries_ready=True, registries populated."""
        import waxprep.main as main

        main._app_state.shutting_down = False
        main._app_state.registries_ready = False
        main._app_state.channel_registry = None
        main._app_state.model_registry = None
        main._app_state.tool_registry = None

        async def _run():
            app = FastAPI(title="test", lifespan=lifespan)
            async with lifespan(app):
                assert main._app_state.registries_ready is True
                assert main._app_state.channel_registry is not None
                assert main._app_state.model_registry is not None
                assert main._app_state.tool_registry is not None

        asyncio.run(_run())

    @pytest.mark.lifecycle
    def test_shutdown_resets_state(self):
        """After lifespan shutdown: state is reset, _registries_ready=False."""
        import waxprep.main as main

        main._app_state.shutting_down = False
        main._app_state.registries_ready = False
        main._app_state.channel_registry = None
        main._app_state.model_registry = None
        main._app_state.tool_registry = None

        async def _run():
            app = FastAPI(title="test", lifespan=lifespan)
            async with lifespan(app):
                pass  # startup has run
            # After exiting: shutdown code has run
            assert main._app_state.shutting_down is True
            assert main._app_state.registries_ready is False
            assert main._app_state.channel_registry is None
            assert main._app_state.model_registry is None
            assert main._app_state.tool_registry is None

        asyncio.run(_run())



