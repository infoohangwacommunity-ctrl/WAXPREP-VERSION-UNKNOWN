"""
Fake Channel Adapter - Stage 02
ONLY for testing registry. NOT a real channel implementation.
"""


class FakeChannelAdapter:
    """Fake channel adapter. Proves registry architecture works."""

    name = "fake"

    async def handle_message(self, message: dict) -> dict:
        """Fake handler. Does nothing real."""
        return {
            "status": "fake_processed",
            "message_id": message.get("id", "unknown"),
            "channel": self.name,
        }
