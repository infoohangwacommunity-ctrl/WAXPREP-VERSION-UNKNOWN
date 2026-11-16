"""
Fake Channel Adapter - Stage 02
ONLY for testing registry. NOT a real channel implementation.
"""

from typing import Any


class FakeChannelAdapter:
    """Fake channel adapter. Proves registry architecture works."""

    name = "fake"

    async def handle_message(self, message: dict[str, Any]) -> dict[str, Any]:
        """Fake handler. Does nothing real."""
        return {
            "status": "fake_processed",
            "message_id": message.get("id", "unknown"),
            "channel": self.name,
        }
