"""
Student Domain Model - Stage 03
Represents a student user in the WaxPrep system.
Pure domain model - NO external imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from waxprep.domain.exceptions import ValidationError
from waxprep.domain.value_objects import StudentId, Timestamp


class StudentStatus(Enum):
    """Status of a student."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


@dataclass(kw_only=True, slots=True)
class Student:
    """Student domain model.

    Represents a student user with their profile information.
    This is the core identity of a learner in the WaxPrep system.
    """

    id: StudentId
    phone_number: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    status: StudentStatus = StudentStatus.ACTIVE
    created_at: Timestamp = field(default_factory=Timestamp.now)
    updated_at: Timestamp = field(default_factory=Timestamp.now)

    def __post_init__(self) -> None:
        """Validate student data on initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate student data."""
        if not self.phone_number:
            raise ValidationError("Student phone number is required")

        if not self.phone_number.startswith("+"):
            raise ValidationError("Phone number must include country code (e.g., +234)")

    @classmethod
    def create(
        cls,
        phone_number: str,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        student_id: StudentId | None = None,
    ) -> Self:
        """Factory method to create a new student."""
        from waxprep.domain.value_objects import create_student_id

        now = Timestamp.now()
        return cls(
            id=student_id or create_student_id(),
            phone_number=phone_number,
            first_name=first_name,
            last_name=last_name,
            email=email,
            status=StudentStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        status: StudentStatus | None = None,
    ) -> None:
        """Update student information."""
        if first_name is not None:
            self.first_name = first_name
        if last_name is not None:
            self.last_name = last_name
        if email is not None:
            self.email = email
        if status is not None:
            self.status = status
        self.updated_at = Timestamp.now()

    def deactivate(self) -> None:
        """Deactivate the student."""
        self.status = StudentStatus.INACTIVE
        self.updated_at = Timestamp.now()

    def suspend(self) -> None:
        """Suspend the student."""
        self.status = StudentStatus.SUSPENDED
        self.updated_at = Timestamp.now()

    def reactivate(self) -> None:
        """Reactivate the student."""
        self.status = StudentStatus.ACTIVE
        self.updated_at = Timestamp.now()

    @property
    def full_name(self) -> str:
        """Get the student's full name."""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else "Unknown"

    @property
    def display_name(self) -> str:
        """Get a display name for the student."""
        return self.full_name if self.full_name != "Unknown" else self.phone_number

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Student):
            return False
        return self.id == other.id
