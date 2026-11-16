"""
Core Protocols - Stage 03
Abstract interfaces for messaging and context systems.

These protocols define WHAT components must do, not HOW they do it.
Implementations live in adapters/ or concrete packages.

Design principle: Protocols are intentionally minimal and flexible.
Do NOT add student types, subject categories, or ability levels here.
"""

from typing import Protocol, runtime_checkable, Any, Dict, Optional


@runtime_checkable
class Message(Protocol):
    """
    A message in the system.

    This is intentionally generic. A message could be:
    - A student's question
    - A system prompt
    - A tool result
    - Any other communication unit

    DO NOT add fields like student_id, subject, ability_level, etc.
    Those constraints belong in concrete implementations if needed.
    """

    def get_content(self) -> str:
        """Return the primary content of the message."""
        ...

    def get_metadata(self) -> Dict[str, Any]:
        """Return optional metadata. Keys are implementation-defined."""
        ...

    def get_id(self) -> str:
        """Unique identifier for this message."""
        ...


@runtime_checkable
class MessageHandler(Protocol):
    """
    Handles messages of a particular type or from a particular source.

    Implementations decide:
    - What message types they accept
    - How to process them
    - What to return

    The protocol is minimal to allow diverse implementations.
    """

    def can_handle(self, message: Message) -> bool:
        """Check if this handler can process the given message."""
        ...

    async def handle(self, message: Message) -> Any:
        """Process the message and return a result."""
        ...


@runtime_checkable
class ContextProvider(Protocol):
    """
    Provides context for processing.

    Context is intentionally abstract. It could include:
    - Conversation history
    - Session information
    - User preferences (if provided by implementation)
    - Any other relevant information

    DO NOT define specific context types or schemas here.
    Let implementations define what context means for their use case.
    """

    def get_context(self, **kwargs: Any) -> Dict[str, Any]:
        """
        Return context information.

        kwargs are implementation-defined. Common examples might include:
        - message_id for conversation context
        - session_id for session context

        Returns a dictionary with implementation-specific keys.
        """
        ...


# Type aliases for common patterns
MessageResult = Any  # Could be a Message, a response, or any result type
HandlerResult = Any  # Could be a Message, a response, or any result type
