"""Dependency name handling for Stage 09.

Lockfiles and requirement declarations do not have to spell a package the same
way (``python-dotenv`` vs ``python_dotenv``). Checks must compare canonical
names, never raw strings, or a dependency could appear resolved while a
lookup misses it.
"""

from __future__ import annotations

import re

# PEP 503: lowercase, and collapse runs of -, _ and . to a single hyphen.
_CANONICAL_SEPARATOR = re.compile(r"[-_.]+")

# Requirement grammar before the version specifier: name, optional extras.
_REQUIREMENT_PREFIX = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[[^\]]*\])?\s*(.*)$")


def canonical_name(name: str) -> str:
    """Return the PEP 503 normalized form of a package name."""
    return _CANONICAL_SEPARATOR.sub("-", name.strip().lower())


def _requirement_part(requirement: str, group: int) -> str:
    match = _REQUIREMENT_PREFIX.match(requirement)
    if match is None:
        raise ValueError(f"not a requirement string: {requirement!r}")
    return match.group(group).strip()


def requirement_name(requirement: str) -> str:
    """Return the package name from a PEP 508 requirement string.

    Extras and environment markers are ignored here; the supply-chain checks
    only need the name and the version specifier.
    """
    return _requirement_part(requirement, 1)


def requirement_specifier(requirement: str) -> str:
    """Return the version specifier of a requirement, or ``""`` when absent."""
    return _requirement_part(requirement, 2).split(";", 1)[0].strip()
