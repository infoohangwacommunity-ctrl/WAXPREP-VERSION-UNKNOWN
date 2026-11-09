"""
Unit Test Fixtures - Stage 05

Fixtures for unit tests.
All fixtures are function-scoped by default.
"""

from datetime import UTC, datetime

import pytest

from waxprep.domain.exceptions import NotFoundError, ValidationError
from waxprep.domain.models.result import Error, Result
from waxprep.domain.value_objects import Timestamp


# Value Object Fixtures


@pytest.fixture
def timestamp() -> Timestamp:
    """Create a timestamp."""
    return Timestamp(datetime.now(UTC))


# Result and Error Fixtures


@pytest.fixture
def result_ok() -> Result[str, Error]:
    """Create a successful result."""
    return Result.ok("Success")


@pytest.fixture
def result_err() -> Result[str, Error]:
    """Create an error result."""
    return Result.err(Error.not_found("Resource", "123"))


@pytest.fixture
def validation_error() -> ValidationError:
    """Create a validation error."""
    return ValidationError("Invalid input", {"field": "name"})


@pytest.fixture
def not_found_error() -> NotFoundError:
    """Create a not found error."""
    return NotFoundError("Resource not found", {"id": "123"})
