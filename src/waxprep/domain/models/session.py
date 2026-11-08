"""
Session Domain Model - Stage 03
Represents a learning session between a student and WaxPrep.
Pure domain model - NO external imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from waxprep.domain.exceptions import StateError, ValidationError
from waxprep.domain.value_objects import SessionId, StudentId, Timestamp


class SessionStatus(Enum):
    """Status of a learning session."""

    CREATED = "created"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass(kw_only=True, slots=True)
class Session:
    """Learning session domain model.

    Represents an ongoing or completed learning interaction.
    Tracks the context, state, and history of a student's session.
    """

    id: SessionId
    student_id: StudentId
    status: SessionStatus = SessionStatus.CREATED
    current_subject: str | None = None
    current_topic: str | None = None
    message_count: int = 0
    created_at: Timestamp = field(default_factory=Timestamp.now)
    updated_at: Timestamp = field(default_factory=Timestamp.now)
    completed_at: Timestamp | None = None

    def __post_init__(self) -> None:
        """Validate session data on initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate session data."""
        if not self.student_id:
            raise ValidationError("Session student_id is required")

    @classmethod
    def create(
        cls,
        student_id: StudentId,
        session_id: SessionId | None = None,
    ) -> Self:
        """Factory method to create a new session."""
        from waxprep.domain.value_objects import create_session_id

        now = Timestamp.now()
        return cls(
            id=session_id or create_session_id(),
            student_id=student_id,
            status=SessionStatus.CREATED,
            created_at=now,
            updated_at=now,
        )

    def start(self, subject: str | None = None, topic: str | None = None) -> None:
        """Start the session."""
        if self.status != SessionStatus.CREATED:
            raise StateError(
                f"Cannot start session in {self.status.value} state",
                {"current_status": self.status.value},
            )

        self.status = SessionStatus.ACTIVE
        self.current_subject = subject
        self.current_topic = topic
        self.updated_at = Timestamp.now()

    def add_message(self) -> None:
        """Increment the message count."""
        if self.status not in (SessionStatus.CREATED, SessionStatus.ACTIVE):
            raise StateError(
                f"Cannot add message to session in {self.status.value} state",
                {"current_status": self.status.value},
            )
        self.message_count += 1
        self.updated_at = Timestamp.now()

    def complete(self) -> None:
        """Mark the session as completed."""
        if self.status != SessionStatus.ACTIVE:
            raise StateError(
                f"Cannot complete session in {self.status.value} state",
                {"current_status": self.status.value},
            )

        self.status = SessionStatus.COMPLETED
        self.completed_at = Timestamp.now()
        self.updated_at = self.completed_at

    def abandon(self) -> None:
        """Mark the session as abandoned."""
        if self.status == SessionStatus.COMPLETED:
            raise StateError(
                "Cannot abandon a completed session",
                {"current_status": self.status.value},
            )

        self.status = SessionStatus.ABANDONED
        self.completed_at = Timestamp.now()
        self.updated_at = self.completed_at

    @property
    def is_active(self) -> bool:
        """Check if the session is currently active."""
        return self.status == SessionStatus.ACTIVE

    @property
    def is_completed(self) -> bool:
        """Check if the session has been completed."""
        return self.status == SessionStatus.COMPLETED

    @property
    def duration(self) -> float:
        """Get the session duration in seconds."""
        end = self.completed_at or Timestamp.now()
        delta = end.value - self.created_at.value
        return delta.total_seconds()

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Session):
            return False
        return self.id == other.id
