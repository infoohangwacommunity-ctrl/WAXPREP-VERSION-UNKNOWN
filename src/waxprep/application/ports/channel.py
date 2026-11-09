"""
Channel Port Interface - Stage 03.

Defines the contract for message channel adapters.

This is a PORT in the Hexagonal Architecture pattern.
Adapters must implement this interface.

Dependency Rule: This module may import domain/ only.
It may NOT import adapters/, infrastructure/, or external frameworks.
"""

from typing import Any, Protocol, runtime_checkable

from waxprep.domain.models.result import Error, Result


@runtime_checkable
class ChannelPort(Protocol):
    """
    Abstract interface for message channel adapters.

    All channel adapters (WhatsApp, Telegram, etc.) must implement
    this protocol to be compatible with the WaxPrep application.

    This is the PORT. Adapters implement this.

    Error Handling:
    - Expected failures (network issues, rate limits) return Result.err
    - Programming errors (bugs) raise exceptions
    """

    name: str

    async def send_message(
        self,
        recipient_id: str,
        content: str,
    ) -> Result[str, Error]:
        """
        Send a message to a recipient.

        Args:
            recipient_id: The recipient identifier
            content: The message content to send

        Returns:
            Result containing the sent message ID or an error
        """
        ...

    async def send_typing_indicator(
        self,
        recipient_id: str,
        is_typing: bool,
    ) -> Result[bool, Error]:
        """
        Send a typing indicator to show the AI is thinking.

        Args:
            recipient_id: The recipient identifier
            is_typing: True to show typing, False to hide

        Returns:
            Result indicating success or failure
        """
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """
        Declare the capabilities of this channel adapter.

        Returns:
            A dictionary describing the adapter's capabilities including:
            - max_message_length: Maximum message length in characters
            - supports_streaming: Whether streaming responses are supported
            - supports_attachments: Whether file attachments are supported
        """
        ...
