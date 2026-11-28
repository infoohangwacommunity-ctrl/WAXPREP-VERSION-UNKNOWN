"""Automatic compatibility enforcement against a published baseline (Stage 17).

The drift check proves the committed schema matches the current model. This
module proves a proposed contract did not silently rewrite or break a previously
published version:

* same version + changed schema -> forbidden unless an explicit exception exists;
* newer version -> classified against the previous baseline schema;
* breaking change -> requires a major version increment;
* conditional change -> requires an explicit decision entry;
* contract removal or version regression -> forbidden unless explicitly decided;
* new contract -> a compatible addition.

The result is machine-readable and is written to the CI evidence directory.
"""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from waxprep.contracts.errors import ContractViolationError
from waxprep.contracts.schema import (
    ContractSchemaRegistry,
    canonical_json,
    load_schema,
)
from waxprep.contracts.versioning import (
    Compatibility,
    ContractIdentity,
    ContractVersion,
    InvalidContractVersionError,
    SchemaChange,
    VersionBump,
    compare_schemas,
)

BASELINE_MANIFEST = "manifest.json"
DECISIONS_TABLE = "decisions"


@dataclass(frozen=True, slots=True)
class EnforcementFinding:
    contract: str
    status: Compatibility
    allowed: bool
    message: str
    previous_version: str | None = None
    current_version: str | None = None
    recommended_bump: VersionBump | None = None
    changes: tuple[SchemaChange, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "status": self.status.value,
            "allowed": self.allowed,
            "message": self.message,
            "previous_version": self.previous_version,
            "current_version": self.current_version,
            "recommended_bump": (
                self.recommended_bump.value if self.recommended_bump is not None else None
            ),
            "changes": [
                {
                    "path": change.path,
                    "change": change.change.value,
                    "compatibility": change.compatibility.value,
                }
                for change in self.changes
            ],
        }


@dataclass(frozen=True, slots=True)
class EnforcementReport:
    findings: tuple[EnforcementFinding, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return all(finding.allowed for finding in self.findings)

    @property
    def violations(self) -> tuple[EnforcementFinding, ...]:
        return tuple(finding for finding in self.findings if not finding.allowed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(canonical_json(self.to_dict()), encoding="utf-8")


def load_decisions(path: Path | None) -> dict[str, str]:
    """Load explicit compatibility decisions keyed by contract or identity."""
    if path is None or not path.is_file():
        return {}
    try:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ContractViolationError(
            "Compatibility decisions file could not be loaded",
            context={"file": path.name},
        ) from exc
    decisions = document.get(DECISIONS_TABLE, {})
    if not isinstance(decisions, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in decisions.items()
    ):
        raise ContractViolationError(
            "Compatibility decisions must be a string-to-string table",
            context={"file": path.name},
        )
    return {str(key): str(value) for key, value in decisions.items()}


def _baseline_entries(directory: Path) -> dict[str, tuple[ContractIdentity, dict[str, Any]]]:
    manifest_path = directory / BASELINE_MANIFEST
    if not manifest_path.is_file():
        raise ContractViolationError(
            "Published contract baseline manifest is missing",
            context={"directory": str(directory)},
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        contracts = manifest.get("contracts")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ContractViolationError(
            "Published contract baseline manifest is invalid",
            context={"directory": str(directory)},
        ) from exc
    if not isinstance(contracts, list):
        raise ContractViolationError(
            "Published contract baseline manifest has no contract list",
            context={"directory": str(directory)},
        )

    entries: dict[str, tuple[ContractIdentity, dict[str, Any]]] = {}
    for item in contracts:
        if not isinstance(item, dict):
            raise ContractViolationError("Baseline contract entry must be an object")
        try:
            name = str(item["name"])
            version = ContractVersion.parse(str(item["version"]))
            filename = str(item["file"])
        except (KeyError, InvalidContractVersionError) as exc:
            raise ContractViolationError("Baseline contract entry is malformed") from exc
        if name in entries:
            raise ContractViolationError(
                "Baseline contains duplicate contract versions",
                context={"contract": name},
            )
        entries[name] = (
            ContractIdentity(name=name, version=version),
            load_schema(directory / filename),
        )
    return entries


def _decision(decisions: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        if key in decisions:
            return decisions[key]
    return None


def enforce_compatibility(
    registry: ContractSchemaRegistry,
    baseline_directory: Path,
    *,
    decisions_path: Path | None = None,
) -> EnforcementReport:
    """Compare the current registry with the previously published baseline."""
    baseline = _baseline_entries(baseline_directory)
    decisions = load_decisions(decisions_path)
    current = {identity.name: identity for identity in registry.identities()}

    findings: list[EnforcementFinding] = []
    for name in sorted(set(current) | set(baseline)):
        if name not in baseline:
            identity = current[name]
            findings.append(
                EnforcementFinding(
                    contract=name,
                    status=Compatibility.COMPATIBLE,
                    allowed=True,
                    message="New contract; compatible addition",
                    current_version=str(identity.version),
                )
            )
            continue

        previous_identity, previous_schema = baseline[name]
        if name not in current:
            decision = _decision(
                decisions,
                name,
                f"{name}@{previous_identity.version}",
            )
            findings.append(
                EnforcementFinding(
                    contract=name,
                    status=Compatibility.BREAKING,
                    allowed=decision is not None,
                    message=(
                        "Contract removed with an explicit decision"
                        if decision is not None
                        else "Contract removed without an explicit decision"
                    ),
                    previous_version=str(previous_identity.version),
                )
            )
            continue

        current_identity = current[name]
        current_schema = registry.schema_for(name)
        if current_identity.version < previous_identity.version:
            findings.append(
                EnforcementFinding(
                    contract=name,
                    status=Compatibility.BREAKING,
                    allowed=False,
                    message="Contract version regressed below the published baseline",
                    previous_version=str(previous_identity.version),
                    current_version=str(current_identity.version),
                )
            )
            continue
        if current_identity.version == previous_identity.version:
            if previous_schema == current_schema:
                findings.append(
                    EnforcementFinding(
                        contract=name,
                        status=Compatibility.COMPATIBLE,
                        allowed=True,
                        message="Published contract is unchanged",
                        previous_version=str(previous_identity.version),
                        current_version=str(current_identity.version),
                    )
                )
                continue
            decision = _decision(
                decisions,
                f"{name}@{current_identity.version}",
            )
            findings.append(
                EnforcementFinding(
                    contract=name,
                    status=Compatibility.BREAKING,
                    allowed=decision is not None,
                    message=(
                        "Published version modified with an explicit exception"
                        if decision is not None
                        else "Published version modified; publish a new version instead"
                    ),
                    previous_version=str(previous_identity.version),
                    current_version=str(current_identity.version),
                    recommended_bump=VersionBump.MAJOR,
                )
            )
            continue

        comparison = compare_schemas(previous_schema, current_schema)
        if comparison.classification is Compatibility.COMPATIBLE:
            findings.append(
                EnforcementFinding(
                    contract=name,
                    status=Compatibility.COMPATIBLE,
                    allowed=True,
                    message="Changes are structurally compatible",
                    previous_version=str(previous_identity.version),
                    current_version=str(current_identity.version),
                    recommended_bump=comparison.recommended_bump,
                    changes=comparison.changes,
                )
            )
            continue
        if comparison.classification is Compatibility.CONDITIONAL:
            decision = _decision(
                decisions,
                f"{name}@{current_identity.version}",
            )
            findings.append(
                EnforcementFinding(
                    contract=name,
                    status=Compatibility.CONDITIONAL,
                    allowed=decision is not None,
                    message=(
                        "Conditional change has an explicit decision"
                        if decision is not None
                        else "Conditional change requires an explicit decision"
                    ),
                    previous_version=str(previous_identity.version),
                    current_version=str(current_identity.version),
                    recommended_bump=comparison.recommended_bump,
                    changes=comparison.changes,
                )
            )
            continue

        major_bump = current_identity.version.major > previous_identity.version.major
        findings.append(
            EnforcementFinding(
                contract=name,
                status=Compatibility.BREAKING,
                allowed=major_bump,
                message=(
                    "Breaking change has a major version increment"
                    if major_bump
                    else "Breaking change requires a major version increment"
                ),
                previous_version=str(previous_identity.version),
                current_version=str(current_identity.version),
                recommended_bump=comparison.recommended_bump,
                changes=comparison.changes,
            )
        )

    return EnforcementReport(tuple(findings))
