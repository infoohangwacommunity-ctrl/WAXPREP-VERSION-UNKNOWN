"""Dependency policy loading for Stage 09.

Three machine-readable policies live under ``security/dependency-policy/``:

* vulnerability exceptions — advisory + package + affected versions, owner,
  reason, review date and remediation evidence;
* license policy — approved, review-required and prohibited SPDX identifiers;
* source policy — allowed registries, whether VCS/URL sources are allowed,
  reviewed major versions and the documented purpose/owner of each direct
  runtime dependency.

Policies are TOML so the gate itself adds no dependency. A missing or invalid
policy is an error, never "no policy configured": an absent exception register
must not silently allow every advisory.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from pathlib import Path

from waxprep.supplychain.names import canonical_name
from waxprep.supplychain.tomlio import (
    TomlError,
    as_table,
    load_table,
    require_bool,
    require_str,
    string_list,
    string_map,
)

POLICY_DIRECTORY = Path("security") / "dependency-policy"
DEPENDENCY_REVIEW_CONFIG = Path(".github") / "dependency-review-config.yml"


class PolicyError(ValueError):
    """A dependency policy is missing, unreadable or inconsistent."""


class LicenseDecision(StrEnum):
    """Outcome of applying the license policy to one expression."""

    APPROVED = "approved"
    REVIEW = "review"
    PROHIBITED = "prohibited"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VulnerabilityException:
    """A tracked, scoped acceptance of one advisory for one package version."""

    advisory: str
    package: str
    versions: tuple[str, ...]
    reason: str
    risk: str
    owner: str
    introduced: date
    review_by: date
    remediation_evidence: str

    def covers(self, advisory: str, package: str, version: str) -> bool:
        """True only for this advisory, this package and an affected version."""
        return (
            advisory == self.advisory
            and canonical_name(package) == canonical_name(self.package)
            and version in self.versions
        )

    def matches_any(self, advisory_ids: tuple[str, ...], package: str, version: str) -> bool:
        """True when any identifier of an advisory is covered by this exception."""
        return any(self.covers(advisory, package, version) for advisory in advisory_ids)

    def is_expired(self, today: date) -> bool:
        """An exception expires the day after its review date."""
        return today > self.review_by


@dataclass(frozen=True)
class LicensePolicy:
    """SPDX license policy.

    ``approved`` passes, ``review`` requires a human decision and
    ``prohibited`` blocks. Anything not listed is unknown and requires review.
    Compound expressions are accepted only when every atom is approved.
    """

    approved: frozenset[str]
    review: frozenset[str]
    prohibited: frozenset[str]
    reviewed: Mapping[str, str] = field(default_factory=dict)

    def accepted(self, expression: str | None) -> bool:
        """True when every atom is approved or explicitly reviewed by a human."""
        atoms = _license_atoms(expression)
        return bool(atoms) and all(atom in self.approved or atom in self.reviewed for atom in atoms)

    def classify(self, expression: str | None) -> LicenseDecision:
        """Classify a license expression against this policy."""
        atoms = _license_atoms(expression)
        if not atoms:
            return LicenseDecision.UNKNOWN
        if any(atom in self.prohibited for atom in atoms):
            return LicenseDecision.PROHIBITED
        if all(atom in self.approved for atom in atoms):
            return LicenseDecision.APPROVED
        if any(atom in self.review for atom in atoms):
            return LicenseDecision.REVIEW
        return LicenseDecision.UNKNOWN


@dataclass(frozen=True)
class SourcePolicy:
    """Allowed dependency origins and reviewed major versions."""

    allowed_registries: tuple[str, ...]
    allow_vcs: bool
    allow_url: bool
    reviewed_majors: Mapping[str, frozenset[int]]

    def registry_allowed(self, url: str) -> bool:
        """True when a registry URL matches an allowed registry."""
        return url.rstrip("/") in {allowed.rstrip("/") for allowed in self.allowed_registries}

    def major_reviewed(self, package: str, version: str) -> bool:
        """True when this package's resolved major version has been reviewed."""
        major = version.split(".", 1)[0]
        if not major.isdigit():
            return False
        return int(major) in self.reviewed_majors.get(canonical_name(package), frozenset())


@dataclass(frozen=True)
class DependencyInventory:
    """Why each direct runtime dependency exists and who owns it."""

    purposes: Mapping[str, str]
    owners: Mapping[str, str]

    def purpose_for(self, package: str) -> str | None:
        """Return the documented purpose, if any."""
        return self.purposes.get(canonical_name(package))


@dataclass(frozen=True)
class DependencyPolicy:
    """Combined Stage 09 policy."""

    exceptions: tuple[VulnerabilityException, ...]
    licenses: LicensePolicy
    sources: SourcePolicy
    inventory: DependencyInventory


def _license_atoms(expression: str | None) -> tuple[str, ...]:
    """Split an SPDX expression into identifiers, preserving none of the operators."""
    if not expression:
        return ()
    cleaned = re.sub(r"[()]", " ", expression)
    atoms = (part.strip() for part in re.split(r"\s+(?:OR|AND)\s+", cleaned))
    return tuple(atom for atom in atoms if atom)


def _as_date(value: object, where: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise PolicyError(f"{where}: expected an ISO date") from exc
    raise PolicyError(f"{where}: expected an ISO date")


def _require_bool(table: dict[str, object], key: str, where: str) -> bool:
    try:
        return require_bool(table, key, where)
    except TomlError as exc:
        raise PolicyError(str(exc)) from exc


def _require_str(table: dict[str, object], key: str, where: str) -> str:
    try:
        return require_str(table, key, where)
    except TomlError as exc:
        raise PolicyError(str(exc)) from exc


def _string_list(value: object, where: str) -> tuple[str, ...]:
    try:
        return string_list(value, where)
    except TomlError as exc:
        raise PolicyError(str(exc)) from exc


def _table(value: object, where: str) -> dict[str, object]:
    try:
        return as_table(value, where)
    except TomlError as exc:
        raise PolicyError(str(exc)) from exc


def _load_toml(path: Path) -> dict[str, object]:
    try:
        return load_table(path)
    except TomlError as exc:
        raise PolicyError(str(exc)) from exc


def _load_exceptions(path: Path) -> tuple[VulnerabilityException, ...]:
    data = _load_toml(path)
    raw = data.get("exceptions")
    if not isinstance(raw, list):
        raise PolicyError(f"{path}: 'exceptions' must be an array of tables")

    exceptions: list[VulnerabilityException] = []
    for index, item in enumerate(raw):
        where = f"{path}: exception #{index + 1}"
        table = _table(item, where)
        versions = _string_list(table.get("versions"), f"{where}.versions")
        if not versions:
            raise PolicyError(f"{where}.versions: at least one version is required")
        exception = VulnerabilityException(
            advisory=_require_str(table, "advisory", where),
            package=_require_str(table, "package", where),
            versions=versions,
            reason=_require_str(table, "reason", where),
            risk=_require_str(table, "risk", where),
            owner=_require_str(table, "owner", where),
            introduced=_as_date(table.get("introduced"), f"{where}.introduced"),
            review_by=_as_date(table.get("review_by"), f"{where}.review_by"),
            remediation_evidence=_require_str(table, "remediation_evidence", where),
        )
        if exception.review_by < exception.introduced:
            raise PolicyError(f"{where}: review_by must not precede introduced")
        exceptions.append(exception)
    return tuple(exceptions)


def _load_reviewed_licenses(raw: object, where: str) -> Mapping[str, str]:
    """Read explicit human acceptances of review-required licenses."""
    table = _table(raw if raw is not None else {}, where)
    reviewed: dict[str, str] = {}
    for license_id, note in table.items():
        if not isinstance(note, str) or not note.strip():
            raise PolicyError(f"{where}.{license_id}: expected a non-empty string")
        reviewed[license_id] = note.strip()
    return reviewed


def _load_license_policy(path: Path) -> LicensePolicy:
    data = _load_toml(path)
    approved = frozenset(_string_list(data.get("approved"), f"{path}.approved"))
    review = frozenset(_string_list(data.get("review"), f"{path}.review"))
    prohibited = frozenset(_string_list(data.get("prohibited"), f"{path}.prohibited"))
    if not approved:
        raise PolicyError(f"{path}: 'approved' must list at least one SPDX identifier")
    overlap = (approved & review) | (approved & prohibited) | (review & prohibited)
    if overlap:
        raise PolicyError(f"{path}: license policy lists are not disjoint: {sorted(overlap)}")
    reviewed = _load_reviewed_licenses(data.get("reviewed"), f"{path}.reviewed")
    conflict = sorted(set(reviewed) & (approved | prohibited))
    if conflict:
        raise PolicyError(
            f"{path}.reviewed: listed as approved or prohibited as well: {', '.join(conflict)}"
        )
    return LicensePolicy(approved=approved, review=review, prohibited=prohibited, reviewed=reviewed)


def dependency_review_licenses(path: Path) -> tuple[str, ...]:
    """Read ``allow_licenses`` from the GitHub Dependency Review config.

    The Dependency Review workflow must never allow a license the internal
    policy does not approve, or a review-required license could become
    approved silently in pull requests.

    Raises:
        PolicyError: when the config cannot be read.
    """
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PolicyError(f"cannot read {path}: {exc}") from exc
    licenses: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line[:1].isspace():
            inside = stripped.split(":", 1)[0].strip() == "allow_licenses"
            continue
        if inside and stripped.startswith("-"):
            value = stripped[1:].strip().strip("'\"")
            if value:
                licenses.append(value)
    return tuple(licenses)


def _load_source_policy(path: Path) -> SourcePolicy:
    data = _load_toml(path)
    registries = _string_list(data.get("allowed_registries"), f"{path}.allowed_registries")
    if not registries:
        raise PolicyError(f"{path}: at least one allowed registry is required")
    raw_majors = _table(data.get("reviewed_majors", {}), f"{path}.reviewed_majors")
    majors: dict[str, frozenset[int]] = {}
    for package, values in raw_majors.items():
        if not isinstance(values, list) or not all(
            isinstance(value, int) and not isinstance(value, bool) for value in values
        ):
            raise PolicyError(f"{path}.reviewed_majors.{package}: expected integer major versions")
        majors[canonical_name(package)] = frozenset(int(value) for value in values)
    return SourcePolicy(
        allowed_registries=registries,
        allow_vcs=_require_bool(data, "allow_vcs", str(path)),
        allow_url=_require_bool(data, "allow_url", str(path)),
        reviewed_majors=majors,
    )


def _load_inventory(path: Path) -> DependencyInventory:
    data = _load_toml(path)
    try:
        purposes = string_map(data, "purpose", str(path))
        owners = string_map(data, "owner", str(path))
    except TomlError as exc:
        raise PolicyError(str(exc)) from exc
    if not purposes:
        raise PolicyError(f"{path}: 'purpose' must document at least one dependency")
    missing_owners = sorted(set(purposes) - set(owners))
    if missing_owners:
        raise PolicyError(f"{path}: no owner recorded for: {', '.join(missing_owners)}")
    return DependencyInventory(
        purposes={canonical_name(name): value for name, value in purposes.items()},
        owners={canonical_name(name): value for name, value in owners.items()},
    )


def load_policy(root: Path = Path(".")) -> DependencyPolicy:
    """Load all Stage 09 policies from ``root``.

    Raises:
        PolicyError: when any policy file is missing or invalid.
    """
    base = root / POLICY_DIRECTORY
    return DependencyPolicy(
        exceptions=_load_exceptions(base / "vulnerability-exceptions.toml"),
        licenses=_load_license_policy(base / "license-policy.toml"),
        sources=_load_source_policy(base / "source-policy.toml"),
        inventory=_load_inventory(base / "dependency-inventory.toml"),
    )
