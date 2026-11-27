"""WaxPrep error taxonomy and retry policy (Stage 15).

Pure package: standard library only. Outer layers translate their vendor and
framework exceptions into these types at their own boundaries.
"""

from waxprep.errors.retry import RetryPolicy, run_with_retry
from waxprep.errors.taxonomy import (
    AuthenticationError,
    AuthorizationError,
    CancellationError,
    ConfigurationError,
    ConflictError,
    DependencyTimeoutError,
    DependencyUnavailableError,
    ErrorCategory,
    InternalInvariantError,
    NotFoundError,
    ProgrammingDefectError,
    ProviderRejectedError,
    RateLimitedError,
    Retryability,
    ValidationError,
    WaxPrepError,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "CancellationError",
    "ConfigurationError",
    "ConflictError",
    "DependencyTimeoutError",
    "DependencyUnavailableError",
    "ErrorCategory",
    "InternalInvariantError",
    "NotFoundError",
    "ProgrammingDefectError",
    "ProviderRejectedError",
    "RateLimitedError",
    "RetryPolicy",
    "Retryability",
    "ValidationError",
    "WaxPrepError",
    "run_with_retry",
]
