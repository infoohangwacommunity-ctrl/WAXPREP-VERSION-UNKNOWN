"""
Model Port Interface - Stage 03.

Defines the contract for AI model gateway adapters.

This is a PORT in the Hexagonal Architecture pattern.
Adapters must implement this interface.

Dependency Rule: This module may import domain/ only.
It may NOT import adapters/, infrastructure/, or external frameworks.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from waxprep.domain.models.message import Message
    from waxprep.domain.models.result import Error, Result
    from waxprep.domain.models.session import Session
    from waxprep.domain.value_objects import StudentId


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
        session: Session | None = None,
        student_id: StudentId | None = None,
    ) -> Result[str, Error]:
        """
        Generate a response from the AI model.

        Args:
            prompt: The prompt to generate a response for
            context: Optional context for the model (conversation history, etc.)
            session: Optional session for maintaining conversation state
            student_id: Optional student ID for personalization

        Returns:
            Result containing the model's response or an error
        """
        ...

    async def stream(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        session: Session | None = None,
        student_id: StudentId | None = None,
    ) -> AsyncIterator[Result[str, Error]]:
        """
        Stream a response from the AI model.

        Args:
            prompt: The prompt to generate a response for
            context: Optional context for the model
            session: Optional session for maintaining conversation state
            student_id: Optional student ID for personalization

        Yields:
            Result objects containing chunks of the streaming response or errors
        """
        ...

    async def analyze_message(
        self,
        message: Message,
        session: Session | None = None,
    ) -> Result[dict[str, Any], Error]:
        """
        Analyze a message to extract intent, entities, and other metadata.

        Args:
            message: The message to analyze
            session: Optional session for context

        Returns:
            Result containing analysis data including:
            - intent: The student's intent
            - entities: Extracted entities (subjects, concepts, etc.)
            - confidence: Confidence score
            - action: Recommended action
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
