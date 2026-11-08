"""
Unit Tests for Domain Models - Stage 05

Tests for domain models to ensure they work correctly in isolation.
"""

import pytest

from waxprep.domain.exceptions import StateError, ValidationError
from waxprep.domain.models.concept import Concept, ConceptDifficulty
from waxprep.domain.models.learning_profile import (
    LearningProfile,
    LearningStyle,
)
from waxprep.domain.models.message import Message, MessageDirection, MessageStatus
from waxprep.domain.models.result import Error, Result
from waxprep.domain.models.session import Session, SessionStatus
from waxprep.domain.models.student import Student, StudentStatus
from waxprep.domain.models.subject import Subject, SubjectCategory
from waxprep.domain.value_objects import (
    SubjectCode,
    create_concept_id,
    create_student_id,
    create_subject_code,
)


class TestStudent:
    """Unit tests for Student domain model."""

    def test_create_student(self) -> None:
        """Test creating a student."""
        student = Student.create(
            phone_number="+2348012345678",
            first_name="John",
            last_name="Doe",
        )
        assert student.phone_number == "+2348012345678"
        assert student.first_name == "John"
        assert student.last_name == "Doe"
        assert student.status == StudentStatus.ACTIVE
        assert student.full_name == "John Doe"
        assert student.display_name == "John Doe"

    def test_create_student_without_name(self) -> None:
        """Test creating a student without name."""
        student = Student.create(phone_number="+2348012345678")
        assert student.full_name == "Unknown"
        assert student.display_name == "+2348012345678"

    def test_student_validation_missing_phone(self) -> None:
        """Test that student validation fails without phone number."""
        with pytest.raises(ValidationError) as exc_info:
            Student.create(phone_number="")
        assert "phone number is required" in str(exc_info.value)

    def test_student_validation_phone_format(self) -> None:
        """Test that student validation fails with invalid phone format."""
        with pytest.raises(ValidationError) as exc_info:
            Student.create(phone_number="08012345678")  # Missing country code
        assert "country code" in str(exc_info.value)

    def test_student_deactivate(self) -> None:
        """Test deactivating a student."""
        student = Student.create(phone_number="+2348012345678")
        student.deactivate()
        assert student.status == StudentStatus.INACTIVE

    def test_student_suspend(self) -> None:
        """Test suspending a student."""
        student = Student.create(phone_number="+2348012345678")
        student.suspend()
        assert student.status == StudentStatus.SUSPENDED

    def test_student_reactivate(self) -> None:
        """Test reactivating a student."""
        student = Student.create(phone_number="+2348012345678")
        student.deactivate()
        student.reactivate()
        assert student.status == StudentStatus.ACTIVE

    def test_student_equality(self) -> None:
        """Test student equality."""
        student1 = Student.create(phone_number="+2348012345678", first_name="John")
        student2 = Student.create(phone_number="+2348012345678", first_name="Jane")
        # Same ID (if generated the same way) or different objects
        assert student1 != student2 or student1.id == student2.id


class TestSession:
    """Unit tests for Session domain model."""

    def test_create_session(self) -> None:
        """Test creating a session."""
        student_id = create_student_id()
        session = Session.create(student_id=student_id)
        assert session.student_id == student_id
        assert session.status == SessionStatus.CREATED
        assert session.message_count == 0
        assert session.is_active is False
        assert session.is_completed is False

    def test_session_start(self) -> None:
        """Test starting a session."""
        student_id = create_student_id()
        session = Session.create(student_id=student_id)
        session.start(subject="Mathematics", topic="Algebra")
        assert session.status == SessionStatus.ACTIVE
        assert session.current_subject == "Mathematics"
        assert session.current_topic == "Algebra"
        assert session.is_active is True

    def test_session_start_already_started(self) -> None:
        """Test that starting an already started session fails."""
        student_id = create_student_id()
        session = Session.create(student_id=student_id)
        session.start()
        with pytest.raises(StateError):
            session.start()

    def test_session_add_message(self) -> None:
        """Test adding a message to a session."""
        student_id = create_student_id()
        session = Session.create(student_id=student_id)
        session.start()
        session.add_message()
        assert session.message_count == 1

    def test_session_complete(self) -> None:
        """Test completing a session."""
        student_id = create_student_id()
        session = Session.create(student_id=student_id)
        session.start()
        session.complete()
        assert session.status == SessionStatus.COMPLETED
        assert session.is_completed is True
        assert session.completed_at is not None

    def test_session_complete_not_started(self) -> None:
        """Test that completing a non-started session fails."""
        student_id = create_student_id()
        session = Session.create(student_id=student_id)
        with pytest.raises(StateError):
            session.complete()

    def test_session_abandon(self) -> None:
        """Test abandoning a session."""
        student_id = create_student_id()
        session = Session.create(student_id=student_id)
        session.start()
        session.abandon()
        assert session.status == SessionStatus.ABANDONED

    def test_session_duration(self) -> None:
        """Test session duration calculation."""
        student_id = create_student_id()
        session = Session.create(student_id=student_id)
        # Duration should be positive after some time
        assert session.duration >= 0


class TestMessage:
    """Unit tests for Message domain model."""

    def test_create_message(self) -> None:
        """Test creating a message."""
        message = Message.create(
            content="Hello",
            direction=MessageDirection.INCOMING,
        )
        assert message.content == "Hello"
        assert message.direction == MessageDirection.INCOMING
        assert message.status == MessageStatus.PENDING
        assert message.is_incoming is True
        assert message.is_outgoing is False

    def test_create_outgoing_message(self) -> None:
        """Test creating an outgoing message."""
        message = Message.create(
            content="Hello",
            direction=MessageDirection.OUTGOING,
        )
        assert message.is_incoming is False
        assert message.is_outgoing is True

    def test_message_mark_processing(self) -> None:
        """Test marking a message as processing."""
        message = Message.create(
            content="Hello",
            direction=MessageDirection.INCOMING,
        )
        message.mark_processing()
        assert message.status == MessageStatus.PROCESSING

    def test_message_mark_processed(self) -> None:
        """Test marking a message as processed."""
        message = Message.create(
            content="Hello",
            direction=MessageDirection.INCOMING,
        )
        message.mark_processing()
        message.mark_processed()
        assert message.status == MessageStatus.PROCESSED
        assert message.processed_at is not None

    def test_message_mark_failed(self) -> None:
        """Test marking a message as failed."""
        message = Message.create(
            content="Hello",
            direction=MessageDirection.INCOMING,
        )
        message.mark_failed("Network error")
        assert message.status == MessageStatus.FAILED
        assert message.error_message == "Network error"

    def test_message_mark_delivered(self) -> None:
        """Test marking a message as delivered."""
        message = Message.create(
            content="Hello",
            direction=MessageDirection.OUTGOING,
        )
        message.mark_processing()
        message.mark_processed()
        message.mark_delivered()
        assert message.status == MessageStatus.DELIVERED
        assert message.delivered_at is not None

    def test_message_mark_delivered_incoming(self) -> None:
        """Test that marking an incoming message as delivered fails."""
        message = Message.create(
            content="Hello",
            direction=MessageDirection.INCOMING,
        )
        with pytest.raises(StateError):
            message.mark_delivered()


class TestSubject:
    """Unit tests for Subject domain model."""

    def test_create_subject(self) -> None:
        """Test creating a subject."""
        subject = Subject.create(
            code="MATH",
            name="Mathematics",
            category=SubjectCategory.SCIENCE,
        )
        assert subject.code == SubjectCode("MATH")
        assert subject.name == "Mathematics"
        assert subject.category == SubjectCategory.SCIENCE
        assert subject.is_active is True
        assert subject.display_name == "MATH - Mathematics"

    def test_subject_deactivate(self) -> None:
        """Test deactivating a subject."""
        subject = Subject.create(code="MATH", name="Mathematics")
        subject.deactivate()
        assert subject.is_active is False

    def test_subject_activate(self) -> None:
        """Test activating a subject."""
        subject = Subject.create(code="MATH", name="Mathematics")
        subject.deactivate()
        subject.activate()
        assert subject.is_active is True


class TestConcept:
    """Unit tests for Concept domain model."""

    def test_create_concept(self) -> None:
        """Test creating a concept."""
        subject_code = create_subject_code("MATH")
        concept = Concept.create(
            subject_code=subject_code,
            name="Quadratic Equations",
            difficulty=ConceptDifficulty.INTERMEDIATE,
        )
        assert concept.subject_code == subject_code
        assert concept.name == "Quadratic Equations"
        assert concept.difficulty == ConceptDifficulty.INTERMEDIATE
        assert concept.is_active is True
        assert concept.has_prerequisites is False

    def test_concept_add_prerequisite(self) -> None:
        """Test adding a prerequisite to a concept."""
        subject_code = create_subject_code("MATH")
        concept = Concept.create(
            subject_code=subject_code,
            name="Calculus",
        )
        prereq_id = create_concept_id()
        concept.add_prerequisite(prereq_id)
        assert concept.has_prerequisites is True
        assert prereq_id in concept.prerequisites


class TestLearningProfile:
    """Unit tests for LearningProfile domain model."""

    def test_create_learning_profile(self) -> None:
        """Test creating a learning profile."""
        student_id = create_student_id()
        profile = LearningProfile.create(student_id=student_id)
        assert profile.student_id == student_id
        assert profile.preferred_learning_style == LearningStyle.MIXED
        assert profile.preferred_difficulty == "intermediate"

    def test_learning_profile_update_preferences(self) -> None:
        """Test updating learning preferences."""
        student_id = create_student_id()
        profile = LearningProfile.create(student_id=student_id)
        profile.update_preferences(
            learning_style=LearningStyle.VISUAL,
            difficulty="advanced",
        )
        assert profile.preferred_learning_style == LearningStyle.VISUAL
        assert profile.preferred_difficulty == "advanced"

    def test_learning_profile_add_strength(self) -> None:
        """Test adding a strength to learning profile."""
        student_id = create_student_id()
        profile = LearningProfile.create(student_id=student_id)
        subject_code = create_subject_code("MATH")
        profile.add_strength(subject_code)
        assert subject_code in profile.strengths

    def test_learning_profile_add_weakness(self) -> None:
        """Test adding a weakness to learning profile."""
        student_id = create_student_id()
        profile = LearningProfile.create(student_id=student_id)
        subject_code = create_subject_code("PHYSICS")
        profile.add_weakness(subject_code)
        assert subject_code in profile.weaknesses


class TestResult:
    """Unit tests for Result type."""

    def test_result_ok(self) -> None:
        """Test creating a successful result."""
        result = Result.ok("success")
        assert result.is_ok is True
        assert result.is_err is False
        assert result.value == "success"
        assert result.error is None

    def test_result_err(self) -> None:
        """Test creating an error result."""
        error = Error.not_found("Student", "123")
        result = Result.err(error)
        assert result.is_ok is False
        assert result.is_err is True
        assert result.value is None
        assert result.error == error

    def test_result_unwrap(self) -> None:
        """Test unwrapping a successful result."""
        result = Result.ok("success")
        assert result.unwrap() == "success"

    def test_result_unwrap_err(self) -> None:
        """Test unwrapping an error result raises exception."""
        error = Error.not_found("Student", "123")
        result = Result.err(error)
        with pytest.raises(ValueError):
            result.unwrap()

    def test_result_unwrap_or(self) -> None:
        """Test unwrap_or with default value."""
        error = Error.not_found("Student", "123")
        result = Result.err(error)
        assert result.unwrap_or("default") == "default"

    def test_result_map(self) -> None:
        """Test mapping over a successful result."""
        result = Result.ok("hello")
        mapped = result.map(lambda x: x.upper())
        assert mapped.is_ok is True
        assert mapped.value == "HELLO"

    def test_result_map_err(self) -> None:
        """Test mapping over an error result."""
        error = Error.not_found("Student", "123")
        result = Result.err(error)
        mapped = result.map(lambda x: x.upper())
        assert mapped.is_err is True
        assert mapped.error == error

    def test_result_bool(self) -> None:
        """Test boolean conversion of result."""
        ok_result = Result.ok("success")
        err_result = Result.err(Error.not_found("Student", "123"))
        assert bool(ok_result) is True
        assert bool(err_result) is False


class TestError:
    """Unit tests for Error value object."""

    def test_error_not_found(self) -> None:
        """Test creating a not found error."""
        error = Error.not_found("Student", "123")
        assert error.code == "NOT_FOUND"
        assert "Student" in error.message
        assert "123" in error.message
        assert error.details is not None
        assert error.details["resource_type"] == "Student"
        assert error.details["resource_id"] == "123"

    def test_error_validation(self) -> None:
        """Test creating a validation error."""
        error = Error.validation("Invalid input", {"field": "name"})
        assert error.code == "VALIDATION_ERROR"
        assert error.message == "Invalid input"
        assert error.details == {"field": "name"}

    def test_error_timeout(self) -> None:
        """Test creating a timeout error."""
        error = Error.timeout("model_provider", 30.0)
        assert error.code == "TIMEOUT"
        assert "model_provider" in error.message
        assert "30" in error.message

    def test_error_rate_limit(self) -> None:
        """Test creating a rate limit error."""
        error = Error.rate_limit("model_provider", retry_after=60.0)
        assert error.code == "RATE_LIMIT"
        assert error.details is not None
        assert error.details["retry_after"] == 60.0

    def test_error_provider(self) -> None:
        """Test creating a provider error."""
        error = Error.provider_error("openai", "API key invalid")
        assert error.code == "PROVIDER_ERROR"
        assert "openai" in error.message
        assert "API key invalid" in error.message
