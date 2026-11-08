"""
Channel Port Interface - Stage 03.

Defines the contract for message channel adapters.

This is a PORT in the Hexagonal Architecture pattern.
Adapters must implement this interface.

Dependency Rule: This module may import domain/ only.
It may NOT import adapters/, infrastructure/, or external frameworks.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from waxprep.domain.models.message import Message
    from waxprep.domain.models.result import Error, Result
    from waxprep.domain.value_objects import MessageId, StudentId


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

    async def handle_message(self, message: Message) -> Result[Message, Error]:
        """
        Handle an incoming message from the channel.

        This method is called when a message is received from the channel.
        The adapter should process the raw channel message and convert it
        to a domain Message object.

        Args:
            message: The incoming message from the channel

        Returns:
            Result containing the processed message or an error
        """
        ...

    async def send_message(
        self,
        recipient_id: StudentId,
        message: Message,
    ) -> Result[MessageId, Error]:
        """
        Send a message to a recipient.

        Args:
            recipient_id: The student identifier
            message: The message to send (domain Message object)

        Returns:
            Result containing the sent message ID or an error
        """
        ...

    async def send_typing_indicator(
        self,
        recipient_id: StudentId,
        is_typing: bool,
    ) -> Result[bool, Error]:
        """
        Send a typing indicator to show the AI is thinking.

        Args:
            recipient_id: The student identifier
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
            - supported_message_types: List of MessageType enums
            - max_message_length: Maximum message length in characters
            - supports_streaming: Whether streaming responses are supported
            - supports_attachments: Whether file attachments are supported
        """
        ...
