"""
Tool Registry - Stage 02
Registry for tools. NO import-time side effects.

Fake tool source of truth: src/waxprep/adapters/fake_tool.py
Register via register_defaults() method explicitly, not at import time.
"""

from typing import Any, Protocol, runtime_checkable

from waxprep.registries.base import BaseRegistry


@runtime_checkable
class Tool(Protocol):
    """Tool protocol. NO implementation details."""

    name: str

    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Execute the tool."""
        ...


class ToolRegistry(BaseRegistry[Tool]):
    """Registry for tools."""

    def register(self, name: str, item: Tool) -> None:
        """Register a tool. Validates protocol compliance."""
        if not hasattr(item, "name"):
            raise ValueError("Tool must have a 'name' attribute")
        if not hasattr(item, "execute") or not callable(item.execute):
            raise ValueError("Tool must have a callable 'execute' method")
        self._validate_not_duplicate(name)
        self._items[name] = item

    def register_defaults(self) -> None:
        """Register default fake tool. Must be called explicitly."""
        from waxprep.adapters.fake_tool import FakeTool

        self.register("fake_tool", FakeTool())


def get_tool_registry() -> ToolRegistry:
    """Get a fresh tool registry. Call register_defaults() to populate."""
    return ToolRegistry()
