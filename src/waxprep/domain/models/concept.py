"""
Concept Domain Model - Stage 03
Represents an educational concept within a subject.
Pure domain model - NO external imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from waxprep.domain.exceptions import ValidationError
from waxprep.domain.value_objects import ConceptId, SubjectCode, Timestamp


class ConceptDifficulty(Enum):
    """Difficulty level of a concept."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass(kw_only=True, slots=True)
class Concept:
    """Concept domain model.

    Represents a specific educational concept that students can learn.
    Concepts are the building blocks of knowledge within subjects.
    """

    id: ConceptId
    subject_code: SubjectCode
    name: str
    description: str | None = None
    difficulty: ConceptDifficulty = ConceptDifficulty.BEGINNER
    prerequisites: list[ConceptId] = field(default_factory=list)
    is_active: bool = True
    created_at: Timestamp = field(default_factory=Timestamp.now)
    updated_at: Timestamp = field(default_factory=Timestamp.now)

    def __post_init__(self) -> None:
        """Validate concept data on initialization."""
        self._validate()

    def _validate(self) -> None:
        """Validate concept data."""
        if not self.id:
            raise ValidationError("Concept id is required")
        if not self.subject_code:
            raise ValidationError("Concept subject_code is required")
        if not self.name:
            raise ValidationError("Concept name is required")

    @classmethod
    def create(
        cls,
        subject_code: SubjectCode,
        name: str,
        concept_id: ConceptId | None = None,
        description: str | None = None,
        difficulty: ConceptDifficulty | None = None,
        prerequisites: list[ConceptId] | None = None,
    ) -> Self:
        """Factory method to create a new concept."""
        from waxprep.domain.value_objects import create_concept_id

        now = Timestamp.now()
        return cls(
            id=concept_id or create_concept_id(),
            subject_code=subject_code,
            name=name,
            description=description,
            difficulty=difficulty or ConceptDifficulty.BEGINNER,
            prerequisites=prerequisites or [],
            is_active=True,
            created_at=now,
            updated_at=now,
        )

    def update(
        self,
        name: str | None = None,
        description: str | None = None,
        difficulty: ConceptDifficulty | None = None,
        prerequisites: list[ConceptId] | None = None,
        is_active: bool | None = None,
    ) -> None:
        """Update concept information."""
        if name is not None:
            self.name = name
        if description is not None:
            self.description = description
        if difficulty is not None:
            self.difficulty = difficulty
        if prerequisites is not None:
            self.prerequisites = prerequisites
        if is_active is not None:
            self.is_active = is_active
        self.updated_at = Timestamp.now()

    def add_prerequisite(self, concept_id: ConceptId) -> None:
        """Add a prerequisite concept."""
        if concept_id not in self.prerequisites:
            self.prerequisites.append(concept_id)
            self.updated_at = Timestamp.now()

    def remove_prerequisite(self, concept_id: ConceptId) -> None:
        """Remove a prerequisite concept."""
        if concept_id in self.prerequisites:
            self.prerequisites.remove(concept_id)
            self.updated_at = Timestamp.now()

    @property
    def has_prerequisites(self) -> bool:
        """Check if this concept has prerequisites."""
        return len(self.prerequisites) > 0

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Concept):
            return False
        return self.id == other.id
