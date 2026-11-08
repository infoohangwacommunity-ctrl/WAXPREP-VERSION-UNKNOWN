"""
Model Registry - Stage 02
Registry for model adapters. Contains ONE fake adapter to prove it works.
NO real AI providers. NO real model implementations. Only fake for testing.
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


class ModelRegistry(BaseRegistry[ModelAdapter]):
    """Registry for model adapters."""

    def register(self, name: str, adapter: ModelAdapter) -> None:
        """Register a model adapter."""
        if not hasattr(adapter, "name"):
            raise ValueError("Model adapter must have a 'name' attribute")
        if not hasattr(adapter, "generate"):
            raise ValueError("Model adapter must have a 'generate' method")
        self._items[name] = adapter


# FAKE adapter for testing only - proves registry works
class FakeModelAdapter:
    """Fake model adapter. NOT a real implementation."""

    name = "fake"

    async def generate(self, prompt: str) -> str:
        """Fake generator. Returns fake response."""
        return f"Fake response to: {prompt[:50]}..."


# Register the fake adapter
_default_model_registry = ModelRegistry()
_default_model_registry.register("fake", FakeModelAdapter())


def get_model_registry() -> ModelRegistry:
    """Get the default model registry with fake adapter."""
    return _default_model_registry
