"""Stages 12/14 — configuration for secrets and telemetry."""

import pytest
from pydantic import SecretStr

from waxprep.config import Settings

pytestmark = pytest.mark.configuration

# Synthetic placeholder built at runtime so it is never mistaken for a
# committed credential by secret scanners.
FAKE_TOKEN = "-".join(["placeholder", "not", "a", "real", "credential"])


class TestSecretField:
    def test_secret_is_masked_in_repr_and_dump(self):
        """A credential must never appear in repr() or model_dump()."""
        sentinel = "SENTINEL-config-8a2f"
        settings = Settings(_env_file=None, telemetry_auth_token=SecretStr(sentinel))
        assert sentinel not in repr(settings)
        assert sentinel not in str(settings.model_dump())
        assert sentinel not in settings.model_dump_json()

    def test_secret_value_still_retrievable_when_needed(self):
        settings = Settings(_env_file=None, telemetry_auth_token=SecretStr(FAKE_TOKEN))
        assert settings.telemetry_auth_token is not None
        assert settings.telemetry_auth_token.get_secret_value() == FAKE_TOKEN

    def test_no_default_secret(self):
        """A missing credential must stay None rather than a placeholder."""
        assert Settings(_env_file=None).telemetry_auth_token is None


class TestTelemetrySettings:
    def test_disabled_by_default(self):
        settings = Settings(_env_file=None)
        assert settings.telemetry_enabled is False
        assert settings.telemetry_endpoint is None

    def test_sample_ratio_range_enforced(self):
        with pytest.raises(ValueError):
            Settings(_env_file=None, telemetry_sample_ratio=2.0)
        with pytest.raises(ValueError):
            Settings(_env_file=None, telemetry_sample_ratio=-0.5)

    def test_enabled_without_endpoint_rejected(self):
        with pytest.raises(ValueError, match="telemetry_endpoint"):
            Settings(_env_file=None, telemetry_enabled=True, telemetry_endpoint="")

    def test_enabled_with_endpoint_accepted(self):
        settings = Settings(
            _env_file=None,
            telemetry_enabled=True,
            telemetry_endpoint="http://collector:4318/v1/traces",
        )
        assert settings.telemetry_enabled is True

    def test_log_json_toggle(self):
        assert Settings(_env_file=None, log_json=False).log_json is False

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("WAXPREP_TELEMETRY_ENABLED", "true")
        monkeypatch.setenv("WAXPREP_TELEMETRY_ENDPOINT", "http://collector:4318/v1/traces")
        settings = Settings(_env_file=None)
        assert settings.telemetry_enabled is True

    def test_metrics_endpoint_is_optional_and_can_be_overridden(self, monkeypatch):
        assert Settings(_env_file=None).telemetry_metrics_endpoint is None
        monkeypatch.setenv("WAXPREP_TELEMETRY_METRICS_ENDPOINT", "http://collector:4318/v1/metrics")
        settings = Settings(_env_file=None)
        assert settings.telemetry_metrics_endpoint == "http://collector:4318/v1/metrics"
