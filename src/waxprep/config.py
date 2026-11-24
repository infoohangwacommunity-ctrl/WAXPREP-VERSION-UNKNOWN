"""
Configuration Management - Stage 02
All operational values configured via environment variables.
Acceptable defaults provided for development convenience.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings. Configured via WAXPREP_ environment variables.

    Acceptable defaults are provided for local development.
    Production deployments must override these via environment.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Use WAXPREP_ prefix to avoid conflicts with sandbox env vars
        env_prefix="WAXPREP_",
    )

    # Application
    environment: str = Field(default="development")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Logging
    log_level: str = Field(default="info")


settings = Settings()
