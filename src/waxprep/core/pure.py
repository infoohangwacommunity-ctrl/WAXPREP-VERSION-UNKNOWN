"""
Pure Functions - Stage 03
Algorithms and transformations with no I/O, no infrastructure.

These functions are purely computational. They take inputs and return outputs
without touching databases, external APIs, files, or any I/O.

Use these as building blocks that can be tested in isolation and combined
in different ways by services or adapters.
"""

import re
from collections.abc import Callable
from typing import Any


def normalize_text(text: str) -> str:
    """
    Normalize text by collapsing whitespace.

    - Strips leading/trailing whitespace
    - Collapses multiple spaces into single spaces

    Does NOT:
    - Perform Unicode normalization (NFC/NFKC)
    - Perform spell correction
    - Categorize content
    - Add any domain-specific transformations

    This is a limited text utility, not a comprehensive normalization function.
    """
    if not text:
        return ""

    # Strip and collapse whitespace
    normalized = " ".join(text.split())
    return normalized


def extract_keywords(text: str, min_length: int = 3) -> list[str]:
    """
    Extract potential keywords from ASCII text.

    This is a simple ASCII-centric heuristic extractor. It does NOT:
    - Use NLP models
    - Categorize into subjects
    - Score by importance
    - Support non-Latin scripts
    - Perform linguistic tokenization
    - Normalize Unicode into canonical forms

    Returns unique alphanumeric tokens that might be meaningful.

    LIMITATIONS:
    - ASCII-only regex ([a-zA-Z0-9]+) excludes many non-Latin scripts
    - Includes numeric-only tokens (e.g., "123")
    - Not suitable as a universal student-language understanding mechanism
    """
    if not text:
        return []

    # Split on non-alphanumeric
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())

    # Filter by length and return unique
    keywords: set[str] = set()
    for word in words:
        if len(word) >= min_length:
            keywords.add(word)

    return sorted(keywords)


def build_response(
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a response dictionary.

    This is a pure function that assembles a response structure.
    It does NOT send the response or interact with any system.

    The structure is intentionally generic - implementations can extend it.
    """
    response: dict[str, Any] = {
        "content": content,
    }

    if metadata:
        response["metadata"] = metadata

    return response


def compose_handlers(
    handlers: list[Callable[[Any], Any]],
) -> Callable[[Any], Any]:
    """
    Compose multiple handler functions into a pipeline.

    Each handler receives the output of the previous handler.
    The first handler receives the initial input.

    Does NOT handle errors or async - that's the caller's responsibility.
    """

    def pipeline(input_data: Any) -> Any:
        result = input_data
        for handler in handlers:
            result = handler(result)
        return result

    return pipeline
