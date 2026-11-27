"""
Error Taxonomy - Stage 15

A small, explicit internal error model. Every failure carries a stable code, a
bounded category, a safe message, and a retryability classification.

BOUNDARY RULES:
- This package is pure: standard library only.
- No FastAPI, Starlette, vendor SDKs, or configuration imports.
- Outer layers translate their own exceptions into these types.

The ``category`` is a bounded value and is therefore safe to use as a metric
label. Never put exception messages, user content, or credentials in a category.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, ClassVar


class ErrorCategory(StrEnum):
    """Bounded failure categories. Safe for metric labels and log fields."""

    VALIDATION = "validation"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    DEPENDENCY_TIMEOUT = "dependency_timeout"
    RATE_LIMITED = "rate_limited"
    PROVIDER_REJECTED = "provider_rejected"
    INTERNAL_INVARIANT = "internal_invariant"
    PROGRAMMING_DEFECT = "programming_defect"
    CANCELLATION = "cancellation"
    UNKNOWN = "unknown"


class Retryability(StrEnum):
    """Whether an operation may be retried automatically."""

    NEVER = "never"
    TRANSIENT = "transient"


class WaxPrepError(Exception):
    """Base class for every WaxPrep failure.

    Subclasses declare ``code``, ``category``, ``retryability`` and
    ``default_message`` as class attributes so callers never have to guess.
    ``safe_message`` is always safe to return to a client: it must never contain
    credentials, raw provider output, prompts, or user content.
    """

    code: ClassVar[str] = "waxprep_error"
    category: ClassVar[ErrorCategory] = ErrorCategory.UNKNOWN
    retryability: ClassVar[Retryability] = Retryability.NEVER
    default_message: ClassVar[str] = "An unexpected error occurred"

    def __init__(
        self,
        safe_message: str | None = None,
        *,
        context: Mapping[str, Any] | None = None,
    ) -> None:
        self.safe_message = safe_message or self.default_message
        self.context: dict[str, Any] = dict(context or {})
        super().__init__(self.safe_message)

    @property
    def is_retryable(self) -> bool:
        """True only for failures that are safe to retry automatically."""
        return self.retryability is Retryability.TRANSIENT

    def to_fields(self) -> dict[str, str]:
        """Return bounded, log-safe fields. Never includes the message or context."""
        return {
            "error.code": self.code,
            "error.category": str(self.category),
            "error.retryable": "true" if self.is_retryable else "false",
        }


class ValidationError(WaxPrepError):
    code: ClassVar[str] = "WAX-1001"
    category: ClassVar[ErrorCategory] = ErrorCategory.VALIDATION
    default_message: ClassVar[str] = "The request could not be validated"


class ConfigurationError(WaxPrepError):
    code: ClassVar[str] = "WAX-1002"
    category: ClassVar[ErrorCategory] = ErrorCategory.CONFIGURATION
    default_message: ClassVar[str] = "The application configuration is invalid"


class AuthenticationError(WaxPrepError):
    code: ClassVar[str] = "WAX-1003"
    category: ClassVar[ErrorCategory] = ErrorCategory.AUTHENTICATION
    default_message: ClassVar[str] = "Authentication failed"


class AuthorizationError(WaxPrepError):
    code: ClassVar[str] = "WAX-1004"
    category: ClassVar[ErrorCategory] = ErrorCategory.AUTHORIZATION
    default_message: ClassVar[str] = "Permission denied"


class NotFoundError(WaxPrepError):
    code: ClassVar[str] = "WAX-1005"
    category: ClassVar[ErrorCategory] = ErrorCategory.NOT_FOUND
    default_message: ClassVar[str] = "The requested resource was not found"


class ConflictError(WaxPrepError):
    code: ClassVar[str] = "WAX-1006"
    category: ClassVar[ErrorCategory] = ErrorCategory.CONFLICT
    default_message: ClassVar[str] = "The operation conflicts with the current state"


class DependencyUnavailableError(WaxPrepError):
    code: ClassVar[str] = "WAX-2001"
    category: ClassVar[ErrorCategory] = ErrorCategory.DEPENDENCY_UNAVAILABLE
    retryability: ClassVar[Retryability] = Retryability.TRANSIENT
    default_message: ClassVar[str] = "A required dependency is unavailable"


class DependencyTimeoutError(WaxPrepError):
    code: ClassVar[str] = "WAX-2002"
    category: ClassVar[ErrorCategory] = ErrorCategory.DEPENDENCY_TIMEOUT
    retryability: ClassVar[Retryability] = Retryability.TRANSIENT
    default_message: ClassVar[str] = "A required dependency timed out"


class RateLimitedError(WaxPrepError):
    code: ClassVar[str] = "WAX-2003"
    category: ClassVar[ErrorCategory] = ErrorCategory.RATE_LIMITED
    retryability: ClassVar[Retryability] = Retryability.TRANSIENT
    default_message: ClassVar[str] = "Too many requests"


class ProviderRejectedError(WaxPrepError):
    code: ClassVar[str] = "WAX-2004"
    category: ClassVar[ErrorCategory] = ErrorCategory.PROVIDER_REJECTED
    default_message: ClassVar[str] = "An upstream provider rejected the request"


class InternalInvariantError(WaxPrepError):
    code: ClassVar[str] = "WAX-3001"
    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL_INVARIANT
    default_message: ClassVar[str] = "An internal invariant was violated"


class ProgrammingDefectError(WaxPrepError):
    code: ClassVar[str] = "WAX-3002"
    category: ClassVar[ErrorCategory] = ErrorCategory.PROGRAMMING_DEFECT
    default_message: ClassVar[str] = "An unexpected error occurred"


class CancellationError(WaxPrepError):
    """Intentional cancellation. Never retried: shutdown would resurrect work.

    The category is still bounded so telemetry can distinguish
    "shutting down" from "failed".
    """

    code: ClassVar[str] = "WAX-3003"
    category: ClassVar[ErrorCategory] = ErrorCategory.CANCELLATION
    retryability: ClassVar[Retryability] = Retryability.NEVER
    default_message: ClassVar[str] = "The operation was cancelled"
