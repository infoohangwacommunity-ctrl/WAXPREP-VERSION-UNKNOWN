"""
Message Domain Model - Stage 03
Represents a message in the WaxPrep system.
Pure domain model - NO external imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from waxprep.domain.exceptions import StateError, ValidationError
from waxprep.domain.value_objects import MessageId, SessionId, StudentId, Timestamp


class MessageDirection(Enum):
    """Direction of a message."""

    INCOMING = "incoming"  # From student to WaxPrep
    OUTGOING = "outgoing"  # From WaxPrep to student


class MessageType(Enum):
    """Type of a message."""

    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    COMMAND = "command"


class MessageStatus(Enum):
    """Status of a message."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    DELIVERED = "delivered"


@dataclass(kw_only=True, slots=True)
class Message:
    """Message domain model.

    Represents a message exchanged between a student and WaxPrep.
    Contains the content, metadata, and processing state of the message.
    """

    id: MessageId
    session_id: SessionId | None = None
    student_id: StudentId | None = None
    direction: MessageDirection
    message_type: MessageType = MessageType.TEXT
    content: str
    metadata: dict = field(default_factory=dict)
    status: MessageStatus = MessageStatus.PENDING
    error_message: str | None = None
    created_at: Timestamp = field(default_factory=Timestamp.now)
    processed_at: Timestamp | None = None
    delivered_at: Timestamp | None = None

    def __post_init__(self) -> None:
        """Validate message data on initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate message data."""
        if not self.id:
            raise ValidationError("Message id is required")
        if not self.content and self.message_type != MessageType.COMMAND:
            raise ValidationError("Message content is required for non-command messages")
        if self.direction not in (MessageDirection.INCOMING, MessageDirection.OUTGOING):
            raise ValidationError(f"Invalid message direction: {self.direction}")

    @classmethod
    def create(
        cls,
        content: str,
        direction: MessageDirection,
        message_id: MessageId | None = None,
        session_id: SessionId | None = None,
        student_id: StudentId | None = None,
        message_type: MessageType | None = None,
        metadata: dict | None = None,
    ) -> Self:
        """Factory method to create a new message."""
        from waxprep.domain.value_objects import create_message_id

        now = Timestamp.now()
        return cls(
            id=message_id or create_message_id(),
            session_id=session_id,
            student_id=student_id,
            direction=direction,
            message_type=message_type or MessageType.TEXT,
            content=content,
            metadata=metadata or {},
            status=MessageStatus.PENDING,
            created_at=now,
        )

    def mark_processing(self) -> None:
        """Mark the message as being processed."""
        if self.status not in (MessageStatus.PENDING, MessageStatus.FAILED):
            raise StateError(
                f"Cannot mark message as processing from {self.status.value} state",
                {"current_status": self.status.value},
            )
        self.status = MessageStatus.PROCESSING
        self.error_message = None

    def mark_processed(self) -> None:
        """Mark the message as successfully processed."""
        if self.status != MessageStatus.PROCESSING:
            raise StateError(
                f"Cannot mark message as processed from {self.status.value} state",
                {"current_status": self.status.value},
            )
        self.status = MessageStatus.PROCESSED
        self.processed_at = Timestamp.now()

    def mark_failed(self, error_message: str) -> None:
        """Mark the message as failed."""
        self.status = MessageStatus.FAILED
        self.error_message = error_message
        self.processed_at = Timestamp.now()

    def mark_delivered(self) -> None:
        """Mark the message as delivered."""
        if self.direction != MessageDirection.OUTGOING:
            raise StateError(
                "Only outgoing messages can be marked as delivered",
                {"direction": self.direction.value},
            )
        if self.status != MessageStatus.PROCESSED:
            raise StateError(
                f"Cannot mark message as delivered from {self.status.value} state",
                {"current_status": self.status.value},
            )
        self.status = MessageStatus.DELIVERED
        self.delivered_at = Timestamp.now()

    @property
    def is_incoming(self) -> bool:
        """Check if the message is incoming."""
        return self.direction == MessageDirection.INCOMING

    @property
    def is_outgoing(self) -> bool:
        """Check if the message is outgoing."""
        return self.direction == MessageDirection.OUTGOING

    @property
    def is_processed(self) -> bool:
        """Check if the message has been processed."""
        return self.status in (MessageStatus.PROCESSED, MessageStatus.DELIVERED)

    @property
    def is_failed(self) -> bool:
        """Check if the message processing failed."""
        return self.status == MessageStatus.FAILED

    @property
    def processing_time(self) -> float | None:
        """Get the processing time in seconds."""
        if self.processed_at is None:
            return None
        delta = self.processed_at.value - self.created_at.value
        return delta.total_seconds()

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Message):
            return False
        return self.id == other.id
