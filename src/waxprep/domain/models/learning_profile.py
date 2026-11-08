"""
Learning Profile Domain Model - Stage 03
Represents a student's personalized learning profile.
Pure domain model - NO external imports.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Self

from waxprep.domain.exceptions import ValidationError
from waxprep.domain.value_objects import ConceptId, StudentId, SubjectCode, Timestamp


class LearningStyle(Enum):
    """Preferred learning style of a student."""

    VISUAL = "visual"
    AUDITORY = "auditory"
    READING = "reading"
    KINESTHETIC = "kinesthetic"
    MIXED = "mixed"


class KnowledgeLevel(Enum):
    """Knowledge level for a specific subject or concept."""

    UNAWARE = "unaware"
    BEGINNER = "beginner"
    DEVELOPING = "developing"
    PROFICIENT = "proficient"
    ADVANCED = "advanced"


@dataclass(kw_only=True, slots=True)
class KnowledgeState:
    """Represents a student's knowledge level for a specific concept."""

    concept_id: ConceptId
    level: KnowledgeLevel = KnowledgeLevel.UNAWARE
    confidence: float = 0.0  # 0.0 to 1.0
    last_assessed: Timestamp | None = None
    times_practiced: int = 0
    times_mastered: int = 0

    def __post_init__(self) -> None:
        """Validate knowledge state data."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValidationError("Confidence must be between 0.0 and 1.0")
        if self.times_practiced < 0:
            raise ValidationError("Times practiced cannot be negative")
        if self.times_mastered < 0:
            raise ValidationError("Times mastered cannot be negative")

    def update_level(self, level: KnowledgeLevel, confidence: float | None = None) -> None:
        """Update the knowledge level."""
        self.level = level
        if confidence is not None:
            self.confidence = max(0.0, min(1.0, confidence))
        self.last_assessed = Timestamp.now()

    def record_practice(self, success: bool) -> None:
        """Record a practice session."""
        self.times_practiced += 1
        if success:
            self.times_mastered += 1
            # Increase confidence based on success
            self.confidence = min(1.0, self.confidence + 0.1)
        else:
            # Decrease confidence slightly on failure
            self.confidence = max(0.0, self.confidence - 0.05)

    @property
    def mastery_rate(self) -> float:
        """Calculate the mastery rate."""
        if self.times_practiced == 0:
            return 0.0
        return self.times_mastered / self.times_practiced


@dataclass(kw_only=True, slots=True)
class LearningProfile:
    """Learning profile domain model.

    Represents a student's personalized learning preferences and knowledge state.
    This is the core of WaxPrep's personalization capability.
    """

    student_id: StudentId
    preferred_learning_style: LearningStyle = LearningStyle.MIXED
    preferred_difficulty: str = "intermediate"  # Can be beginner, intermediate, advanced
    preferred_language: str = "english"
    knowledge_states: dict[ConceptId, KnowledgeState] = field(default_factory=dict)
    strengths: list[SubjectCode] = field(default_factory=list)
    weaknesses: list[SubjectCode] = field(default_factory=list)
    created_at: Timestamp = field(default_factory=Timestamp.now)
    updated_at: Timestamp = field(default_factory=Timestamp.now)

    def __post_init__(self) -> None:
        """Validate learning profile data."""
        if not self.student_id:
            raise ValidationError("Learning profile student_id is required")

    @classmethod
    def create(cls, student_id: StudentId) -> Self:
        """Factory method to create a new learning profile."""
        now = Timestamp.now()
        return cls(
            student_id=student_id,
            preferred_learning_style=LearningStyle.MIXED,
            preferred_difficulty="intermediate",
            preferred_language="english",
            created_at=now,
            updated_at=now,
        )

    def update_preferences(
        self,
        learning_style: LearningStyle | None = None,
        difficulty: str | None = None,
        language: str | None = None,
    ) -> None:
        """Update learning preferences."""
        if learning_style is not None:
            self.preferred_learning_style = learning_style
        if difficulty is not None:
            self.preferred_difficulty = difficulty
        if language is not None:
            self.preferred_language = language
        self.updated_at = Timestamp.now()

    def add_knowledge_state(self, knowledge_state: KnowledgeState) -> None:
        """Add or update a knowledge state."""
        self.knowledge_states[knowledge_state.concept_id] = knowledge_state
        self.updated_at = Timestamp.now()

    def get_knowledge_state(self, concept_id: ConceptId) -> KnowledgeState | None:
        """Get the knowledge state for a concept."""
        return self.knowledge_states.get(concept_id)

    def add_strength(self, subject_code: SubjectCode) -> None:
        """Add a subject to strengths."""
        if subject_code not in self.strengths:
            self.strengths.append(subject_code)
            self.updated_at = Timestamp.now()

    def add_weakness(self, subject_code: SubjectCode) -> None:
        """Add a subject to weaknesses."""
        if subject_code not in self.weaknesses:
            self.weaknesses.append(subject_code)
            # Remove from strengths if present
            if subject_code in self.strengths:
                self.strengths.remove(subject_code)
            self.updated_at = Timestamp.now()

    def remove_strength(self, subject_code: SubjectCode) -> None:
        """Remove a subject from strengths."""
        if subject_code in self.strengths:
            self.strengths.remove(subject_code)
            self.updated_at = Timestamp.now()

    def remove_weakness(self, subject_code: SubjectCode) -> None:
        """Remove a subject from weaknesses."""
        if subject_code in self.weaknesses:
            self.weaknesses.remove(subject_code)
            self.updated_at = Timestamp.now()

    @property
    def known_concepts(self) -> list[ConceptId]:
        """Get list of all concepts the student has knowledge about."""
        return list(self.knowledge_states.keys())

    @property
    def mastered_concepts(self) -> list[ConceptId]:
        """Get list of concepts the student has mastered."""
        return [
            cid
            for cid, state in self.knowledge_states.items()
            if state.level in (KnowledgeLevel.PROFICIENT, KnowledgeLevel.ADVANCED)
        ]

    def __hash__(self) -> int:
        return hash(self.student_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LearningProfile):
            return False
        return self.student_id == other.student_id
