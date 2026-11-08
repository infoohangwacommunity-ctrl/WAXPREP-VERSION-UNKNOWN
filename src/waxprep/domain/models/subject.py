"""
Subject Domain Model - Stage 03
Represents an academic subject.
Pure domain model - NO external imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from waxprep.domain.exceptions import ValidationError
from waxprep.domain.value_objects import SubjectCode, Timestamp


class SubjectCategory(Enum):
    """Category of academic subjects."""

    SCIENCE = "science"
    MATH = "mathematics"
    ENGLISH = "english"
    SOCIAL_STUDIES = "social_studies"
    TECHNICAL = "technical"
    ARTS = "arts"
    LANGUAGES = "languages"
    BUSINESS = "business"
    OTHER = "other"


@dataclass(kw_only=True, slots=True)
class Subject:
    """Subject domain model.

    Represents an academic subject that students can learn about.
    Contains metadata about the subject for categorization and filtering.
    """

    code: SubjectCode
    name: str
    category: SubjectCategory = SubjectCategory.OTHER
    description: str | None = None
    is_active: bool = True
    created_at: Timestamp = field(default_factory=Timestamp.now)
    updated_at: Timestamp = field(default_factory=Timestamp.now)

    def __post_init__(self) -> None:
        """Validate subject data on initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate subject data."""
        if not self.code:
            raise ValidationError("Subject code is required")
        if not self.name:
            raise ValidationError("Subject name is required")

    @classmethod
    def create(
        cls,
        code: str,
        name: str,
        category: SubjectCategory | None = None,
        description: str | None = None,
    ) -> Self:
        """Factory method to create a new subject."""
        from waxprep.domain.value_objects import create_subject_code

        now = Timestamp.now()
        return cls(
            code=create_subject_code(code),
            name=name,
            category=category or SubjectCategory.OTHER,
            description=description,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        name: str | None = None,
        category: SubjectCategory | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> None:
        """Update subject information."""
        if name is not None:
            self.name = name
        if category is not None:
            self.category = category
        if description is not None:
            self.description = description
        if is_active is not None:
            self.is_active = is_active
        self.updated_at = Timestamp.now()

    def deactivate(self) -> None:
        """Deactivate the subject."""
        self.is_active = False
        self.updated_at = Timestamp.now()

    def activate(self) -> None:
        """Activate the subject."""
        self.is_active = True
        self.updated_at = Timestamp.now()

    @property
    def display_name(self) -> str:
        """Get the display name for the subject."""
        return f"{self.code} - {self.name}"

    def __hash__(self) -> int:
        return hash(self.code)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Subject):
            return False
        return self.code == other.code
