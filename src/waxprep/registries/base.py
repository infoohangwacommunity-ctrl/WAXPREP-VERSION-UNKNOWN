"""
Base Registry - Stage 02
Abstract base class for all registries.
"""

from abc import ABC, abstractmethod
from typing import Dict, Generic, TypeVar, List

T = TypeVar('T')


class BaseRegistry(ABC, Generic[T]):
    """Base registry class. NO hardcoded adapters."""

    def __init__(self) -> None:
        self._items: Dict[str, T] = {}

    @abstractmethod
    def register(self, name: str, item: T) -> None:
        """Register an item. Must validate before registering."""
        pass

    def get(self, name: str) -> T:
        """Get a registered item by name."""
        if name not in self._items:
            raise KeyError(f"No item registered with name: {name}")
        return self._items[name]

    def list_all(self) -> List[str]:
        """List all registered item names."""
        return list(self._items.keys())

    def is_registered(self, name: str) -> bool:
        """Check if an item is registered."""
        return name in self._items
