"""
Channel Registry - Stage 02
Registry for channel adapters. NO import-time side effects.

Fake adapter source of truth: src/waxprep/adapters/fake_channel.py
Register via register_defaults() method explicitly, not at import time.
"""

from typing import Any, Protocol, runtime_checkable

from waxprep.registries.base import BaseRegistry


@runtime_checkable
class ChannelAdapter(Protocol):
    """Channel adapter protocol. NO implementation details."""

    name: str

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Handle an incoming message."""
        ...


class ChannelRegistry(BaseRegistry):
    """Registry for channel adapters."""

    def register(self, name: str, item: object) -> None:
        """Register a channel adapter. Validates protocol compliance."""
        if not hasattr(item, "name"):
            raise ValueError("Channel adapter must have a 'name' attribute")
        if not hasattr(item, "handle_message") or not callable(item.handle_message):
            raise ValueError("Channel adapter must have a callable 'handle_message' method")
        self._validate_not_duplicate(name)
        self._items[name] = item

    def register_defaults(self) -> None:
        """Register default fake adapter. Must be called explicitly."""
        from waxprep.adapters.fake_channel import FakeChannelAdapter

        self.register("fake", FakeChannelAdapter())


def get_channel_registry() -> ChannelRegistry:
    """Get a fresh channel registry. Call register_defaults() to populate."""
    return ChannelRegistry()
