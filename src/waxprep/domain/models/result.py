"""
Result Type - Stage 03
Functional result type for expected failures.
Pure domain model - NO external imports.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Self, TypeVar

T = TypeVar("T")
E = TypeVar("E", bound="Error")


@dataclass(frozen=True, slots=True)
class Error:
    """Domain error value object.

    Represents an expected failure that can occur during normal operation.
    Used with Result type for functional error handling.
    """

    code: str
    message: str
    details: dict | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    @classmethod
    def not_found(cls, resource_type: str, resource_id: str) -> Self:
        """Create a not found error."""
        return cls(
            code="NOT_FOUND",
            message=f"{resource_type} not found: {resource_id}",
            details={"resource_type": resource_type, "resource_id": resource_id},
        )

    @classmethod
    def validation(cls, message: str, details: dict | None = None) -> Self:
        """Create a validation error."""
        return cls(
            code="VALIDATION_ERROR",
            message=message,
            details=details,
        )

    @classmethod
    def timeout(cls, operation: str, timeout_seconds: float) -> Self:
        """Create a timeout error."""
        return cls(
            code="TIMEOUT",
            message=f"{operation} timed out after {timeout_seconds}s",
            details={"operation": operation, "timeout_seconds": timeout_seconds},
        )

    @classmethod
    def rate_limit(cls, operation: str, retry_after: float | None = None) -> Self:
        """Create a rate limit error."""
        details = {"operation": operation}
        if retry_after is not None:
            details["retry_after"] = retry_after
        return cls(
            code="RATE_LIMIT",
            message=f"{operation} rate limited",
            details=details,
        )

    @classmethod
    def invalid_config(cls, setting: str, expected: str | None = None) -> Self:
        """Create an invalid configuration error."""
        details = {"setting": setting}
        if expected is not None:
            details["expected"] = expected
        return cls(
            code="INVALID_CONFIG",
            message=f"Invalid configuration: {setting}",
            details=details,
        )

    @classmethod
    def provider_error(cls, provider: str, message: str, details: dict | None = None) -> Self:
        """Create a provider error."""
        return cls(
            code="PROVIDER_ERROR",
            message=f"{provider} error: {message}",
            details={"provider": provider, **(details or {})},
        )


@dataclass(frozen=True, slots=True)
class Result(Generic[T, E]):
    """Functional result type for expected failures.

    Used to distinguish between expected failures (returned as Result.err)
    and unexpected failures (raised as exceptions).

    This pattern is used at boundaries where failures are expected:
    - External service calls (model providers, channels)
    - Validation
    - Parsing
    - Input/output operations

    For programming errors (bugs), use exceptions instead.
    """

    value: T | None = None
    error: E | None = None

    @property
    def is_ok(self) -> bool:
        """Check if the result is successful."""
        return self.error is None and self.value is not None

    @property
    def is_err(self) -> bool:
        """Check if the result is an error."""
        return self.error is not None

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        """Create a successful result."""
        return cls(value=value, error=None)

    @classmethod
    def err(cls, error: E) -> "Result[T, E]":
        """Create an error result."""
        return cls(value=None, error=error)

    def unwrap(self) -> T:
        """Get the value or raise the error."""
        if self.is_ok:
            return self.value  # type: ignore
        raise ValueError(str(self.error))

    def unwrap_or(self, default: T) -> T:
        """Get the value or return a default."""
        if self.is_ok:
            return self.value  # type: ignore
        return default

    def map(self, fn: Callable[[T], T]) -> "Result[T, E]":
        """Map the value if successful."""
        if self.is_ok:
            return Result.ok(fn(self.value))  # type: ignore
        return self  # type: ignore

    def map_err(self, fn: Callable[[E], E]) -> "Result[T, E]":
        """Map the error if failed."""
        if self.is_err:
            return Result.err(fn(self.error))  # type: ignore
        return self  # type: ignore

    def __bool__(self) -> bool:
        """Boolean conversion - True if successful."""
        return self.is_ok

    def __repr__(self) -> str:
        if self.is_ok:
            return f"Result.ok({self.value!r})"
        return f"Result.err({self.error!r})"
