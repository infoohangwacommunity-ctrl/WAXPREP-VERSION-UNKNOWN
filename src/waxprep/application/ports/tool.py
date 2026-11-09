"""
Tool Port Interface - Stage 03.

Defines the contract for tool adapters.

This is a PORT in the Hexagonal Architecture pattern.
Adapters must implement this interface.

Dependency Rule: This module may import domain/ only.
It may NOT import adapters/, infrastructure/, or external frameworks.
"""

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from waxprep.domain.models.result import Error, Result


@runtime_checkable
class ToolPort(Protocol):
    """
    Abstract interface for tool adapters.

    All tools (embedding providers, external APIs, calculators, etc.)
    must implement this protocol to be compatible with the WaxPrep application.

    This is the PORT. Adapters implement this.

    Error Handling:
    - Expected failures (API errors, invalid input) return Result.err
    - Programming errors (bugs) raise exceptions
    """

    name: str

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> Result[dict[str, Any], Error]:
        """
        Execute the tool with given arguments.

        Args:
            tool_name: The name of the tool to execute
            arguments: The arguments for the tool
            context: Optional context for the tool

        Returns:
            Result containing the tool execution result or an error
        """
        ...

    async def execute_streaming(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[Result[dict[str, Any], Error]]:
        """
        Execute the tool with streaming output.

        Args:
            tool_name: The name of the tool to execute
            arguments: The arguments for the tool
            context: Optional context for streaming

        Yields:
            Result objects containing chunks of the streaming result or errors
        """
        ...

    def validate_arguments(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Result[bool, Error]:
        """
        Validate arguments for a tool before execution.

        Args:
            tool_name: The name of the tool
            arguments: The arguments to validate

        Returns:
            Result indicating whether arguments are valid
        """
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """
        Declare the capabilities of this tool adapter.

        Returns:
            A dictionary describing the adapter's capabilities including:
            - available_tools: List of available tool names
            - supports_streaming: Whether streaming execution is supported
            - rate_limits: Rate limit information
        """
        ...
