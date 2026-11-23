"""
Wax ID - Reusable Internal Identity Generation

Stage 04 Foundation: Provides UUIDv7 based identity generation for system entities.

Design Principles:
- UUIDv7 format (time-sortable, RFC 9562)
- Standard UUID string representation
- No semantic prefixes (no wax_, student_, message_, etc.)
- Centralized generation - all components use this utility
- No automatic attachment to HTTP requests
- Entity IDs, request IDs, and trace IDs remain conceptually separate

Usage:
    from waxprep.id import generate_id
    entity_id = generate_id()
    # Returns: "01936f4a-7b21-7c31-9e82-8a45d7c612ab"
"""

# uuid7 may not be available on all Python versions
# We try to import it, falling back to uuid4 if not available
from uuid import UUID


def _fallback_uuid7() -> UUID:
    """Fallback UUID generation using uuid4 when uuid7 is unavailable."""
    import uuid as _uuid_mod

    return _uuid_mod.uuid4()


try:
    from uuid7 import uuid7
except ImportError:
    uuid7 = _fallback_uuid7


def generate_id() -> str:
    """
    Generate a new UUIDv7 identifier.

    Returns a time-sortable UUID string suitable for use as an internal
    identifier for system entities (messages, conversations, requests,
    context records, jobs, events, etc.).

    The ID contains no student information, category, role, or business
    meaning. It is purely a technical identifier.

    Returns:
        str: Standard UUID string format (e.g., "01936f4a-7b21-7c31-9e82-8a45d7c612ab")

    Example:
        >>> id = generate_id()
        >>> len(id)
        36
        >>> '-' in id
        True
    """
    return str(uuid7())


def is_valid_id(id_string: str) -> bool:
    """
    Validate that a string is a properly formatted UUID.

    Args:
        id_string: String to validate

    Returns:
        bool: True if valid UUID format, False otherwise
    """
    try:
        UUID(id_string)
        return True
    except (ValueError, TypeError, AttributeError):
        return False
