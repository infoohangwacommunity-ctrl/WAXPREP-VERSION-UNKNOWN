"""
Dependency Injection / Service Locator - Stage 03
Simple service locator pattern for dependency injection.

Dependency Rule: This module may import domain/ and application/.
It may NOT import adapters/ directly (adapters are registered at runtime).
"""

from collections.abc import Callable
from typing import Any, TypeVar

from waxprep.infrastructure.logging import get_logger

T = TypeVar("T")

logger = get_logger(__name__)


class ServiceLocator:
    """Simple service locator for dependency injection.

    This provides a way to register and retrieve services without
    creating tight coupling between components.

    Usage:
        # Register a service
        locator = ServiceLocator()
        locator.register(ChannelPort, my_channel_adapter)

        # Retrieve a service
        channel = locator.get(ChannelPort)
    """

    def __init__(self) -> None:
        self._services: dict[type, Any] = {}
        self._factories: dict[type, Callable[[], Any]] = {}
        self._singletons: dict[type, Any] = {}

    def register(
        self,
        service_type: type[T],
        instance: T,
        singleton: bool = True,
    ) -> None:
        """Register a service instance.

        Args:
            service_type: The type/interface of the service
            instance: The service instance
            singleton: Whether to cache the instance
        """
        if singleton:
            self._singletons[service_type] = instance
        else:
            self._services[service_type] = instance
        logger.debug(
            "ServiceLocator: Registered service",
            service_type=service_type.__name__,
            singleton=singleton,
        )

    def register_factory(
        self,
        service_type: type[T],
        factory: Callable[[], T],
    ) -> None:
        """Register a factory function for a service.

        Args:
            service_type: The type/interface of the service
            factory: A callable that creates the service instance
        """
        self._factories[service_type] = factory
        logger.debug(
            "ServiceLocator: Registered factory",
            service_type=service_type.__name__,
        )

    def get(self, service_type: type[T]) -> T:
        """Get a service instance.

        Args:
            service_type: The type/interface of the service

        Returns:
            The service instance

        Raises:
            KeyError: If the service is not registered
        """
        # Check singletons first
        if service_type in self._singletons:
            return self._singletons[service_type]

        # Check factories
        if service_type in self._factories:
            factory = self._factories[service_type]
            instance = factory()
            # Cache the instance for future requests
            self._singletons[service_type] = instance
            return instance

        # Check regular services
        if service_type in self._services:
            return self._services[service_type]

        raise KeyError(f"Service not registered: {service_type.__name__}")

    def get_optional(self, service_type: type[T]) -> T | None:
        """Get a service instance if registered, otherwise None.

        Args:
            service_type: The type/interface of the service

        Returns:
            The service instance or None
        """
        try:
            return self.get(service_type)
        except KeyError:
            return None

    def has(self, service_type: type[T]) -> bool:
        """Check if a service is registered.

        Args:
            service_type: The type/interface of the service

        Returns:
            True if the service is registered
        """
        return (
            service_type in self._services
            or service_type in self._factories
            or service_type in self._singletons
        )

    def unregister(self, service_type: type[T]) -> bool:
        """Unregister a service.

        Args:
            service_type: The type/interface of the service

        Returns:
            True if the service was unregistered
        """
        removed = False
        if service_type in self._services:
            del self._services[service_type]
            removed = True
        if service_type in self._factories:
            del self._factories[service_type]
            removed = True
        if service_type in self._singletons:
            del self._singletons[service_type]
            removed = True

        if removed:
            logger.debug(
                "ServiceLocator: Unregistered service",
                service_type=service_type.__name__,
            )

        return removed

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        logger.debug("ServiceLocator: Cleared all services")

    def list_services(self) -> list[str]:
        """List all registered service types.

        Returns:
            List of service type names
        """
        all_types = set()
        all_types.update(self._services.keys())
        all_types.update(self._factories.keys())
        all_types.update(self._singletons.keys())
        return [t.__name__ for t in all_types]


# Global service locator instance
_service_locator: ServiceLocator | None = None


def get_service_locator() -> ServiceLocator:
    """Get the global service locator."""
    global _service_locator
    if _service_locator is None:
        _service_locator = ServiceLocator()
    return _service_locator


def reset_service_locator() -> None:
    """Reset the global service locator (for testing)."""
    global _service_locator
    if _service_locator is not None:
        _service_locator.clear()
        _service_locator = None
