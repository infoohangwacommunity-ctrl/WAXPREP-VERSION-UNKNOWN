"""
Value Objects - Stage 03
Immutable, self-validating value objects for domain entities.
NO external imports - pure Python only.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self


@dataclass(frozen=True, slots=True)
class Timestamp:
    """Immutable timestamp value object."""

    value: datetime

    @classmethod
    def now(cls) -> Self:
        """Create a timestamp with current UTC time."""
        return cls(value=datetime.now(UTC))

    @classmethod
    def from_iso(cls, iso_string: str) -> Self:
        """Create a timestamp from ISO format string."""
        dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return cls(value=dt)

    def to_iso(self) -> str:
        """Convert to ISO format string."""
        return self.value.isoformat()

    def __str__(self) -> str:
        return self.to_iso()


def generate_id() -> str:
    """Generate a unique identifier."""
    from uuid import uuid4
    return str(uuid4())
