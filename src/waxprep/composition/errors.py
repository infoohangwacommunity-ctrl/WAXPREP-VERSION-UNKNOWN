"""Typed composition failures (Stage 18).

Composition errors reuse the Stage 15 taxonomy: a broken dependency graph is an
internal invariant/programming defect, not an external validation failure.
"""

from __future__ import annotations

from typing import ClassVar

from waxprep.errors.taxonomy import ErrorCategory, WaxPrepError


class CompositionError(WaxPrepError):
    """The application could not be assembled from its dependency graph."""

    code: ClassVar[str] = "WAX-6000"
    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL_INVARIANT
    default_message: ClassVar[str] = "The application dependency graph is invalid"


class DuplicateProviderError(CompositionError):
    code: ClassVar[str] = "WAX-6001"
    default_message: ClassVar[str] = "A duplicate dependency provider was registered"


class MissingDependencyError(CompositionError):
    code: ClassVar[str] = "WAX-6002"
    default_message: ClassVar[str] = "A required dependency has no provider"


class CircularDependencyError(CompositionError):
    code: ClassVar[str] = "WAX-6003"
    default_message: ClassVar[str] = "The dependency graph contains a cycle"


class LifetimeViolationError(CompositionError):
    code: ClassVar[str] = "WAX-6004"
    default_message: ClassVar[str] = "A dependency lifetime is shorter than its consumer"


class ScopeError(CompositionError):
    code: ClassVar[str] = "WAX-6005"
    default_message: ClassVar[str] = "A dependency cannot be resolved in this scope"


class ProviderSignatureError(CompositionError):
    """A provider factory cannot accept its declared dependencies."""

    code: ClassVar[str] = "WAX-6006"
    default_message: ClassVar[str] = "A provider factory signature does not match its dependencies"
