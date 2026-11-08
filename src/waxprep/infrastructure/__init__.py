"""
Infrastructure Layer - Stage 03

Runtime concerns: configuration, lifecycle, logging.

Dependency Rule: This module may import domain/ and application/.
It may NOT import adapters/.

This layer contains:
- Configuration management (extended from Stage 02)
- Application lifecycle management
- Logging configuration
- Dependency injection / service locator
"""

from waxprep.infrastructure.config import get_settings, settings
from waxprep.infrastructure.di import ServiceLocator
from waxprep.infrastructure.lifecycle import LifecycleManager
from waxprep.infrastructure.logging import configure_logging, get_logger

__all__ = [
    "LifecycleManager",
    "ServiceLocator",
    "configure_logging",
    "get_logger",
    "get_settings",
    "settings",
]
