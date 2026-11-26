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
from typing import TYPE_CHECKING

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    pass


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


class Settings(BaseSettings):
    """Validated application settings.

    Configured via WAXPREP_ environment variables.
    Development defaults are provided for convenience.
    Production deployments must supply their own values via environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="WAXPREP_",
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

    def check_for_unknown_waxprep_variables(self) -> list[str]:
        """Detect likely configuration mistakes from unsupported WAXPREP_ variables.

        Pydantic Settings ignores unknown OS environment variables by default,
        so a typo like WAXPREP_PORRT=8000 would silently fall back to the default.
        This method inspects the process environment for suspicious WAXPREP_ variables
        and returns a list of warnings.
        """
        warnings: list[str] = []
        waxprep_prefix = "WAXPREP_"

        for env_name, env_value in os.environ.items():
            if not env_name.startswith(waxprep_prefix):
                continue

            # Determine the field name without the prefix
            field_name = env_name[len(waxprep_prefix) :].lower()

            # Check if it matches a declared field (case-insensitive)
            declared_field_names = {
                field_name.lower() for field_name in Settings.model_fields.keys()
            }
            if field_name in declared_field_names:
                continue

            # Check known misspellings
            if env_name in KNOWN_MISSPELLINGS:
                suggested = KNOWN_MISSPELLINGS[env_name]
                warnings.append(
                    f"Unrecognised configuration variable {env_name}={env_value!r} "
                    f"— did you mean {suggested}?"
                )
                continue

            # Generic unknown WAXPREP_ variable
            warnings.append(
                f"Unrecognised configuration variable {env_name}={env_value!r} "
                f"— no matching setting found."
            )

        return warnings


def _detect_unknown_waxprep_variables() -> None:
    """Check for unsupported WAXPREP_ environment variables at import time.

    This runs once when config.py is first imported. It inspects the current
    process environment and warns about likely typos or unsupported variables.
    """
    settings_instance = Settings()
    warnings = settings_instance.check_for_unknown_waxprep_variables()
    if warnings:
        for warning in warnings:
            print(f"WAXPREP_CONFIG_WARNING: {warning}", file=sys.stderr)


# Trigger unknown-variable detection once at module import.
# This runs after the Settings class is defined so it has field metadata.
_detect_unknown_waxprep_variables()

# Module-level validated settings instance.
# Application code should import and use this rather than reading environment
# variables directly.
settings = Settings()
