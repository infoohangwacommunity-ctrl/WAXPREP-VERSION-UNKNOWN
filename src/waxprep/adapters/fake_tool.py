"""
Fake Tool - Stage 02
ONLY for testing registry. NOT a real tool implementation.
"""

from typing import Any


class FakeTool:
    """Fake tool. Proves registry architecture works."""

    name = "fake_tool"

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Fake execution. Does nothing real."""
        return {
            "status": "fake_executed",
            "input": kwargs,
            "tool": self.name,
        }
