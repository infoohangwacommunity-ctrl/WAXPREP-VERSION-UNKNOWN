"""
Domain Layer - Stage 03
Pure business logic. NO external imports (only stdlib and domain).
NO framework imports. NO provider SDKs. NO FastAPI. NO LiteLLM.
"""

from waxprep.domain.exceptions import (
    DomainError,
    InvariantError,
    NotFoundError,
    ValidationError,
)
from waxprep.domain.models.result import Error, Result
from waxprep.domain.value_objects import Timestamp

__all__ = [
    # Exceptions
    "DomainError",
    "InvariantError",
    "NotFoundError",
    "ValidationError",
    # Models
    "Error",
    "Result",
    # Value Objects
    "Timestamp",
]
