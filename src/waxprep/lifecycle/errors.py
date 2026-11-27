"""Typed lifecycle failures.

They reuse the Stage 15 error taxonomy so the HTTP boundary and logs already
know how to classify them as bounded ``internal_invariant`` failures.
"""

from __future__ import annotations

from typing import ClassVar

from waxprep.errors.taxonomy import ErrorCategory, WaxPrepError


class LifecycleError(WaxPrepError):
    """The application lifecycle could not perform an operation safely."""

    code: ClassVar[str] = "WAX-4001"
    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL_INVARIANT
    default_message: ClassVar[str] = "The application lifecycle operation failed"


class LifecycleTransitionError(LifecycleError):
    """A state transition outside the documented contract was requested."""

    code: ClassVar[str] = "WAX-4002"
    default_message: ClassVar[str] = "The requested lifecycle state transition is not allowed"


class ResourceOwnershipError(LifecycleError):
    """A resource has no unique owner or a dependency was not registered."""

    code: ClassVar[str] = "WAX-4003"
    default_message: ClassVar[str] = "The resource ownership contract was violated"
