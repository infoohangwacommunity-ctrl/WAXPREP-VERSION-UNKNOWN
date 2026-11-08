"""
Session Port Interface - Stage 03.

Defines the contract for session repository adapters.

This is a PORT in the Hexagonal Architecture pattern.
Adapters must implement this interface.

Dependency Rule: This module may import domain/ only.
It may NOT import adapters/, infrastructure/, or external frameworks.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from waxprep.domain.models.message import Message
    from waxprep.domain.models.result import Error, Result
    from waxprep.domain.models.session import Session
    from waxprep.domain.value_objects import MessageId, SessionId, StudentId


@runtime_checkable
class SessionPort(Protocol):
    """
    Abstract interface for session repository adapters.

    All session storage adapters (database, in-memory, etc.) must implement
    this protocol to be compatible with the WaxPrep application.

    This is the PORT. Adapters implement this.

    Error Handling:
    - Expected failures (not found, duplicate) return Result.err
    - Programming errors (bugs) raise exceptions
    """

    name: str

    async def get(self, session_id: SessionId) -> Result[Session, Error]:
        """
        Get a session by ID.

        Args:
            session_id: The session ID

        Returns:
            Result containing the session or an error
        """
        ...

    async def get_by_student(
        self,
        student_id: StudentId,
        limit: int | None = None,
    ) -> Result[list[Session], Error]:
        """
        Get all sessions for a student.

        Args:
            student_id: The student ID
            limit: Maximum number of sessions to return

        Returns:
            Result containing the list of sessions or an error
        """
        ...

    async def get_active_by_student(
        self,
        student_id: StudentId,
    ) -> Result[Session | None, Error]:
        """
        Get the currently active session for a student.

        Args:
            student_id: The student ID

        Returns:
            Result containing the active session or None if no active session
        """
        ...

    async def create(self, session: Session) -> Result[Session, Error]:
        """
        Create a new session.

        Args:
            session: The session to create

        Returns:
            Result containing the created session or an error
        """
        ...

    async def update(self, session: Session) -> Result[Session, Error]:
        """
        Update an existing session.

        Args:
            session: The session to update

        Returns:
            Result containing the updated session or an error
        """
        ...

    async def add_message(
        self,
        session_id: SessionId,
        message: Message,
    ) -> Result[Message, Error]:
        """
        Add a message to a session.

        Args:
            session_id: The session ID
            message: The message to add

        Returns:
            Result containing the added message or an error
        """
        ...

    async def get_messages(
        self,
        session_id: SessionId,
        limit: int | None = None,
        offset: int = 0,
    ) -> Result[list[Message], Error]:
        """
        Get all messages in a session.

        Args:
            session_id: The session ID
            limit: Maximum number of messages to return
            offset: Offset for pagination

        Returns:
            Result containing the list of messages or an error
        """
        ...

    async def get_message(
        self,
        message_id: MessageId,
    ) -> Result[Message, Error]:
        """
        Get a specific message by ID.

        Args:
            message_id: The message ID

        Returns:
            Result containing the message or an error
        """
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """
        Declare the capabilities of this session repository adapter.

        Returns:
            A dictionary describing the adapter's capabilities including:
            - storage_type: Type of storage (database, in-memory, etc.)
            - max_messages_per_session: Maximum messages per session
            - message_retention_days: How long messages are retained
        """
        ...
