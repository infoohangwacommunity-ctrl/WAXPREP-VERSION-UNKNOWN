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
    def test_startup_sets_globals(self):
        """After lifespan startup: _registries_ready=True, registries populated."""
        import waxprep.main as main

        main._shutting_down = False
        main._registries_ready = False
        main._channel_registry = None
        main._model_registry = None
        main._tool_registry = None

        async def _run():
            app = FastAPI(title="test", lifespan=lifespan)
            async with lifespan(app):
                assert main._registries_ready is True
                assert main._channel_registry is not None
                assert main._model_registry is not None
                assert main._tool_registry is not None

        asyncio.run(_run())

    @pytest.mark.lifecycle
    def test_shutdown_resets_globals(self):
        """After lifespan shutdown: globals are None, _registries_ready=False."""
        import waxprep.main as main

        main._shutting_down = False
        main._registries_ready = False
        main._channel_registry = None
        main._model_registry = None
        main._tool_registry = None

        async def _run():
            app = FastAPI(title="test", lifespan=lifespan)
            async with lifespan(app):
                pass  # startup has run
            # After exiting: shutdown code has run
            assert main._shutting_down is True
            assert main._registries_ready is False
            assert main._channel_registry is None
            assert main._model_registry is None
            assert main._tool_registry is None

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# handle_shutdown idempotency and logging
# ---------------------------------------------------------------------------


class TestHandleShutdown:
    """Prove handle_shutdown is idempotent and logs on first call."""

    @pytest.mark.lifecycle
    def test_first_call_sets_flag_and_logs(self):
        """First call: _shutting_down becomes True, logger.info called."""
        import waxprep.main as main

        main._shutting_down = False
        with patch("waxprep.main.logger") as mock_logger:
            main.handle_shutdown(signum=15, _frame=None)
        assert main._shutting_down is True
        mock_logger.info.assert_called_once()
        assert mock_logger.info.call_args.kwargs["signal"] == 15

    @pytest.mark.lifecycle
    def test_second_call_is_noop(self):
        """Second call while shutting down: no log, flag unchanged."""
        import waxprep.main as main

        main._shutting_down = True
        with patch("waxprep.main.logger") as mock_logger:
            main.handle_shutdown(signum=15, _frame=None)
        assert main._shutting_down is True
        mock_logger.info.assert_not_called()
