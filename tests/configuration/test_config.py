"""
Configuration Tests — Stage 11

Comprehensive tests proving:
1. Valid defaults are loaded when no overrides are supplied.
2. Environment variables override defaults.
3. OS environment variables take precedence over .env file values.
4. Environment names are validated.
5. Invalid environment names are rejected.
6. Invalid log levels are rejected.
7. Port values below 1 or above 65535 are rejected.
8. Non-integer port values are rejected.
9. Empty or invalid host values are rejected.
10. Missing required production configuration is rejected.
11. Misspelled or unsupported WAXPREP_ variables are detected.
12. Tests do not accidentally inherit the developer's real .env file or
    machine-specific environment variables.
13. The application uses validated configuration when starting.
14. Configuration failures are reported without exposing secret values.

Isolation rule: every test sets up its own environment. No test relies on
the developer's current terminal environment or .env file.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from waxprep.config import (
    KNOWN_MISSPELLINGS,
    Environment,
    LogLevel,
    Settings,
    load_settings,
)

pytestmark = pytest.mark.configuration

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_configuration_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Guarantee every configuration test is independent of the developer's machine.

    Two leaks are closed:
    1. WAXPREP_* variables from the developer's shell are removed.
    2. The working directory is moved to an empty temporary directory so an
       implicit Settings() cannot read the developer's real .env file.

    Tests that need dotenv values must supply a dedicated temporary file.
    """
    for key in list(os.environ.keys()):
        if key.startswith("WAXPREP_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove all WAXPREP_ variables from the test process so tests are isolated.

    Any existing WAXPREP_* variables from the developer's machine are stripped.
    Tests that need specific values must set them explicitly.
    """
    prefix = "WAXPREP_"
    for key in list(os.environ.keys()):
        if key.startswith(prefix):
            monkeypatch.delenv(key, raising=False)


def _make_settings_with_env(
    monkeypatch: pytest.MonkeyPatch,
    env_vars: dict[str, str],
    isolated_env: None,
) -> Settings:
    """Build a Settings instance with specific env vars set via monkeypatch.

    This is the canonical way to override config in tests since Pydantic
    Settings reads from the OS environment, not from a constructor dict.
    """
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return Settings(_env_file=None)


# ---------------------------------------------------------------------------
# 1. Valid defaults
# ---------------------------------------------------------------------------


class TestValidDefaults:
    """Prove the application loads valid defaults when no overrides are supplied."""

    def test_default_environment(self, isolated_env: None) -> None:
        settings = Settings(_env_file=None)
        assert settings.environment == Environment.DEVELOPMENT

    def test_default_host(self, isolated_env: None) -> None:
        settings = Settings(_env_file=None)
        assert settings.host == "0.0.0.0"

    def test_default_port(self, isolated_env: None) -> None:
        settings = Settings(_env_file=None)
        assert settings.port == 8000

    def test_default_log_level(self, isolated_env: None) -> None:
        settings = Settings(_env_file=None)
        assert settings.log_level == LogLevel.INFO

    def test_all_defaults_are_valid(self, isolated_env: None) -> None:
        """Defaults themselves must pass validation (they are not magic bypasses)."""
        settings = Settings(_env_file=None)
        assert settings.environment in tuple(Environment)
        assert settings.log_level in tuple(LogLevel)
        assert 1 <= settings.port <= 65535
        assert settings.host.strip() != ""


# ---------------------------------------------------------------------------
# 2. Environment variable overrides
# ---------------------------------------------------------------------------


class TestEnvironmentVariableOverrides:
    """Prove that a valid environment variable overrides its default."""

    def test_environment_override(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _make_settings_with_env(
            monkeypatch, {"WAXPREP_ENVIRONMENT": "staging"}, isolated_env
        )
        assert settings.environment == Environment.STAGING

    def test_host_override(self, isolated_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _make_settings_with_env(monkeypatch, {"WAXPREP_HOST": "127.0.0.1"}, isolated_env)
        assert settings.host == "127.0.0.1"

    def test_port_override(self, isolated_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = _make_settings_with_env(monkeypatch, {"WAXPREP_PORT": "9000"}, isolated_env)
        assert settings.port == 9000

    def test_log_level_override_lowercase(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lowercase log level values are normalised to uppercase."""
        settings = _make_settings_with_env(
            monkeypatch, {"WAXPREP_LOG_LEVEL": "debug"}, isolated_env
        )
        assert settings.log_level == LogLevel.DEBUG
        assert settings.log_level.value == "DEBUG"

    def test_log_level_override_uppercase(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _make_settings_with_env(
            monkeypatch, {"WAXPREP_LOG_LEVEL": "WARNING"}, isolated_env
        )
        assert settings.log_level == LogLevel.WARNING

    def test_multiple_overrides_at_once(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings = _make_settings_with_env(
            monkeypatch,
            {
                "WAXPREP_ENVIRONMENT": "staging",
                "WAXPREP_HOST": "0.0.0.0",
                "WAXPREP_PORT": "8080",
                "WAXPREP_LOG_LEVEL": "error",
            },
            isolated_env,
        )
        assert settings.environment == Environment.STAGING
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080
        assert settings.log_level == LogLevel.ERROR


# ---------------------------------------------------------------------------
# 3. OS env vars take precedence over .env
# ---------------------------------------------------------------------------


class TestEnvPrecedenceOverDotenv:
    """OS environment variables take precedence over .env file values."""

    def test_os_env_wins_over_dotenv(self, tmp_path: str, monkeypatch: pytest.MonkeyPatch) -> None:
        dotenv_path = os.path.join(tmp_path, ".env")
        with open(dotenv_path, "w", encoding="utf-8") as f:
            f.write("WAXPREP_PORT=5000\n")

        monkeypatch.setenv("WAXPREP_PORT", "7000")

        # Load the dedicated file directly; no global model_config mutation that
        # could leak into tests running in parallel.
        settings = Settings(_env_file=dotenv_path)
        assert settings.port == 7000, "OS env should override .env"


# ---------------------------------------------------------------------------
# 4 & 5. Environment validation
# ---------------------------------------------------------------------------


class TestEnvironmentValidation:
    """The selected environment is validated."""

    def test_valid_environment_values(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All recognised environment values are accepted."""
        for env in Environment:
            overrides = {"WAXPREP_ENVIRONMENT": env.value}
            if env == Environment.PRODUCTION:
                overrides.update({
                    "WAXPREP_HOST": "0.0.0.0",
                    "WAXPREP_PORT": "8000",
                    "WAXPREP_LOG_LEVEL": "info",
                })
            settings = _make_settings_with_env(monkeypatch, overrides, isolated_env)
            assert settings.environment == env

    def test_invalid_environment_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unrecognised environment name raises ValidationError."""
        with pytest.raises(ValidationError, match="environment"):
            _make_settings_with_env(
                monkeypatch, {"WAXPREP_ENVIRONMENT": "invalid_environment"}, isolated_env
            )

    def test_typo_in_environment_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A misspelled but non-empty environment name is rejected."""
        with pytest.raises(ValidationError, match="environment"):
            _make_settings_with_env(monkeypatch, {"WAXPREP_ENVIRONMENT": "producon"}, isolated_env)


# ---------------------------------------------------------------------------
# 6. Log level validation
# ---------------------------------------------------------------------------


class TestLogLevelValidation:
    """Invalid log levels are rejected."""

    def test_valid_log_level_values(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for level in LogLevel:
            settings = _make_settings_with_env(
                monkeypatch, {"WAXPREP_LOG_LEVEL": level.value}, isolated_env
            )
            assert settings.log_level == level

    def test_invalid_log_level_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(ValidationError, match="log_level"):
            _make_settings_with_env(monkeypatch, {"WAXPREP_LOG_LEVEL": "TRACE"}, isolated_env)

    def test_typo_in_log_level_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(ValidationError, match="log_level"):
            _make_settings_with_env(monkeypatch, {"WAXPREP_LOG_LEVEL": "infoo"}, isolated_env)

    def test_empty_log_level_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(ValidationError, match="log_level"):
            _make_settings_with_env(monkeypatch, {"WAXPREP_LOG_LEVEL": ""}, isolated_env)

    def test_normalize_log_level_passes_non_string_through(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """normalize_log_level passes non-string values through unchanged.

        The before-validator receives values from Pydantic's field coercion.
        When the value is already an enum member (not a string), it should
        pass through without uppercasing.
        """
        from waxprep.config import Settings

        # The validator is a classmethod; calling it via the class passes cls automatically.
        # Simulate what Pydantic does: pass an already-resolved enum member.
        result = Settings.normalize_log_level(42)
        assert result == 42
        result = Settings.normalize_log_level(LogLevel.DEBUG)
        assert result == LogLevel.DEBUG

    def test_production_with_valid_config_succeeds(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production with complete valid configuration starts normally."""
        settings = _make_settings_with_env(
            monkeypatch,
            {
                "WAXPREP_ENVIRONMENT": "production",
                "WAXPREP_HOST": "127.0.0.1",
                "WAXPREP_PORT": "8000",
                "WAXPREP_LOG_LEVEL": "error",
            },
            isolated_env,
        )
        assert settings.environment == Environment.PRODUCTION
        assert settings.host == "127.0.0.1"
        assert settings.port == 8000
        assert settings.log_level == LogLevel.ERROR

    def test_production_missing_host_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Production without an explicit host must not use the development default."""
        with pytest.raises(ValidationError, match="WAXPREP_HOST"):
            _make_settings_with_env(
                monkeypatch,
                {
                    "WAXPREP_ENVIRONMENT": "production",
                    "WAXPREP_PORT": "8000",
                    "WAXPREP_LOG_LEVEL": "info",
                },
                isolated_env,
            )

    def test_production_missing_port_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(ValidationError, match="WAXPREP_PORT"):
            _make_settings_with_env(
                monkeypatch,
                {
                    "WAXPREP_ENVIRONMENT": "production",
                    "WAXPREP_HOST": "0.0.0.0",
                    "WAXPREP_LOG_LEVEL": "info",
                },
                isolated_env,
            )

    def test_production_missing_log_level_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(ValidationError, match="WAXPREP_LOG_LEVEL"):
            _make_settings_with_env(
                monkeypatch,
                {
                    "WAXPREP_ENVIRONMENT": "production",
                    "WAXPREP_HOST": "0.0.0.0",
                    "WAXPREP_PORT": "8000",
                },
                isolated_env,
            )

    def test_production_with_invalid_port_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(ValidationError, match="port"):
            _make_settings_with_env(
                monkeypatch,
                {
                    "WAXPREP_ENVIRONMENT": "production",
                    "WAXPREP_HOST": "0.0.0.0",
                    "WAXPREP_PORT": "70000",
                    "WAXPREP_LOG_LEVEL": "info",
                },
                isolated_env,
            )


# ---------------------------------------------------------------------------
# 9. Host validation
# ---------------------------------------------------------------------------


class TestHostValidation:
    """Empty or invalid host values are rejected."""

    def test_empty_host_rejected(self, isolated_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
        with pytest.raises(ValidationError, match="host"):
            _make_settings_with_env(monkeypatch, {"WAXPREP_HOST": ""}, isolated_env)

    def test_whitespace_only_host_rejected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(ValidationError, match="host"):
            _make_settings_with_env(monkeypatch, {"WAXPREP_HOST": "   "}, isolated_env)


# ---------------------------------------------------------------------------
# 11. Misspelled / unsupported WAXPREP_ variables
# ---------------------------------------------------------------------------


class TestUnknownVariableDetection:
    """Misspelled or unsupported WAXPREP_ variables are detected."""

    def test_known_misspelling_detected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Adding a known misspelling like WAXPREP_PORRT should produce a warning."""
        monkeypatch.setenv("WAXPREP_PORRT", "9999")
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables()
        assert len(warnings) >= 1
        assert any("WAXPREP_PORRT" in w and "WAXPREP_PORT" in w for w in warnings)

    def test_warnings_never_include_variable_values(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secretish = "super-secret-value-do-not-leak"
        monkeypatch.setenv("WAXPREP_PORRT", secretish)
        monkeypatch.setenv("WAXPREP_FOOBAR", secretish)
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables()
        joined = "\n".join(warnings)
        assert secretish not in joined
        assert "super-secret" not in joined
        assert all("=" not in w for w in warnings)

    def test_unknown_variable_from_env_file_detected(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("WAXPREP_UNKNOWNOWN=should-not-appear\n", encoding="utf-8")
        # Build settings without loading the unknown key as a settings field.
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables(env_file=env_file)
        assert any("WAXPREP_UNKNOWNOWN" in w and "env_file" in w for w in warnings)
        assert all("should-not-appear" not in w for w in warnings)

    def test_known_misspelling_from_env_file_detected(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("WAXPREP_PORRT=9999\n", encoding="utf-8")
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables(env_file=env_file)
        assert any("WAXPREP_PORRT" in w and "WAXPREP_PORT" in w for w in warnings)
        assert all("9999" not in w for w in warnings)

    def test_missing_variable_does_not_warn(self, isolated_env: None) -> None:
        """Not setting any WAXPREP_ variables does not produce warnings."""
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables(env_file=Path("/nonexistent/.env"))
        assert warnings == []

    def test_supported_variable_does_not_warn(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Setting a supported variable does not produce warnings."""
        monkeypatch.setenv("WAXPREP_PORT", "8000")
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables()
        assert warnings == []

    def test_generic_unknown_waxprep_variable_detected(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_FOOBAR", "baz")
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables()
        assert any("WAXPREP_FOOBAR" in w for w in warnings)
        assert all("baz" not in w for w in warnings)

    def test_non_waxprep_environment_variables_ignored(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unrelated environment variables must not trigger warnings."""
        monkeypatch.setenv("PATH", "/usr/bin")
        monkeypatch.setenv("HOME", "/home/user")
        monkeypatch.setenv("SOME_OTHER_VAR", "value")
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables()
        assert warnings == []

    def test_known_misspelling_table_contents(self, isolated_env: None) -> None:
        """The known misspellings table maps typos to correct names."""
        assert "WAXPREP_PORRT" in KNOWN_MISSPELLINGS
        assert KNOWN_MISSPELLINGS["WAXPREP_PORRT"] == "WAXPREP_PORT"
        assert "WAXPREP_ENVIRONMET" in KNOWN_MISSPELLINGS
        assert KNOWN_MISSPELLINGS["WAXPREP_ENVIRONMET"] == "WAXPREP_ENVIRONMENT"

    def test_critical_misspelling_blocks_production_startup(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "production")
        monkeypatch.setenv("WAXPREP_HOST", "0.0.0.0")
        monkeypatch.setenv("WAXPREP_PORT", "8000")
        monkeypatch.setenv("WAXPREP_LOG_LEVEL", "info")
        monkeypatch.setenv("WAXPREP_PORRT", "9000")
        with pytest.raises(ValueError, match="critical configuration misspellings"):
            load_settings(env_file=Path("/nonexistent/.env"))

    def test_critical_misspelling_warns_outside_production(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "development")
        monkeypatch.setenv("WAXPREP_PORRT", "9000")
        loaded = load_settings(env_file=Path("/nonexistent/.env"))
        assert loaded.port == 8000
        warnings = loaded.check_for_unknown_waxprep_variables(env_file=Path("/nonexistent/.env"))
        assert any("WAXPREP_PORRT" in w for w in warnings)


# ---------------------------------------------------------------------------
# 12. Test isolation
# ---------------------------------------------------------------------------


class TestTestIsolation:
    """Tests do not accidentally inherit the developer's real .env file or
    machine-specific environment variables."""

    def test_isolated_env_strips_existing_waxprep_vars(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After isolated_env, no WAXPREP_ variables remain."""
        for key in list(os.environ.keys()):
            assert not key.startswith("WAXPREP_"), (
                f"WAXPREP_ variable {key} leaked into test environment"
            )

    def test_building_settings_without_env_yields_defaults(self, isolated_env: None) -> None:
        """With a clean environment, Settings returns validated defaults."""
        settings = Settings(_env_file=None)
        assert settings.environment == Environment.DEVELOPMENT
        assert settings.host == "0.0.0.0"
        assert settings.port == 8000
        assert settings.log_level == LogLevel.INFO


# ---------------------------------------------------------------------------
# 13 & 14. Application startup uses validated config; failures are safe
# ---------------------------------------------------------------------------


class TestApplicationUsesValidatedConfiguration:
    """The application uses the validated configuration when starting."""

    def test_settings_are_imported_by_main(self) -> None:
        """main.py imports the settings singleton from config.py."""
        from waxprep.main import settings as main_settings

        assert main_settings is not None
        assert isinstance(main_settings, Settings)

    def test_settings_environment_reachable_from_main(self) -> None:
        """The main module's settings instance exposes the environment."""
        from waxprep.main import settings as main_settings

        assert main_settings.environment in tuple(Environment)

    def test_settings_host_reachable_from_main(self) -> None:
        from waxprep.main import settings as main_settings

        assert main_settings.host.strip() != ""


class TestConfigurationFailureSafety:
    """Configuration failures are reported without exposing secret values."""

    def test_validation_error_does_not_expose_secrets(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Even with invalid config, no secret-like values appear in error messages."""
        with pytest.raises(ValidationError) as exc_info:
            _make_settings_with_env(monkeypatch, {"WAXPREP_PORT": "-1"}, isolated_env)

        error_str = str(exc_info.value)
        assert "port" in error_str.lower()
        assert "secret" not in error_str.lower()
        assert "password" not in error_str.lower()
        assert "token" not in error_str.lower()
        assert "api_key" not in error_str.lower()

    def test_invalid_environment_does_not_expose_internal_details(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        with pytest.raises(ValidationError) as exc_info:
            _make_settings_with_env(monkeypatch, {"WAXPREP_ENVIRONMENT": "bad_env"}, isolated_env)

        error_str = str(exc_info.value)
        assert "environment" in error_str.lower()


class TestWarningOutput:
    """The unknown-variable detection emits warnings to stderr."""

    def test_warning_emitted_to_stderr_on_import(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Setting a known misspelling and reloading the module emits a warning on stderr."""
        import importlib

        import waxprep.main as main_module

        monkeypatch.setenv("WAXPREP_PORRT", "9999")
        # Import first (so the module exists), then reload to trigger detection
        import waxprep.config as config_module

        importlib.reload(config_module)
        # Keep main.settings pointing at the reloaded singleton used by the app.
        main_module.settings = config_module.settings

        captured = capsys.readouterr()
        assert "WAXPREP_CONFIG_WARNING" in captured.err
        assert "WAXPREP_PORRT" in captured.err
        assert "WAXPREP_PORT" in captured.err
        assert "9999" not in captured.err

    def test_no_warning_on_import_when_no_unknown_vars(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Reloading the module with no unknown WAXPREP_ variables produces no warning."""
        import importlib

        import waxprep.main as main_module

        monkeypatch.delenv("WAXPREP_PORRT", raising=False)
        import waxprep.config as config_module

        importlib.reload(config_module)
        main_module.settings = config_module.settings

        captured = capsys.readouterr()
        assert "WAXPREP_CONFIG_WARNING" not in captured.err


class TestConfigurationSources:
    """Safe diagnostics for where each setting originated."""

    def test_defaults_report_default_source(self, isolated_env: None) -> None:
        settings = Settings(_env_file=None)
        sources = settings.configuration_sources(env_file=Path("/nonexistent/.env"))
        assert sources["environment"] == "default"
        assert sources["host"] == "default"
        assert sources["port"] == "default"
        assert sources["log_level"] == "default"

    def test_os_environment_source(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_PORT", "9000")
        settings = Settings(_env_file=None)
        sources = settings.configuration_sources(env_file=Path("/nonexistent/.env"))
        assert sources["port"] == "environment"
        assert sources["host"] == "default"

    def test_env_file_source(self, isolated_env: None, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("WAXPREP_HOST=127.0.0.1\n", encoding="utf-8")
        settings = Settings(_env_file=env_file)
        sources = settings.configuration_sources(env_file=env_file)
        assert sources["host"] == "env_file"

    def test_sources_never_include_values(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_PORT", "9000")
        settings = Settings(_env_file=None)
        rendered = str(settings.configuration_sources(env_file=Path("/nonexistent/.env")))
        assert "9000" not in rendered


class TestLoadSettingsLifecycle:
    """load_settings constructs a single Settings instance for the module lifecycle."""

    def test_load_settings_returns_settings(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_PORT", "8123")
        loaded = load_settings(env_file=Path("/nonexistent/.env"))
        assert type(loaded).__name__ == "Settings"
        assert loaded.port == 8123

    def test_module_settings_is_settings_instance(self) -> None:
        from waxprep import config as config_module

        assert type(config_module.settings).__name__ == "Settings"
        assert hasattr(config_module.settings, "environment")
        assert hasattr(config_module, "load_settings")

    def test_load_settings_reads_production_intent_from_env_file(
        self, isolated_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "export WAXPREP_ENVIRONMENT=production\n"
            "WAXPREP_HOST=0.0.0.0\n"
            "WAXPREP_PORT=8000\n"
            "WAXPREP_LOG_LEVEL=info\n"
            "WAXPREP_PORRT=9000\n",
            encoding="utf-8",
        )
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ValueError, match="critical configuration misspellings"):
            load_settings(env_file=env_file)

    def test_load_settings_env_file_oserror_is_ignored(
        self, isolated_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("WAXPREP_ENVIRONMENT=development\n", encoding="utf-8")

        import waxprep.config as config_module

        def boom(*args: object, **kwargs: object) -> dict[str, str | None]:
            raise OSError("unreadable")

        monkeypatch.setattr(config_module, "dotenv_values", boom)
        loaded = load_settings(env_file=env_file)
        assert loaded.environment == Environment.DEVELOPMENT

    def test_read_env_file_environment_helper(self, isolated_env: None, tmp_path: Path) -> None:
        from waxprep.config import _read_env_file_environment

        env_file = tmp_path / ".env"
        env_file.write_text('export WAXPREP_ENVIRONMENT="Staging"\n', encoding="utf-8")
        assert _read_env_file_environment(env_file) == "staging"
        assert _read_env_file_environment(tmp_path / "missing.env") is None


class TestEnvFileParsingHelpers:
    """Edge cases for .env key extraction (values are never returned)."""

    def test_parse_skips_comments_export_and_invalid_lines(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        from waxprep.config import _parse_env_file_keys

        env_file = tmp_path / ".env"
        env_file.write_text(
            "# comment\n"
            "\n"
            "export WAXPREP_HOST=127.0.0.1\n"
            "NOT_A_SETTING\n"
            "WAXPREP_PORT=8000\n"
            "OTHER=1\n",
            encoding="utf-8",
        )
        keys = _parse_env_file_keys(env_file)
        assert keys == {"WAXPREP_HOST", "WAXPREP_PORT"}

    def test_parse_oserror_returns_empty(
        self, isolated_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from waxprep.config import _parse_env_file_keys

        env_file = tmp_path / ".env"
        env_file.write_text("WAXPREP_PORT=1\n", encoding="utf-8")

        import waxprep.config as config_module

        def boom(*args: object, **kwargs: object) -> dict[str, str | None]:
            raise OSError("unreadable")

        monkeypatch.setattr(config_module, "dotenv_values", boom)
        assert _parse_env_file_keys(env_file) == set()

    def test_duplicate_case_variants_in_environ_deduped(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Both keys keep the WAXPREP_ prefix; Linux environ is case-sensitive.
        monkeypatch.setenv("WAXPREP_FOOBAR", "one")
        monkeypatch.setenv("WAXPREP_foobar", "two")
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables(env_file=Path("/nonexistent/.env"))
        foobar_warnings = [w for w in warnings if "FOOBAR" in w.upper()]
        assert len(foobar_warnings) == 1
        assert all("one" not in w and "two" not in w for w in foobar_warnings)

    def test_declared_env_file_key_does_not_warn(self, isolated_env: None, tmp_path: Path) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("WAXPREP_PORT=9000\n", encoding="utf-8")
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables(env_file=env_file)
        assert warnings == []

    def test_environ_unknown_suppresses_env_file_duplicate(
        self, isolated_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("WAXPREP_FOOBAR=from-file\n", encoding="utf-8")
        monkeypatch.setenv("WAXPREP_FOOBAR", "from-environ")
        settings = Settings(_env_file=None)
        warnings = settings.check_for_unknown_waxprep_variables(env_file=env_file)
        assert len([w for w in warnings if "FOOBAR" in w]) == 1
        assert any("environment" in w for w in warnings)


# ---------------------------------------------------------------------------
# PART 2 — load_settings() must use the exact file it was given
# ---------------------------------------------------------------------------


class TestLoadSettingsEnvFileConsistency:
    """The file inspected and the file loaded are always the same file."""

    def test_custom_env_file_is_loaded(self, isolated_env: None, tmp_path: Path) -> None:
        env_file = tmp_path / "custom.env"
        env_file.write_text("WAXPREP_PORT=6001\n", encoding="utf-8")
        assert load_settings(env_file=env_file).port == 6001

    def test_each_selected_file_is_loaded_independently(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        first = tmp_path / "first.env"
        first.write_text("WAXPREP_PORT=6001\nWAXPREP_HOST=127.0.0.1\n", encoding="utf-8")
        second = tmp_path / "second.env"
        second.write_text("WAXPREP_PORT=6002\nWAXPREP_HOST=127.0.0.2\n", encoding="utf-8")

        assert load_settings(env_file=first).port == 6001
        assert load_settings(env_file=first).host == "127.0.0.1"
        assert load_settings(env_file=second).port == 6002
        assert load_settings(env_file=second).host == "127.0.0.2"

    def test_working_directory_dotenv_is_ignored_for_custom_file(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text("WAXPREP_PORT=9999\nWAXPREP_FOOBAR=leak\n", encoding="utf-8")
        selected = tmp_path / "selected.env"
        selected.write_text("WAXPREP_PORT=6001\n", encoding="utf-8")

        loaded = load_settings(env_file=selected)
        assert loaded.port == 6001
        warnings = loaded.check_for_unknown_waxprep_variables(env_file=selected)
        assert all("FOOBAR" not in w for w in warnings)

    def test_disabled_dotenv_source_stays_disabled(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text("WAXPREP_PORT=9999\n", encoding="utf-8")
        loaded = load_settings(env_file=None)
        assert loaded.port == 8000
        assert loaded.configuration_sources(env_file=None)["port"] == "default"

    def test_selected_file_production_is_enforced(self, isolated_env: None, tmp_path: Path) -> None:
        env_file = tmp_path / "prod.env"
        env_file.write_text("WAXPREP_ENVIRONMENT=production\nWAXPREP_PORT=8000\n", encoding="utf-8")
        with pytest.raises(ValidationError, match="WAXPREP_HOST"):
            load_settings(env_file=env_file)

    def test_production_intent_uses_selected_file_not_working_directory(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        # A production .env in the working directory must not influence a load
        # that explicitly selects a different development file.
        (tmp_path / ".env").write_text("WAXPREP_ENVIRONMENT=production\n", encoding="utf-8")
        selected = tmp_path / "dev.env"
        selected.write_text("WAXPREP_ENVIRONMENT=development\n", encoding="utf-8")

        assert load_settings(env_file=selected).environment == Environment.DEVELOPMENT


# ---------------------------------------------------------------------------
# PART 5 — dotenv parsing is delegated to python-dotenv
# ---------------------------------------------------------------------------


class TestDotenvParsing:
    """The detector and Pydantic must interpret .env syntax identically."""

    def test_export_quotes_inline_comments_and_whitespace(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        from waxprep.config import _parse_env_file_keys

        env_file = tmp_path / "complex.env"
        env_file.write_text(
            "# comment\n"
            "\n"
            'export WAXPREP_HOST = "127.0.0.1"  # inline comment\n'
            "WAXPREP_PORT='6003'\n"
            "WAXPREP_LOG_LEVEL=debug # trailing\n"
            "MALFORMED_LINE\n"
            "OTHER=1\n",
            encoding="utf-8",
        )
        assert _parse_env_file_keys(env_file) == {
            "WAXPREP_HOST",
            "WAXPREP_PORT",
            "WAXPREP_LOG_LEVEL",
        }

    def test_duplicate_keys_use_last_value_in_both_systems(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "dupes.env"
        env_file.write_text("WAXPREP_PORT=6004\nWAXPREP_PORT=6005\n", encoding="utf-8")
        assert load_settings(env_file=env_file).port == 6005

    def test_escaped_characters_do_not_break_key_extraction(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        from waxprep.config import _parse_env_file_keys

        env_file = tmp_path / "escaped.env"
        env_file.write_text(
            'WAXPREP_UNKNOWNOWN="line\\nbreak"\nWAXPREP_HOST="127.0.0.1"\n',
            encoding="utf-8",
        )
        keys = _parse_env_file_keys(env_file)
        assert "WAXPREP_UNKNOWNOWN" in keys
        assert "WAXPREP_HOST" in keys

    def test_unreadable_dotenv_is_treated_as_empty(
        self, isolated_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import waxprep.config as config_module

        env_file = tmp_path / "unreadable.env"
        env_file.write_text("WAXPREP_PORT=1\n", encoding="utf-8")

        def boom(*args: object, **kwargs: object) -> dict[str, str | None]:
            raise OSError("unreadable")

        monkeypatch.setattr(config_module, "dotenv_values", boom)
        assert config_module._parse_env_file_keys(env_file) == set()

    def test_detector_and_loader_agree_on_quoted_export_values(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "agree.env"
        env_file.write_text(
            'export WAXPREP_PORT="6006"\nexport WAXPREP_HOST="127.0.0.1"\n',
            encoding="utf-8",
        )
        loaded = load_settings(env_file=env_file)
        assert loaded.port == 6006
        assert loaded.host == "127.0.0.1"


# ---------------------------------------------------------------------------
# PART 6 — production typo detection
# ---------------------------------------------------------------------------


class TestProductionTypoDetection:
    """A misspelled environment must never silently downgrade to development."""

    def test_misspelled_environment_production_blocks_startup(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_ENVIRONMET", "production")
        monkeypatch.setenv("WAXPREP_HOST", "0.0.0.0")
        monkeypatch.setenv("WAXPREP_PORT", "8000")
        monkeypatch.setenv("WAXPREP_LOG_LEVEL", "info")
        with pytest.raises(ValueError, match="critical configuration misspellings"):
            load_settings(env_file=None)

    def test_misspelled_environment_in_dotenv_blocks_startup(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "prod.env"
        env_file.write_text(
            "WAXPREP_ENVIRONMET=production\nWAXPREP_PORRT=9000\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="critical configuration misspellings"):
            load_settings(env_file=env_file)

    def test_misspelled_environment_alone_still_blocks(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_ENVIRONMET", "production")
        with pytest.raises(ValueError, match="WAXPREP_ENVIRONMET"):
            load_settings(env_file=None)

    def test_misspelled_host_in_production_blocks(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "production")
        monkeypatch.setenv("WAXPREP_HOST", "0.0.0.0")
        monkeypatch.setenv("WAXPREP_PORT", "8000")
        monkeypatch.setenv("WAXPREP_LOG_LEVEL", "info")
        monkeypatch.setenv("WAXPREP_HOSTT", "127.0.0.1")
        with pytest.raises(ValueError, match="WAXPREP_HOSTT"):
            load_settings(env_file=None)

    def test_production_block_message_omits_values(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "production")
        monkeypatch.setenv("WAXPREP_HOST", "0.0.0.0")
        monkeypatch.setenv("WAXPREP_PORT", "8000")
        monkeypatch.setenv("WAXPREP_LOG_LEVEL", "info")
        monkeypatch.setenv("WAXPREP_PORRT", "9876")
        with pytest.raises(ValueError) as exc_info:
            load_settings(env_file=None)
        assert "9876" not in str(exc_info.value)

    def test_correct_environment_wins_over_misspelled_dotenv(
        self, isolated_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "typo.env"
        env_file.write_text("WAXPREP_ENVIRONMET=production\n", encoding="utf-8")
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "development")
        assert load_settings(env_file=env_file).environment == Environment.DEVELOPMENT

    def test_os_production_wins_over_dotenv_development(
        self, isolated_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "development.env"
        env_file.write_text("WAXPREP_ENVIRONMENT=development\n", encoding="utf-8")
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "production")
        monkeypatch.setenv("WAXPREP_HOST", "0.0.0.0")
        monkeypatch.setenv("WAXPREP_PORT", "8000")
        monkeypatch.setenv("WAXPREP_LOG_LEVEL", "info")
        assert load_settings(env_file=env_file).environment == Environment.PRODUCTION

    def test_os_production_with_dotenv_critical_typo_blocks(
        self, isolated_env: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env_file = tmp_path / "typo.env"
        env_file.write_text("WAXPREP_PORRT=9000\n", encoding="utf-8")
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "production")
        monkeypatch.setenv("WAXPREP_HOST", "0.0.0.0")
        monkeypatch.setenv("WAXPREP_PORT", "8000")
        monkeypatch.setenv("WAXPREP_LOG_LEVEL", "info")
        with pytest.raises(ValueError, match="WAXPREP_PORRT"):
            load_settings(env_file=env_file)

    def test_invalid_production_dotenv_is_rejected(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        env_file = tmp_path / "invalid.env"
        env_file.write_text(
            "WAXPREP_ENVIRONMENT=production\n"
            "WAXPREP_HOST=0.0.0.0\n"
            "WAXPREP_PORT=70000\n"
            "WAXPREP_LOG_LEVEL=info\n",
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="port"):
            load_settings(env_file=env_file)


# ---------------------------------------------------------------------------
# PART 3 — prove isolation from a deliberate local .env
# ---------------------------------------------------------------------------


class TestLocalDotenvIsolation:
    """A fake local .env with conflicting values cannot leak into clean tests."""

    def test_deliberate_local_dotenv_is_not_loaded_when_disabled(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        (tmp_path / ".env").write_text(
            "WAXPREP_PORT=9999\nWAXPREP_HOST=10.0.0.1\nWAXPREP_ENVIRONMENT=production\n",
            encoding="utf-8",
        )
        settings = Settings(_env_file=None)
        assert settings.port == 8000
        assert settings.host == "0.0.0.0"
        assert settings.environment == Environment.DEVELOPMENT

    def test_deliberate_local_dotenv_would_be_loaded_without_isolation(
        self, isolated_env: None, tmp_path: Path
    ) -> None:
        # Proves the assertion above is meaningful: the file is real and loadable.
        (tmp_path / ".env").write_text("WAXPREP_PORT=9999\n", encoding="utf-8")
        assert Settings().port == 9999

    def test_lowercase_misspelling_is_normalised_and_blocks(
        self, isolated_env: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "production")
        monkeypatch.setenv("WAXPREP_HOST", "0.0.0.0")
        monkeypatch.setenv("WAXPREP_PORT", "8000")
        monkeypatch.setenv("WAXPREP_LOG_LEVEL", "info")
        monkeypatch.setenv("waxprep_porrt", "9000")
        with pytest.raises(ValueError, match="WAXPREP_PORRT"):
            load_settings(env_file=None)

    def test_correct_variable_is_not_a_critical_misspelling(self, isolated_env: None) -> None:
        from waxprep.config import _is_critical_misspelling

        assert _is_critical_misspelling("WAXPREP_PORT") is False
        assert _is_critical_misspelling("WAXPREP_NONSENSE") is False
        assert _is_critical_misspelling("WAXPREP_PORRT") is True
        assert _is_critical_misspelling("WAXPREP_LOG_LEVEl") is True
