"""
Adapters - Stage 03

This package contains implementations of ports (adapters).

Dependency Rule: Adapters may import domain/ and application/ports/.
They may NOT import other adapters or infrastructure/.

NO cross-adapter imports allowed.
"""

# This module intentionally does NOT import from other adapters
# to maintain adapter isolation as per hexagonal architecture rules.

# Adapters are discovered and registered through the registry system,
# not through this __init__.py file.

__all__ = []
