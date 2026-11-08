"""
Configuration Management - Stage 02
NO hardcoded values. All from environment.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. NO hardcoded values."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Use WAXPREP_ prefix to avoid conflicts with sandbox env vars
        env_prefix = "WAXPREP_",
    )

    # Application
    environment: str = Field(default="development")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Shutdown - configurable, NOT hardcoded
    shutdown_grace_period: int = Field(default=30)

    # Logging
    log_level: str = Field(default="info")


settings = Settings()
