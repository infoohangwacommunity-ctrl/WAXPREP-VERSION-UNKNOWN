"""
Configuration Management - Stage 11

Centralised, validated application configuration via Pydantic Settings.
All operational values are configured through WAXPREP_ environment variables.

Configuration sources (in precedence order):
1. Explicit runtime or test overrides (where intentionally supported)
2. Operating-system environment variables
3. Local .env file
4. Validated development defaults

The application must not start with invalid configuration.
Invalid configuration produces a clear validation error without exposing secrets.
"""

from __future__ import annotations

import os
import sys
from enum import StrEnum
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ConfigSource = Literal["environment", "env_file", "default"]

# Fields that production deployments must supply explicitly (not from defaults).
_PRODUCTION_REQUIRED_FIELDS: tuple[str, ...] = ("host", "port", "log_level")


class Environment(StrEnum):
    """Recognised deployment environments."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Recognised log levels, normalised to uppercase."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# Known misspelling targets — environment variables that look like WaxPrep settings
# but do not match any declared field. These are likely typos.
KNOWN_MISSPELLINGS: dict[str, str] = {
    "WAXPREP_PORRT": "WAXPREP_PORT",
    "WAXPREP_ENVIRONMET": "WAXPREP_ENVIRONMENT",
    "WAXPREP_LOG_LEVEl": "WAXPREP_LOG_LEVEL",
    "WAXPREP_HOSTT": "WAXPREP_HOST",
}

# Critical settings: a known misspelling of these must not silently use defaults
# in production (startup fails). In non-production they remain warnings.
_CRITICAL_SETTING_NAMES: frozenset[str] = frozenset({"PORT", "ENVIRONMENT", "HOST", "LOG_LEVEL"})


def _declared_env_names() -> set[str]:
    """Return uppercase env names for all Settings fields (with WAXPREP_ prefix)."""
    return {f"WAXPREP_{name.upper()}" for name in Settings.model_fields}


def _iter_env_file_entries(env_file: Path | None) -> list[tuple[str, str]]:
    """Return (key, value) pairs from a .env file for WAXPREP_ keys only.

    Parsing is delegated to ``python-dotenv`` so the detector and Pydantic
    Settings interpret the same file syntax identically (quotes, ``export``,
    inline comments, duplicate keys, escapes and malformed entries).

    Callers must not log or expose values outside production-intent checks.
    """
    if env_file is None or not env_file.is_file():
        return []
    try:
        parsed = dotenv_values(env_file, encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return []

    entries: list[tuple[str, str]] = []
    for key, value in parsed.items():
        if not key.startswith("WAXPREP_"):
            continue
        entries.append((key, "" if value is None else value))
    return entries


def _as_env_path(env_file: str | Path | None) -> Path | None:
    """Normalise an env_file argument, preserving an explicitly disabled source."""
    if env_file is None:
        return None
    return Path(env_file)


def _parse_env_file_keys(env_file: str | Path | None) -> set[str]:
    """Return WAXPREP_ key names present in a .env file (values are never returned)."""
    return {key for key, _value in _iter_env_file_entries(_as_env_path(env_file))}


def _read_env_file_environment(env_file: Path | None) -> str | None:
    """Return the WAXPREP_ENVIRONMENT value from a .env file, if present."""
    expected = f"WAXPREP_{'environment'.upper()}"
    for key, value in _iter_env_file_entries(env_file):
        if key.upper() == expected:
            return value.strip().lower()
    return None


def _explicit_environment_value(env_file: Path | None) -> str | None:
    """Return the effective explicitly configured environment (OS env wins)."""
    from_process = os.environ.get("WAXPREP_ENVIRONMENT")
    if from_process is not None:
        return from_process.strip().lower()
    return _read_env_file_environment(env_file)


def _detect_production_intent(env_file: Path | None) -> bool:
    """Return True when the effective configuration is intended for production.

    The correctly spelled ``WAXPREP_ENVIRONMENT`` takes precedence. Only when it
    is absent do we honour a misspelled ``WAXPREP_ENVIRONMET=production`` so that
    a typo cannot silently downgrade a production deployment to development.
    """
    explicit = _explicit_environment_value(env_file)
    if explicit is not None:
        return explicit == Environment.PRODUCTION.value

    values = [value for key, value in os.environ.items() if key.upper() == "WAXPREP_ENVIRONMET"]
    values.extend(
        value
        for key, value in _iter_env_file_entries(env_file)
        if key.upper() == "WAXPREP_ENVIRONMET"
    )
    return any(value.strip().lower() == Environment.PRODUCTION.value for value in values)


def _format_unknown_variable_warning(
    env_name: str,
    *,
    source: str,
) -> str:
    """Build a safe warning that never includes variable values."""
    if env_name in KNOWN_MISSPELLINGS:
        suggested = KNOWN_MISSPELLINGS[env_name]
        return (
            f"Unrecognised configuration variable {env_name} "
            f"(from {source}) — did you mean {suggested}?"
        )
    return (
        f"Unrecognised configuration variable {env_name} "
        f"(from {source}) — no matching setting found."
    )


def _canonical_misspelling(env_name: str) -> str | None:
    """Return the KNOWN_MISSPELLINGS key for a typo, if it is one.

    Exact matches are checked first so entries that only differ by casing
    (e.g. ``WAXPREP_LOG_LEVEl``) are not mistaken for the correctly spelled
    variable when uppercased.
    """
    if env_name in KNOWN_MISSPELLINGS:
        return env_name
    canonical = env_name.upper()
    if canonical in KNOWN_MISSPELLINGS:
        return canonical
    return None


def _is_critical_misspelling(env_name: str) -> bool:
    misspelling = _canonical_misspelling(env_name)
    if misspelling is None:
        return False
    suggested = KNOWN_MISSPELLINGS[misspelling]
    suffix = suggested.removeprefix("WAXPREP_")
    return suffix in _CRITICAL_SETTING_NAMES


class Settings(BaseSettings):
    """Validated application settings.

    Configured via WAXPREP_ environment variables.
    Development defaults are provided for convenience.
    Production deployments must supply host, port, and log_level explicitly.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="WAXPREP_",
        # Unknown keys are reported by check_for_unknown_waxprep_variables(),
        # not by Pydantic extras — keep OS env and .env behaviour aligned.
        extra="ignore",
    )

    environment: Environment = Field(
        default=Environment.DEVELOPMENT,
        description="Deployment environment. One of: development, test, staging, production.",
    )
    host: str = Field(
        default="0.0.0.0",
        description="Network host to bind to. Must be non-empty.",
    )
    port: int = Field(
        default=8000,
        description="Network port to bind to. Must be between 1 and 65535.",
    )
    log_level: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application log level. One of: DEBUG, INFO, WARNING, ERROR, CRITICAL.",
    )

    @field_validator("host")
    @classmethod
    def host_must_not_be_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("host must be a non-empty string")
        return value.strip()

    @field_validator("port")
    @classmethod
    def port_must_be_in_range(cls, value: int) -> int:
        if value < 1 or value > 65535:
            raise ValueError(f"port must be between 1 and 65535, got {value}")
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        """Normalise log level strings to uppercase so 'info' and 'INFO' behave the same."""
        if isinstance(value, str):
            return value.upper()
        return value

    @model_validator(mode="after")
    def enforce_production_explicit_settings(self) -> Settings:
        """Reject production configs that silently rely on development defaults."""
        if self.environment != Environment.PRODUCTION:
            return self

        missing = [
            field for field in _PRODUCTION_REQUIRED_FIELDS if field not in self.model_fields_set
        ]
        if missing:
            names = ", ".join(f"WAXPREP_{name.upper()}" for name in missing)
            raise ValueError(
                "Production requires explicitly supplied configuration for: "
                f"{names}. Development defaults must not be used in production."
            )
        return self

    def check_for_unknown_waxprep_variables(
        self,
        *,
        env_file: str | Path | None = ".env",
    ) -> list[str]:
        """Detect likely configuration mistakes from unsupported WAXPREP_ variables.

        Inspects both the process environment and the local .env file.
        Warning messages never include variable values.
        """
        warnings: list[str] = []
        declared = _declared_env_names()
        seen: set[str] = set()

        for env_name in os.environ:
            if not env_name.upper().startswith("WAXPREP_"):
                continue
            misspelling = _canonical_misspelling(env_name)
            if misspelling is None:
                canonical = env_name.upper()
                if canonical in declared:
                    continue
            else:
                canonical = misspelling
            if canonical in seen:
                continue
            seen.add(canonical)
            warnings.append(_format_unknown_variable_warning(canonical, source="environment"))

        for env_name in _parse_env_file_keys(_as_env_path(env_file)):
            misspelling = _canonical_misspelling(env_name)
            if misspelling is None:
                canonical = env_name.upper()
                if canonical in declared:
                    continue
            else:
                canonical = misspelling
            # Already reported from the OS environment (including case variants).
            if canonical in seen:
                continue
            seen.add(canonical)
            warnings.append(_format_unknown_variable_warning(canonical, source="env_file"))

        return warnings

    def collect_critical_misspellings(
        self,
        *,
        env_file: str | Path | None = ".env",
    ) -> list[str]:
        """Return known critical misspellings found in environment or .env."""
        found: list[str] = []
        seen: set[str] = set()
        candidates = list(os.environ.keys()) + list(_parse_env_file_keys(_as_env_path(env_file)))
        for env_name in candidates:
            misspelling = _canonical_misspelling(env_name)
            if misspelling is not None and _is_critical_misspelling(misspelling):
                if misspelling not in seen:
                    seen.add(misspelling)
                    found.append(misspelling)
        return found

    def configuration_sources(
        self,
        *,
        env_file: str | Path | None = ".env",
    ) -> dict[str, ConfigSource]:
        """Return where each setting's effective value originated (never values).

        Precedence: OS environment > .env file > default.
        """
        env_file_keys = {k.upper() for k in _parse_env_file_keys(_as_env_path(env_file))}
        sources: dict[str, ConfigSource] = {}
        for field_name in type(self).model_fields:
            env_name = f"WAXPREP_{field_name.upper()}"
            if any(k.upper() == env_name for k in os.environ):
                sources[field_name] = "environment"
            elif env_name in env_file_keys:
                sources[field_name] = "env_file"
            else:
                sources[field_name] = "default"
        return sources


def _emit_config_warnings(warnings: list[str]) -> None:
    for warning in warnings:
        print(f"WAXPREP_CONFIG_WARNING: {warning}", file=sys.stderr)


def load_settings(*, env_file: str | Path | None = ".env") -> Settings:
    """Load and validate settings once, then report unknown-variable warnings.

    The same ``env_file`` is used for one consistent view of configuration:
    the file Pydantic Settings loads, the file inspected for unknown variables,
    and the file used for production-intent detection. Passing ``None`` disables
    dotenv loading entirely.

    Known critical misspellings fail startup when targeting production
    (via WAXPREP_ENVIRONMENT=production in the process environment or .env),
    including when production is only expressed through the misspelled
    WAXPREP_ENVIRONMET variable.
    """
    selected_file = _as_env_path(env_file)

    # Detect production intent before constructing Settings so a misspelled
    # port cannot silently fall through to the default during validation.
    production_intent = _detect_production_intent(selected_file)

    # Load exactly the selected file — never the implicit working-directory .env.
    # pydantic-settings accepts _env_file at runtime; its generated __init__
    # signature does not expose the keyword to mypy.
    provisional = Settings(_env_file=selected_file)  # type: ignore[call-arg]

    critical = provisional.collect_critical_misspellings(env_file=selected_file)
    if critical and production_intent:
        names = ", ".join(critical)
        raise ValueError(
            "Production startup blocked due to critical configuration misspellings: "
            f"{names}. Correct the variable names and restart. "
            "(Variable values are intentionally omitted.)"
        )

    warnings = provisional.check_for_unknown_waxprep_variables(env_file=selected_file)
    if warnings:
        _emit_config_warnings(warnings)

    return provisional


# Module-level validated settings instance.
# Application code should import and use this rather than reading environment
# variables directly. Constructed once via load_settings() — no duplicate
# Settings() call for detection.
settings = load_settings()
