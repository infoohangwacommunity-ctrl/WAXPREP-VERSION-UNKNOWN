"""
Configuration Management - Stage 03
Extended configuration with validation and runtime checks.

Dependency Rule: This module may import domain/ and application/.
It may NOT import adapters/.
"""

from functools import lru_cache

from pydantic import DirectoryPath, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from waxprep.domain.exceptions import ValidationError


class Settings(BaseSettings):
    """Application settings with comprehensive validation.

    NO hardcoded values. All configuration from environment.
    Extended from Stage 02 with additional validation.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="WAXPREP_",
        # Validate on assignment
        validate_assignment=True,
        # Extra fields are not allowed
        extra="forbid",
    )

    # Application
    environment: str = Field(default="development")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    debug: bool = Field(default=False)

    # Shutdown configuration
    shutdown_grace_period: int = Field(default=30, ge=1, le=300)
    shutdown_timeout: int = Field(default=60, ge=1, le=600)

    # Logging
    log_level: str = Field(default="info")
    log_format: str = Field(default="json")
    log_directory: DirectoryPath | None = Field(default=None)

    # Rate limiting
    rate_limit_requests: int = Field(default=100, ge=1, le=10000)
    rate_limit_period: int = Field(default=60, ge=1, le=3600)

    # Message processing
    max_message_length: int = Field(default=4096, ge=100, le=100000)
    message_timeout_seconds: int = Field(default=30, ge=1, le=300)

    # Session configuration
    session_timeout_minutes: int = Field(default=30, ge=1, le=1440)
    max_messages_per_session: int = Field(default=1000, ge=10, le=10000)

    # Model provider configuration
    model_provider: str = Field(default="fake")
    model_name: str = Field(default="fake-model")
    model_api_key: str | None = Field(default=None)
    model_api_url: str | None = Field(default=None)
    model_timeout_seconds: int = Field(default=60, ge=1, le=600)
    model_max_tokens: int = Field(default=4096, ge=100, le=32768)

    # Channel configuration
    channel_provider: str = Field(default="fake")
    channel_api_key: str | None = Field(default=None)
    channel_webhook_secret: str | None = Field(default=None)

    # Security
    api_key: str | None = Field(default=None)
    webhook_secret: str | None = Field(default=None)

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = {"development", "staging", "production", "testing"}
        if v.lower() not in valid_envs:
            raise ValidationError(f"Invalid environment: {v}. Must be one of {valid_envs}")
        return v.lower()

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = {"debug", "info", "warning", "error", "critical"}
        if v.lower() not in valid_levels:
            raise ValidationError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v.lower()

    @field_validator("log_format")
    @classmethod
    def validate_log_format(cls, v: str) -> str:
        """Validate log format."""
        valid_formats = {"json", "text", "console"}
        if v.lower() not in valid_formats:
            raise ValidationError(f"Invalid log format: {v}. Must be one of {valid_formats}")
        return v.lower()

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.environment == "testing"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Use this for runtime settings access with caching.
    For testing, use Settings() directly to get fresh instances.
    """
    return Settings()


# Default settings instance
settings = get_settings()
