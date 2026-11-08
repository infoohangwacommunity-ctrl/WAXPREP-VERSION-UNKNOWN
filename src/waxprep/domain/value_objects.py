"""
Value Objects - Stage 03
Immutable, self-validating value objects for domain entities.
NO external imports - pure Python only.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NewType, Self
from uuid import uuid4

# Type aliases for clarity
StudentId = NewType("StudentId", str)
SessionId = NewType("SessionId", str)
MessageId = NewType("MessageId", str)
SubjectCode = NewType("SubjectCode", str)
ConceptId = NewType("ConceptId", str)


@dataclass(frozen=True, slots=True)
class Timestamp:
    """Immutable timestamp value object."""

    value: datetime

    @classmethod
    def now(cls) -> Self:
        """Create a timestamp with current UTC time."""
        return cls(value=datetime.now(UTC))

    @classmethod
    def from_iso(cls, iso_string: str) -> Self:
        """Create a timestamp from ISO format string."""
        dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return cls(value=dt)

    def to_iso(self) -> str:
        """Convert to ISO format string."""
        return self.value.isoformat()

    def __str__(self) -> str:
        return self.to_iso()


def generate_id() -> str:
    """Generate a unique identifier."""
    return str(uuid4())


def create_student_id() -> StudentId:
    """Create a new student ID."""
    return StudentId(generate_id())


def create_session_id() -> SessionId:
    """Create a new session ID."""
    return SessionId(generate_id())


def create_message_id() -> MessageId:
    """Create a new message ID."""
    return MessageId(generate_id())


def create_subject_code(code: str) -> SubjectCode:
    """Create a subject code."""
    return SubjectCode(code.upper())


def create_concept_id() -> ConceptId:
    """Create a new concept ID."""
    return ConceptId(generate_id())
