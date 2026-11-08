"""
Tool Registry - Stage 02
Registry for tools. Contains ONE fake tool to prove it works.
NO real tools. Only fake for testing.
"""

from typing import Protocol, runtime_checkable
from waxprep.registries.base import BaseRegistry


@runtime_checkable
class Tool(Protocol):
    """Tool protocol. NO implementation details."""

    name: str

    async def execute(self, **kwargs) -> dict:
        """Execute the tool."""
        ...


class ToolRegistry(BaseRegistry[Tool]):
    """Registry for tools."""

    def register(self, name: str, tool: Tool) -> None:
        """Register a tool."""
        if not hasattr(tool, 'name'):
            raise ValueError("Tool must have a 'name' attribute")
        if not hasattr(tool, 'execute'):
            raise ValueError("Tool must have an 'execute' method")
        self._items[name] = tool


# FAKE tool for testing only - proves registry works
class FakeTool:
    """Fake tool. NOT a real implementation."""

    name = "fake_tool"

    async def execute(self, **kwargs) -> dict:
        """Fake execution. Does nothing real."""
        return {"status": "fake_executed", "input": kwargs}


# Register the fake tool
_default_tool_registry = ToolRegistry()
_default_tool_registry.register("fake_tool", FakeTool())


def get_tool_registry() -> ToolRegistry:
    """Get the default tool registry with fake tool."""
    return _default_tool_registry
