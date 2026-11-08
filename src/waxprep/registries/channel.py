"""
Channel Registry - Stage 02
Registry for channel adapters. Contains ONE fake adapter to prove it works.
NO real WhatsApp. NO real Telegram. Only fake for testing.
"""

from typing import Protocol, runtime_checkable

from waxprep.registries.base import BaseRegistry


@runtime_checkable
class ChannelAdapter(Protocol):
    """Channel adapter protocol. NO implementation details."""

    name: str

    async def handle_message(self, message: dict) -> dict:
        """Handle an incoming message."""
        ...


class ChannelRegistry(BaseRegistry[ChannelAdapter]):
    """Registry for channel adapters."""

    def register(self, name: str, adapter: ChannelAdapter) -> None:
        """Register a channel adapter."""
        if not hasattr(adapter, "name"):
            raise ValueError("Channel adapter must have a 'name' attribute")
        if not hasattr(adapter, "handle_message"):
            raise ValueError("Channel adapter must have a 'handle_message' method")
        self._items[name] = adapter


# FAKE adapter for testing only - proves registry works
class FakeChannelAdapter:
    """Fake channel adapter. NOT a real implementation."""

    name = "fake"

    async def handle_message(self, message: dict) -> dict:
        """Fake handler. Does nothing real."""
        return {"status": "fake_processed", "message_id": message.get("id")}


# Register the fake adapter
_default_channel_registry = ChannelRegistry()
_default_channel_registry.register("fake", FakeChannelAdapter())


def get_channel_registry() -> ChannelRegistry:
    """Get the default channel registry with fake adapter."""
    return _default_channel_registry
