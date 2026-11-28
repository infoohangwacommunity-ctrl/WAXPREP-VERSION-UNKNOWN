"""Contract identity, semantic versions and compatibility rules (Stage 17).

Published contracts use ``name.major.minor.patch`` identity:

* name: lower-case dot-separated identity, e.g. ``waxprep.notebook.lookup.request``;
* version: strict semantic version, e.g. ``1.0.0``.

Compatibility is not inferred from Python still running. Structural schema
changes are classified against an explicit policy. Semantic meaning changes
cannot be detected mechanically and are always breaking: a contract owner must
record them explicitly and bump the major version.

The comparator is intentionally conservative: when a change cannot be proven
compatible, it is reported as breaking (or conditional where the direction
depends on the documented consumer policy).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_NAME = re.compile(r"^[a-z][a-z0-9]*(\.[a-z0-9]+)+$")


class InvalidContractVersionError(ValueError):
    """A contract version string is not strict semantic versioning."""


@dataclass(frozen=True, order=True, slots=True)
class ContractVersion:
    """Strict ``major.minor.patch`` version."""

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        for name, value in (("major", self.major), ("minor", self.minor), ("patch", self.patch)):
            if value < 0:
                raise InvalidContractVersionError(f"{name} must be non-negative")

    @classmethod
    def parse(cls, value: str) -> ContractVersion:
        match = _SEMVER.fullmatch(value)
        if match is None:
            raise InvalidContractVersionError("Contract version must be strict major.minor.patch")
        return cls(*(int(part) for part in match.groups()))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def bump_major(self) -> ContractVersion:
        return ContractVersion(self.major + 1, 0, 0)

    def bump_minor(self) -> ContractVersion:
        return ContractVersion(self.major, self.minor + 1, 0)

    def bump_patch(self) -> ContractVersion:
        return ContractVersion(self.major, self.minor, self.patch + 1)


@dataclass(frozen=True, slots=True)
class ContractIdentity:
    """Stable identity of one published contract revision."""

    name: str
    version: ContractVersion

    def __post_init__(self) -> None:
        if _NAME.fullmatch(self.name) is None:
            raise InvalidContractVersionError(
                "Contract name must be lower-case dot-separated, e.g. waxprep.domain.request"
            )

    @classmethod
    def parse(cls, value: str) -> ContractIdentity:
        name, separator, version = value.rpartition("@")
        if not separator or not name or not version:
            raise InvalidContractVersionError("Contract identity must be 'name@major.minor.patch'")
        return cls(name=name, version=ContractVersion.parse(version))

    def __str__(self) -> str:
        return f"{self.name}@{self.version}"

    @property
    def urn(self) -> str:
        return f"urn:waxprep:contract:{self.name}:{self.version}"


class ChangeType(StrEnum):
    """Bounded structural change vocabulary."""

    NONE = "none"
    ADD_OPTIONAL_FIELD = "add_optional_field"
    ADD_REQUIRED_FIELD = "add_required_field"
    REQUIRED_FIELD_OPTIONAL = "required_field_optional"
    REMOVE_FIELD = "remove_field"
    TYPE_CHANGE = "type_change"
    ENUM_VALUE_ADDED = "enum_value_added"
    ENUM_VALUE_REMOVED = "enum_value_removed"
    VALIDATION_RESTRICTED = "validation_restricted"
    VALIDATION_RELAXED = "validation_relaxed"
    ADDITIONAL_PROPERTIES_RELAXED = "additional_properties_relaxed"
    ADDITIONAL_PROPERTIES_RESTRICTED = "additional_properties_restricted"
    VARIANT_ADDED = "variant_added"
    VARIANT_REMOVED = "variant_removed"
    SEMANTIC_CHANGE = "semantic_change"
    SERIALIZATION_CHANGE = "serialization_change"


class Compatibility(StrEnum):
    """How a change affects consumers/producers."""

    COMPATIBLE = "compatible"
    CONDITIONAL = "conditional"
    BREAKING = "breaking"


class VersionBump(StrEnum):
    """Recommended semantic version component to increment."""

    MAJOR = "major"
    MINOR = "minor"
    PATCH = "patch"


_POLICY: dict[ChangeType, Compatibility] = {
    ChangeType.NONE: Compatibility.COMPATIBLE,
    ChangeType.ADD_OPTIONAL_FIELD: Compatibility.COMPATIBLE,
    ChangeType.ADD_REQUIRED_FIELD: Compatibility.BREAKING,
    ChangeType.REQUIRED_FIELD_OPTIONAL: Compatibility.CONDITIONAL,
    ChangeType.REMOVE_FIELD: Compatibility.BREAKING,
    ChangeType.TYPE_CHANGE: Compatibility.BREAKING,
    ChangeType.ENUM_VALUE_ADDED: Compatibility.CONDITIONAL,
    ChangeType.ENUM_VALUE_REMOVED: Compatibility.BREAKING,
    ChangeType.VALIDATION_RESTRICTED: Compatibility.BREAKING,
    ChangeType.VALIDATION_RELAXED: Compatibility.CONDITIONAL,
    ChangeType.ADDITIONAL_PROPERTIES_RELAXED: Compatibility.CONDITIONAL,
    ChangeType.ADDITIONAL_PROPERTIES_RESTRICTED: Compatibility.BREAKING,
    ChangeType.VARIANT_ADDED: Compatibility.CONDITIONAL,
    ChangeType.VARIANT_REMOVED: Compatibility.BREAKING,
    ChangeType.SEMANTIC_CHANGE: Compatibility.BREAKING,
    ChangeType.SERIALIZATION_CHANGE: Compatibility.BREAKING,
}


def classify_change(change: ChangeType) -> Compatibility:
    """Return the documented compatibility class for a structural change."""
    return _POLICY[change]


@dataclass(frozen=True, slots=True)
class SchemaChange:
    path: str
    change: ChangeType
    detail: str

    @property
    def compatibility(self) -> Compatibility:
        return classify_change(self.change)


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    changes: tuple[SchemaChange, ...]

    @property
    def classification(self) -> Compatibility:
        if any(change.compatibility is Compatibility.BREAKING for change in self.changes):
            return Compatibility.BREAKING
        if any(change.compatibility is Compatibility.CONDITIONAL for change in self.changes):
            return Compatibility.CONDITIONAL
        return Compatibility.COMPATIBLE

    @property
    def compatible(self) -> bool:
        return self.classification is not Compatibility.BREAKING

    @property
    def recommended_bump(self) -> VersionBump:
        if self.classification is Compatibility.BREAKING:
            return VersionBump.MAJOR
        if self.classification is Compatibility.CONDITIONAL:
            return VersionBump.MINOR
        return VersionBump.PATCH


def _resolve(node: Any, root: dict[str, Any]) -> Any:
    """Resolve a local ``#/$defs/...`` reference used by Pydantic schemas."""
    seen: set[str] = set()
    while isinstance(node, dict):
        reference = node.get("$ref")
        if not isinstance(reference, str):
            break
        if reference in seen or not reference.startswith("#/$defs/"):
            return node
        seen.add(reference)
        name = reference.removeprefix("#/$defs/")
        definitions = root.get("$defs")
        if not isinstance(definitions, dict) or name not in definitions:
            return node
        node = definitions[name]
    return node


def _type_of(node: Any) -> Any:
    return node.get("type") if isinstance(node, dict) else None


def _compare_node(
    old: Any,
    new: Any,
    *,
    path: str,
    old_root: dict[str, Any],
    new_root: dict[str, Any],
    seen: set[tuple[int, int]],
) -> list[SchemaChange]:
    old = _resolve(old, old_root)
    new = _resolve(new, new_root)
    if not isinstance(old, dict) or not isinstance(new, dict):
        return [SchemaChange(path, ChangeType.TYPE_CHANGE, "schema shape changed")]
    identity = (id(old), id(new))
    if identity in seen:
        return []
    seen.add(identity)

    changes: list[SchemaChange] = []
    if _type_of(old) != _type_of(new):
        changes.append(SchemaChange(path, ChangeType.TYPE_CHANGE, "type changed"))
        return changes

    changes.extend(_compare_enum(old, new, path))
    changes.extend(_compare_properties(old, new, path, old_root, new_root, seen))
    changes.extend(_compare_required(old, new, path))
    changes.extend(_compare_variants(old, new, path, old_root, new_root, seen))
    changes.extend(_compare_additional_properties(old, new, path))
    changes.extend(_compare_bounds(old, new, path))
    return changes


def _compare_enum(old: dict[str, Any], new: dict[str, Any], path: str) -> list[SchemaChange]:
    if "const" in old or "const" in new:
        if old.get("const") != new.get("const"):
            return [SchemaChange(path, ChangeType.ENUM_VALUE_REMOVED, "const changed")]
        return []
    old_values = old.get("enum")
    new_values = new.get("enum")
    if not isinstance(old_values, list) or not isinstance(new_values, list):
        return []
    old_set = {str(value) for value in old_values}
    new_set = {str(value) for value in new_values}
    changes: list[SchemaChange] = []
    if old_set - new_set:
        changes.append(SchemaChange(path, ChangeType.ENUM_VALUE_REMOVED, "enum value removed"))
    if new_set - old_set:
        changes.append(SchemaChange(path, ChangeType.ENUM_VALUE_ADDED, "enum value added"))
    return changes


def _compare_properties(
    old: dict[str, Any],
    new: dict[str, Any],
    path: str,
    old_root: dict[str, Any],
    new_root: dict[str, Any],
    seen: set[tuple[int, int]],
) -> list[SchemaChange]:
    old_properties = old.get("properties")
    new_properties = new.get("properties")
    if not isinstance(old_properties, dict) or not isinstance(new_properties, dict):
        return []
    changes: list[SchemaChange] = []
    new_required = set(new.get("required") or ())
    for name, old_property in old_properties.items():
        if name not in new_properties:
            changes.append(
                SchemaChange(f"{path}.{name}", ChangeType.REMOVE_FIELD, "property removed")
            )
            continue
        changes.extend(
            _compare_node(
                old_property,
                new_properties[name],
                path=f"{path}.{name}",
                old_root=old_root,
                new_root=new_root,
                seen=seen,
            )
        )
    for name in new_properties:
        if name in old_properties:
            continue
        change = (
            ChangeType.ADD_REQUIRED_FIELD if name in new_required else ChangeType.ADD_OPTIONAL_FIELD
        )
        changes.append(SchemaChange(f"{path}.{name}", change, "property added"))
    return changes


def _compare_required(old: dict[str, Any], new: dict[str, Any], path: str) -> list[SchemaChange]:
    old_required = set(old.get("required") or ())
    new_required = set(new.get("required") or ())
    changes: list[SchemaChange] = []
    if new_required - old_required:
        changes.append(SchemaChange(path, ChangeType.ADD_REQUIRED_FIELD, "required field added"))
    if old_required - new_required:
        changes.append(
            SchemaChange(path, ChangeType.REQUIRED_FIELD_OPTIONAL, "required field relaxed")
        )
    return changes


def _variant_key(node: Any, root: dict[str, Any]) -> str:
    resolved = _resolve(node, root)
    if isinstance(resolved, dict):
        value = resolved.get("const")
        if value is not None:
            return str(value)
        properties = resolved.get("properties")
        if isinstance(properties, dict):
            for name, schema in properties.items():
                if isinstance(schema, dict) and schema.get("const") is not None:
                    return f"{name}={schema['const']}"
    return str(_type_of(resolved))


def _variants(node: dict[str, Any], root: dict[str, Any]) -> dict[str, Any]:
    for key in ("oneOf", "anyOf"):
        value = node.get(key)
        if isinstance(value, list):
            return {_variant_key(item, root): item for item in value}
    return {}


def _compare_variants(
    old: dict[str, Any],
    new: dict[str, Any],
    path: str,
    old_root: dict[str, Any],
    new_root: dict[str, Any],
    seen: set[tuple[int, int]],
) -> list[SchemaChange]:
    old_variants = _variants(old, old_root)
    new_variants = _variants(new, new_root)
    if not old_variants and not new_variants:
        return []
    changes: list[SchemaChange] = []
    for key, old_variant in old_variants.items():
        if key not in new_variants:
            changes.append(
                SchemaChange(f"{path}[{key}]", ChangeType.VARIANT_REMOVED, "variant removed")
            )
            continue
        changes.extend(
            _compare_node(
                old_variant,
                new_variants[key],
                path=f"{path}[{key}]",
                old_root=old_root,
                new_root=new_root,
                seen=seen,
            )
        )
    for key in new_variants:
        if key not in old_variants:
            changes.append(
                SchemaChange(f"{path}[{key}]", ChangeType.VARIANT_ADDED, "variant added")
            )
    return changes


def _compare_additional_properties(
    old: dict[str, Any], new: dict[str, Any], path: str
) -> list[SchemaChange]:
    old_value = old.get("additionalProperties", True)
    new_value = new.get("additionalProperties", True)
    if old_value == new_value:
        return []
    if old_value is False and new_value is not False:
        return [SchemaChange(path, ChangeType.ADDITIONAL_PROPERTIES_RELAXED, "extras allowed")]
    if new_value is False:
        return [SchemaChange(path, ChangeType.ADDITIONAL_PROPERTIES_RESTRICTED, "extras forbidden")]
    return []


_BOUNDS = (
    ("minLength", True),
    ("maxLength", False),
    ("minimum", True),
    ("maximum", False),
    ("exclusiveMinimum", True),
    ("exclusiveMaximum", False),
    ("minItems", True),
    ("maxItems", False),
    ("minProperties", True),
    ("maxProperties", False),
)


def _compare_bounds(old: dict[str, Any], new: dict[str, Any], path: str) -> list[SchemaChange]:
    changes: list[SchemaChange] = []
    for name, tightening in _BOUNDS:
        old_value = old.get(name)
        new_value = new.get(name)
        if old_value == new_value:
            continue
        if old_value is None:
            change = (
                ChangeType.VALIDATION_RESTRICTED if tightening else ChangeType.VALIDATION_RELAXED
            )
            changes.append(SchemaChange(f"{path}.{name}", change, "bound added"))
            continue
        if new_value is None:
            change = (
                ChangeType.VALIDATION_RELAXED if tightening else ChangeType.VALIDATION_RESTRICTED
            )
            changes.append(SchemaChange(f"{path}.{name}", change, "bound removed"))
            continue
        if not isinstance(old_value, (int, float)) or not isinstance(new_value, (int, float)):
            changes.append(
                SchemaChange(f"{path}.{name}", ChangeType.VALIDATION_RESTRICTED, "bound changed")
            )
            continue
        if (tightening and new_value > old_value) or (not tightening and new_value < old_value):
            changes.append(
                SchemaChange(f"{path}.{name}", ChangeType.VALIDATION_RESTRICTED, "bound tightened")
            )
        else:
            changes.append(
                SchemaChange(f"{path}.{name}", ChangeType.VALIDATION_RELAXED, "bound relaxed")
            )
    return changes


def compare_schemas(old: dict[str, Any], new: dict[str, Any]) -> CompatibilityReport:
    """Classify structural changes between two JSON schemas."""
    changes = _compare_node(
        old,
        new,
        path="$",
        old_root=old,
        new_root=new,
        seen=set(),
    )
    return CompatibilityReport(tuple(changes))
