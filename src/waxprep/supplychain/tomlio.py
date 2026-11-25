"""Strict TOML helpers for Stage 09 supply-chain data.

The supply-chain gate reads ``uv.lock`` and its own policy files. Both are
TOML, so the gate uses the standard library and adds no dependency of its own.
These helpers turn malformed structures into a single error type with a
useful location instead of leaking ``KeyError``/``TypeError`` from deep
inside a check.
"""

from __future__ import annotations

import tomllib
from pathlib import Path


class TomlError(ValueError):
    """A TOML document is missing, unparsable or structurally invalid."""


def load_table(path: Path) -> dict[str, object]:
    """Load a TOML document and require a table at the top level."""
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise TomlError(f"missing file: {path}") from exc
    except OSError as exc:
        raise TomlError(f"cannot read {path}: {exc}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise TomlError(f"invalid TOML in {path}: {exc}") from exc
    return as_table(data, str(path))


def as_table(value: object, where: str) -> dict[str, object]:
    """Return ``value`` as a string-keyed table or raise :class:`TomlError`."""
    if not isinstance(value, dict):
        raise TomlError(f"{where}: expected a table")
    return {str(key): item for key, item in value.items()}


def require_str(table: dict[str, object], key: str, where: str) -> str:
    """Return a required, non-empty string field."""
    value = table.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TomlError(f"{where}: '{key}' must be a non-empty string")
    return value.strip()


def require_bool(table: dict[str, object], key: str, where: str) -> bool:
    """Return a required boolean field."""
    value = table.get(key)
    if not isinstance(value, bool):
        raise TomlError(f"{where}: '{key}' must be true or false")
    return value


def string_list(value: object, where: str) -> tuple[str, ...]:
    """Return a list of non-empty strings, preserving order."""
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TomlError(f"{where}: expected an array of strings")
    items = tuple(str(item).strip() for item in value)
    if any(not item for item in items):
        raise TomlError(f"{where}: entries must be non-empty")
    return items


def string_map(table: dict[str, object], key: str, where: str) -> dict[str, str]:
    """Return a required table of string to non-empty string."""
    raw = table.get(key)
    mapping = as_table(raw, f"{where}.{key}")
    result: dict[str, str] = {}
    for entry_key, entry_value in mapping.items():
        if not isinstance(entry_value, str) or not entry_value.strip():
            raise TomlError(f"{where}.{key}.{entry_key}: expected a non-empty string")
        result[entry_key] = entry_value.strip()
    return result
