"""
Student Port Interface - Stage 03.

Defines the contract for student repository adapters.

This is a PORT in the Hexagonal Architecture pattern.
Adapters must implement this interface.

Dependency Rule: This module may import domain/ only.
It may NOT import adapters/, infrastructure/, or external frameworks.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from waxprep.domain.models.learning_profile import LearningProfile
    from waxprep.domain.models.result import Error, Result
    from waxprep.domain.models.student import Student
    from waxprep.domain.value_objects import StudentId


@runtime_checkable
class StudentPort(Protocol):
    """
    Abstract interface for student repository adapters.

    All student storage adapters (database, in-memory, etc.) must implement
    this protocol to be compatible with the WaxPrep application.

    This is the PORT. Adapters implement this.

    Error Handling:
    - Expected failures (not found, duplicate) return Result.err
    - Programming errors (bugs) raise exceptions
    """

    name: str

    async def get(self, student_id: StudentId) -> Result[Student, Error]:
        """
        Get a student by ID.

        Args:
            student_id: The student ID

        Returns:
            Result containing the student or an error
        """
        ...

    async def get_by_phone(self, phone_number: str) -> Result[Student, Error]:
        """
        Get a student by phone number.

        Args:
            phone_number: The phone number (with country code)

        Returns:
            Result containing the student or an error
        """
        ...

    async def create(self, student: Student) -> Result[Student, Error]:
        """
        Create a new student.

        Args:
            student: The student to create

        Returns:
            Result containing the created student or an error
        """
        ...

    async def update(self, student: Student) -> Result[Student, Error]:
        """
        Update an existing student.

        Args:
            student: The student to update

        Returns:
            Result containing the updated student or an error
        """
        ...

    async def delete(self, student_id: StudentId) -> Result[bool, Error]:
        """
        Delete a student.

        Args:
            student_id: The student ID to delete

        Returns:
            Result indicating success or failure
        """
        ...

    async def list_all(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> Result[list[Student], Error]:
        """
        List all students with pagination.

        Args:
            limit: Maximum number of students to return
            offset: Offset for pagination

        Returns:
            Result containing the list of students or an error
        """
        ...

    async def get_learning_profile(
        self,
        student_id: StudentId,
    ) -> Result[LearningProfile, Error]:
        """
        Get a student's learning profile.

        Args:
            student_id: The student ID

        Returns:
            Result containing the learning profile or an error
        """
        ...

    async def update_learning_profile(
        self,
        learning_profile: LearningProfile,
    ) -> Result[LearningProfile, Error]:
        """
        Update a student's learning profile.

        Args:
            learning_profile: The learning profile to update

        Returns:
            Result containing the updated learning profile or an error
        """
        ...

    def get_capabilities(self) -> dict[str, Any]:
        """
        Declare the capabilities of this student repository adapter.

        Returns:
            A dictionary describing the adapter's capabilities including:
            - storage_type: Type of storage (database, in-memory, etc.)
            - supports_transactions: Whether transactions are supported
            - max_batch_size: Maximum batch size for operations
        """
        ...
