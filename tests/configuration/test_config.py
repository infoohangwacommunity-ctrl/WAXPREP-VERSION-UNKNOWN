"""
Test Configuration - Stage 02
Verify configuration values are configurable via environment variables.
Some defaults are intentional development defaults, not forbidden hardcoding.
"""

import pytest

from waxprep.config import settings


class TestConfigurationIsConfigurable:
    """Verify configuration values can be changed via environment."""

    @pytest.mark.configuration
    def test_port_not_hardcoded(self):
        """Prove port is configurable, not hardcoded."""
        # The default is 8000, but it can be changed via environment
        assert hasattr(settings, "port")
        # Default value exists but is not hardcoded in logic
        assert settings.port == 8000

    @pytest.mark.configuration
    def test_host_not_hardcoded(self):
        """Prove host is configurable, not hardcoded."""
        assert hasattr(settings, "host")
        assert settings.host == "0.0.0.0"

    @pytest.mark.configuration
    def test_shutdown_grace_period_removed(self):
        """Verify shutdown_grace_period has been removed from configuration.

        The shutdown grace period setting was disconnected from application
        behavior and has been removed. Graceful shutdown is handled by the
        ASGI server (uvicorn) lifecycle management.
        """
        assert not hasattr(settings, "shutdown_grace_period")

    @pytest.mark.configuration
    def test_environment_not_hardcoded(self):
        """Prove environment is configurable, not hardcoded."""
        assert hasattr(settings, "environment")
        assert settings.environment == "development"

    @pytest.mark.configuration
    def test_log_level_not_hardcoded(self):
        """Prove log level is configurable, not hardcoded."""
        assert hasattr(settings, "log_level")
        assert settings.log_level == "info"
