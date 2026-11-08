"""
Domain Layer - Stage 03
Pure business logic. NO external imports (only stdlib and domain).
NO framework imports. NO provider SDKs. NO FastAPI. NO LiteLLM.
"""

from waxprep.domain.exceptions import (
    DomainError,
    InvariantError,
    NotFoundError,
    ValidationError,
)
from waxprep.domain.models.concept import Concept, ConceptDifficulty
from waxprep.domain.models.learning_profile import (
    KnowledgeLevel,
    LearningProfile,
    LearningStyle,
)
from waxprep.domain.models.message import (
    Message,
    MessageDirection,
    MessageStatus,
    MessageType,
)
from waxprep.domain.models.result import Error, Result
from waxprep.domain.models.session import Session, SessionStatus
from waxprep.domain.models.student import Student, StudentStatus
from waxprep.domain.models.subject import Subject, SubjectCategory
from waxprep.domain.value_objects import (
    ConceptId,
    MessageId,
    SessionId,
    StudentId,
    SubjectCode,
    Timestamp,
)

__all__ = [
    # Exceptions
    "DomainError",
    "InvariantError",
    "NotFoundError",
    "ValidationError",
    # Models
    "Concept",
    "ConceptDifficulty",
    "Error",
    "KnowledgeLevel",
    "LearningProfile",
    "LearningStyle",
    "Message",
    "MessageDirection",
    "MessageId",
    "MessageStatus",
    "MessageType",
    "Result",
    "Session",
    "SessionId",
    "SessionStatus",
    "Student",
    "StudentId",
    "StudentStatus",
    "Subject",
    "SubjectCategory",
    "SubjectCode",
    # Value Objects
    "ConceptId",
    "Timestamp",
]
