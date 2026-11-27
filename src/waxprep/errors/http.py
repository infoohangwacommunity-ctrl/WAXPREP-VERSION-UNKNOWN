"""
HTTP Error Boundary - Stage 15

The only place internal error meaning becomes an HTTP response. Business logic
stays out of exception handlers; they translate and report, nothing more.

Public contract (deliberately unchanged from the Stage 01-11 foundation so
existing clients and tests keep working):

    4xx/5xx  {"detail": "<safe summary>", ...}
    500      {"detail": "Internal server error",
              "message": "An unexpected error occurred"}

Every response carries the effective correlation ID via X-Request-ID, and no
response ever contains a traceback, file path, exception class, or secret.
"""

from __future__ import annotations

import structlog

from waxprep.errors.taxonomy import (
    ErrorCategory,
    WaxPrepError,
)

logger = structlog.get_logger()

GENERIC_DETAIL = "Internal server error"
GENERIC_MESSAGE = "An unexpected error occurred"

# Bounded mapping from internal category to public HTTP status. Categories that
# are not request-shaped (timeouts, cancellations, dependency outages) map to
# 503 so clients can distinguish "retry later" from "your request is wrong".
_CATEGORY_STATUS: dict[ErrorCategory, int] = {
    ErrorCategory.VALIDATION: 422,
    ErrorCategory.AUTHENTICATION: 401,
    ErrorCategory.AUTHORIZATION: 403,
    ErrorCategory.NOT_FOUND: 404,
    ErrorCategory.CONFLICT: 409,
    ErrorCategory.RATE_LIMITED: 429,
    ErrorCategory.DEPENDENCY_UNAVAILABLE: 503,
    ErrorCategory.DEPENDENCY_TIMEOUT: 504,
    ErrorCategory.CANCELLATION: 503,
    ErrorCategory.PROVIDER_REJECTED: 502,
    ErrorCategory.INTERNAL_INVARIANT: 500,
    ErrorCategory.PROGRAMMING_DEFECT: 500,
    ErrorCategory.CONFIGURATION: 500,
    ErrorCategory.UNKNOWN: 500,
}


def status_for(category: ErrorCategory) -> int:
    """Return the public HTTP status for an internal error category."""
    return _CATEGORY_STATUS.get(category, 500)


def should_expose_message(category: ErrorCategory) -> bool:
    """Only client-facing categories may surface their safe message.

    Server-side categories stay generic so an internal detail can never leak
    through a message that was written for operators.
    """
    return category in {
        ErrorCategory.VALIDATION,
        ErrorCategory.NOT_FOUND,
        ErrorCategory.CONFLICT,
        ErrorCategory.AUTHENTICATION,
        ErrorCategory.AUTHORIZATION,
        ErrorCategory.RATE_LIMITED,
    }


def public_body(error: WaxPrepError) -> dict[str, object]:
    """Build the sanitized response body for a WaxPrep error."""
    status = status_for(error.category)
    if status >= 500:
        return {"detail": GENERIC_DETAIL, "message": GENERIC_MESSAGE}
    return {"detail": error.safe_message}
