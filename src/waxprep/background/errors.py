"""Typed background-execution failures (Stage 19)."""

from __future__ import annotations

from typing import ClassVar

from waxprep.errors.taxonomy import ErrorCategory, Retryability, WaxPrepError


class BackgroundError(WaxPrepError):
    """Base class for background execution failures."""

    code: ClassVar[str] = "WAX-7000"
    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL_INVARIANT
    default_message: ClassVar[str] = "Background execution failed"


class JobRegistrationError(BackgroundError):
    code: ClassVar[str] = "WAX-7001"
    category: ClassVar[ErrorCategory] = ErrorCategory.PROGRAMMING_DEFECT
    default_message: ClassVar[str] = "The background job registration is invalid"


class JobSubmissionError(BackgroundError):
    code: ClassVar[str] = "WAX-7002"
    category: ClassVar[ErrorCategory] = ErrorCategory.DEPENDENCY_UNAVAILABLE
    retryability: ClassVar[Retryability] = Retryability.TRANSIENT
    default_message: ClassVar[str] = "The background job could not be submitted"


class JobValidationError(BackgroundError):
    code: ClassVar[str] = "WAX-7003"
    category: ClassVar[ErrorCategory] = ErrorCategory.VALIDATION
    default_message: ClassVar[str] = "The background job message is invalid"


class JobExecutionError(BackgroundError):
    code: ClassVar[str] = "WAX-7004"
    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL_INVARIANT
    default_message: ClassVar[str] = "The background job handler failed"


class BackgroundUnavailableError(BackgroundError):
    code: ClassVar[str] = "WAX-7005"
    category: ClassVar[ErrorCategory] = ErrorCategory.DEPENDENCY_UNAVAILABLE
    retryability: ClassVar[Retryability] = Retryability.TRANSIENT
    default_message: ClassVar[str] = "Background execution is unavailable"
