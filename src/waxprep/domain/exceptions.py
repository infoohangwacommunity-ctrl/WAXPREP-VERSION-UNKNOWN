"""
Domain Exceptions - Stage 03
Typed exception hierarchy for domain errors.
NO external imports - pure Python only.
"""

from typing import Any


class DomainError(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        if self.context:
            return f"{self.message} | Context: {self.context}"
        return self.message


class ValidationError(DomainError):
    """Raised when domain validation fails."""

    pass


class NotFoundError(DomainError):
    """Raised when a domain entity is not found."""

    pass


class InvariantError(DomainError):
    """Raised when a domain invariant is violated."""

    pass


class StateError(DomainError):
    """Raised when an operation is not allowed in the current state."""

    pass
