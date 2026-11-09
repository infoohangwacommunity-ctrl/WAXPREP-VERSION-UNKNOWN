"""
Model Port Interface - Stage 03.

Defines the contract for AI model gateway adapters.

This is a PORT in the Hexagonal Architecture pattern.
Adapters must implement this interface.

Dependency Rule: This module may import domain/ only.
It may NOT import adapters/, infrastructure/, or external frameworks.
"""

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from waxprep.domain.models.result import Error, Result


@runtime_checkable
class ModelPort(Protocol):
    """
    Abstract interface for AI model gateway adapters.

    All model providers (Upstage, OpenAI, Anthropic, etc.) must implement
    this protocol to be compatible with the WaxPrep application.

    This is the PORT. Adapters implement this.

    Error Handling:
    - Expected failures (rate limits, timeouts) return Result.err
    - Programming errors (bugs) raise exceptions
    """

    name: str

    async def generate(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> Result[str, Error]:
        """
        Generate a response from the AI model.

        Args:
            prompt: The prompt to generate a response for
            context: Optional context for the model (conversation history, etc.)

        Returns:
            Result containing the model's response or an error
        """
        ...

    async def stream(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
    ) -> AsyncIterator[Result[str, Error]]:
        """
        Stream a response from the AI model.

        Args:
            prompt: The prompt to generate a response for
            context: Optional context for the model

        Yields:
            Result objects containing chunks of the streaming response or errors
        """
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """
        Declare the capabilities of this model adapter.

        Returns:
            A dictionary describing the adapter's capabilities including:
            - provider: The AI provider name
            - model_name: The specific model name
            - max_tokens: Maximum tokens supported
            - supports_streaming: Whether streaming is supported
            - supports_tools: Whether tool calling is supported
            - context_window: Size of the context window
        """
        ...
