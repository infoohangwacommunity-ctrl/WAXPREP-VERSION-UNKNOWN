"""
Model Registry - Stage 02
Registry for model adapters. NO import-time side effects.

Fake adapter source of truth: src/waxprep/adapters/fake_model.py
Register via register_defaults() method explicitly, not at import time.
"""

from typing import Protocol, runtime_checkable

from waxprep.registries.base import BaseRegistry


@runtime_checkable
class ModelAdapter(Protocol):
    """Model adapter protocol. NO implementation details."""

    name: str

    async def generate(self, prompt: str) -> str:
        """Generate a response."""
        ...


class ModelRegistry(BaseRegistry):
    """Registry for model adapters."""

    def register(self, name: str, item: ModelAdapter) -> None:
        """Register a model adapter. Validates protocol compliance."""
        if not hasattr(item, "name"):
            raise ValueError("Model adapter must have a 'name' attribute")
        if not hasattr(item, "generate") or not callable(item.generate):
            raise ValueError("Model adapter must have a callable 'generate' method")
        self._validate_not_duplicate(name)
        self._items[name] = item

    def register_defaults(self) -> None:
        """Register default fake adapter. Must be called explicitly."""
        from waxprep.adapters.fake_model import FakeModelAdapter

        self.register("fake", FakeModelAdapter())


def get_model_registry() -> ModelRegistry:
    """Get a fresh model registry. Call register_defaults() to populate."""
    return ModelRegistry()
