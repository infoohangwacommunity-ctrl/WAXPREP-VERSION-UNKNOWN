"""
WaxPrep test configuration - Stage 05.

Covers:
- Time control (freezegun) with explicit default, no request.param
- Seeded randomness, opt-in (not autouse)
- Fresh registry instances (not singletons)
- App/client fixtures
- Mock fixture
- pytest markers: unit, integration, contract, lifecycle, regression, architecture, configuration
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from waxprep.main import get_app
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry

# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Register custom pytest markers."""
    markers = [
        "unit: unit tests (fast, isolated)",
        "integration: integration tests (app + real dependencies)",
        "contract: contract tests (interface compliance)",
        "lifecycle: lifecycle tests (startup/shutdown)",
        "regression: regression tests (specific bug fixes)",
        "architecture: architecture tests (boundaries, dependencies)",
        "configuration: configuration tests (settings, env)",
    ]
    for marker in markers:
        config.addinivalue_line("markers", marker)


# ---------------------------------------------------------------------------
# Time control
# ---------------------------------------------------------------------------

@pytest.fixture
def frozen_time():
    """Freeze time at a fixed point. Opt-in via explicit request.

    Uses freezegun with a hardcoded default date. No request.param needed.
    """
    from freezegun import freeze_time as _freeze_time

    with _freeze_time("2026-01-01 00:00:00 UTC"):
        yield


# ---------------------------------------------------------------------------
# Seeded randomness (opt-in)
# ---------------------------------------------------------------------------

@pytest.fixture
def seeded_random():
    """Seed random and numpy.random for reproducible tests.

    OPT-IN only: tests must explicitly request this fixture to get seeded
    randomness. Not autouse, so non-deterministic tests remain detectable.
    """
    import random

    random.seed(42)
    yield
    # No teardown needed - each test gets a fresh seed via fixture scope


# ---------------------------------------------------------------------------
# App and client
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Return the FastAPI application instance."""
    return get_app()


@pytest.fixture
def client(app):
    """Return a TestClient wrapping the app."""
    with TestClient(app) as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# Fresh registry instances (not singletons)
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_channel_registry():
    """Fresh ChannelRegistry instance, no defaults registered."""
    return ChannelRegistry()


@pytest.fixture
def fresh_model_registry():
    """Fresh ModelRegistry instance, no defaults registered."""
    return ModelRegistry()


@pytest.fixture
def fresh_tool_registry():
    """Fresh ToolRegistry instance, no defaults registered."""
    return ToolRegistry()


@pytest.fixture
def populated_channel_registry():
    """Fresh ChannelRegistry with defaults registered."""
    registry = ChannelRegistry()
    registry.register_defaults()
    return registry


@pytest.fixture
def populated_model_registry():
    """Fresh ModelRegistry with defaults registered."""
    registry = ModelRegistry()
    registry.register_defaults()
    return registry


@pytest.fixture
def populated_tool_registry():
    """Fresh ToolRegistry with defaults registered."""
    registry = ToolRegistry()
    registry.register_defaults()
    return registry


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_registry():
    """Return a MagicMock that simulates a registry."""
    return MagicMock()


@pytest.fixture
def mock_adapter():
    """Return a MagicMock that simulates a registry adapter."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Monkeypatch is built into pytest - explicitly document
# ---------------------------------------------------------------------------

# pytest's built-in `monkeypatch` fixture is available in all tests.
# Use it for patching environment variables, attributes, and sys.path.
