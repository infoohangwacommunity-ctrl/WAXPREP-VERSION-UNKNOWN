"""
Unit Test Fixtures - Stage 05

Fixtures for unit tests.
All fixtures are function-scoped by default.
"""

from datetime import UTC, datetime

import pytest

from waxprep.domain.exceptions import NotFoundError, ValidationError
from waxprep.domain.models.concept import Concept, ConceptDifficulty
from waxprep.domain.models.learning_profile import (
    LearningProfile,
)
from waxprep.domain.models.message import Message, MessageDirection
from waxprep.domain.models.result import Error, Result
from waxprep.domain.models.session import Session
from waxprep.domain.models.student import Student
from waxprep.domain.models.subject import Subject, SubjectCategory
from waxprep.domain.value_objects import (
    ConceptId,
    MessageId,
    SessionId,
    StudentId,
    SubjectCode,
    Timestamp,
    create_concept_id,
    create_message_id,
    create_session_id,
    create_student_id,
    create_subject_code,
)

# Value Object Fixtures


@pytest.fixture
def student_id() -> StudentId:
    """Create a student ID."""
    return create_student_id()


@pytest.fixture
def session_id() -> SessionId:
    """Create a session ID."""
    return create_session_id()


@pytest.fixture
def message_id() -> MessageId:
    """Create a message ID."""
    return create_message_id()


@pytest.fixture
def subject_code() -> SubjectCode:
    """Create a subject code."""
    return create_subject_code("MATH")


@pytest.fixture
def concept_id() -> ConceptId:
    """Create a concept ID."""
    return create_concept_id()


@pytest.fixture
def timestamp() -> Timestamp:
    """Create a timestamp."""
    return Timestamp(datetime.now(UTC))


# Domain Model Fixtures


@pytest.fixture
def student(student_id: StudentId) -> Student:
    """Create a student."""
    return Student.create(
        phone_number="+2348012345678",
        first_name="John",
        last_name="Doe",
        student_id=student_id,
    )


@pytest.fixture
def session(student_id: StudentId, session_id: SessionId) -> Session:
    """Create a session."""
    return Session.create(
        student_id=student_id,
        session_id=session_id,
    )


@pytest.fixture
def active_session(student_id: StudentId) -> Session:
    """Create an active session."""
    session = Session.create(student_id=student_id)
    session.start(subject="Mathematics", topic="Algebra")
    return session


@pytest.fixture
def message(message_id: MessageId, student_id: StudentId) -> Message:
    """Create a message."""
    return Message.create(
        content="Hello, can you help me with math?",
        direction=MessageDirection.INCOMING,
        message_id=message_id,
        student_id=student_id,
    )


@pytest.fixture
def outgoing_message(message_id: MessageId, student_id: StudentId) -> Message:
    """Create an outgoing message."""
    return Message.create(
        content="Sure, I can help with that!",
        direction=MessageDirection.OUTGOING,
        message_id=message_id,
        student_id=student_id,
    )


@pytest.fixture
def subject(subject_code: SubjectCode) -> Subject:
    """Create a subject."""
    return Subject.create(
        code="MATH",
        name="Mathematics",
        category=SubjectCategory.SCIENCE,
    )


@pytest.fixture
def concept(subject_code: SubjectCode, concept_id: ConceptId) -> Concept:
    """Create a concept."""
    return Concept.create(
        subject_code=subject_code,
        name="Quadratic Equations",
        concept_id=concept_id,
        description="Equations of the form ax^2 + bx + c = 0",
        difficulty=ConceptDifficulty.INTERMEDIATE,
    )


@pytest.fixture
def learning_profile(student_id: StudentId) -> LearningProfile:
    """Create a learning profile."""
    return LearningProfile.create(student_id=student_id)


# Result and Error Fixtures


@pytest.fixture
def result_ok() -> Result[str, Error]:
    """Create a successful result."""
    return Result.ok("Success")


@pytest.fixture
def result_err() -> Result[str, Error]:
    """Create an error result."""
    return Result.err(Error.not_found("Student", "123"))


@pytest.fixture
def validation_error() -> ValidationError:
    """Create a validation error."""
    return ValidationError("Invalid input", {"field": "name"})


@pytest.fixture
def not_found_error() -> NotFoundError:
    """Create a not found error."""
    return NotFoundError("Student not found", {"student_id": "123"})
