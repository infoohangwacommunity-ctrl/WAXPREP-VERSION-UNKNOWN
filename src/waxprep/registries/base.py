"""
Base Registry - Stage 02
Abstract base class for all registries.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, TypeVar

T = TypeVar("T")


class DuplicateRegistrationError(ValueError):
    """Raised when attempting to register an item with an already-used name."""

    pass


class BaseRegistry(ABC):
    """Base registry class. NO hardcoded adapters."""

    def __init__(self) -> None:
        self._items: Dict[str, Any] = {}

    @abstractmethod
    def register(self, name: str, item: T) -> None:  # noqa: V107
        """Register an item. Must validate before registering."""

    def get(self, name: str) -> Any:
        """Get a registered item by name."""
        if name not in self._items:
            raise KeyError(f"No item registered with name: {name}")
        return self._items[name]

    def list_all(self) -> list[str]:
        """List all registered item names."""
        return list(self._items.keys())

    def is_registered(self, name: str) -> bool:
        """Check if an item is registered."""
        return name in self._items

    def _validate_not_duplicate(self, name: str) -> None:
        """Raise DuplicateRegistrationError if name is already registered."""
        if name in self._items:
            raise DuplicateRegistrationError(f"Item already registered with name: {name}")
