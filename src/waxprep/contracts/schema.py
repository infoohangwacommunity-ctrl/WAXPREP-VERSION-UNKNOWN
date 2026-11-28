"""Deterministic JSON Schema generation and publication (Stage 17).

Every registered contract has one stable identity and one generated JSON Schema
(Draft 2020-12). Schemas are sorted and serialized deterministically so a diff
shows a real contract change, not dictionary ordering noise. Historical schema
files are never overwritten: a version bump adds a new file.

The committed baseline lives in ``contracts/schemas/``. CI runs the drift check,
so changing a model without publishing its schema fails the gate.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from waxprep.contracts.errors import ContractViolationError
from waxprep.contracts.models.result import ErrorDetail, OperationResult
from waxprep.contracts.versioning import ContractIdentity, ContractVersion

SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True, slots=True)
class SchemaEntry:
    identity: ContractIdentity
    adapter: TypeAdapter[Any]

    @property
    def filename(self) -> str:
        return f"{self.identity.name}@{self.identity.version}.schema.json"


@dataclass(frozen=True, slots=True)
class DriftReport:
    missing: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.missing and not self.changed


@dataclass(slots=True)
class ContractSchemaRegistry:
    """One authoritative schema registry for the current contract revisions."""

    _entries: dict[str, SchemaEntry] = field(default_factory=dict)

    def register(
        self,
        identity: ContractIdentity,
        contract: type[BaseModel] | TypeAdapter[Any],
    ) -> None:
        if identity.name in self._entries:
            raise ContractViolationError(
                "A contract with this name is already registered",
                context={"contract": identity.name},
            )
        adapter = contract if isinstance(contract, TypeAdapter) else TypeAdapter(contract)
        self._entries[identity.name] = SchemaEntry(identity=identity, adapter=adapter)

    def entry(self, name: str) -> SchemaEntry:
        try:
            return self._entries[name]
        except KeyError as exc:
            raise ContractViolationError(
                "Unknown contract identity",
                context={"contract": name},
            ) from exc

    def identities(self) -> tuple[ContractIdentity, ...]:
        return tuple(
            entry.identity
            for entry in sorted(self._entries.values(), key=lambda item: item.identity.name)
        )

    def schema_for(self, name: str) -> dict[str, Any]:
        entry = self.entry(name)
        schema = copy.deepcopy(entry.adapter.json_schema())
        schema["$schema"] = SCHEMA_DIALECT
        schema["$id"] = entry.identity.urn
        return schema

    def manifest(self) -> dict[str, Any]:
        return {
            "schema_dialect": SCHEMA_DIALECT,
            "contracts": [
                {
                    "name": entry.identity.name,
                    "version": str(entry.identity.version),
                    "id": entry.identity.urn,
                    "file": entry.filename,
                }
                for entry in sorted(self._entries.values(), key=lambda item: item.identity.name)
            ],
        }

    def documents(self) -> dict[str, str]:
        documents = {
            entry.filename: canonical_json(self.schema_for(entry.identity.name))
            for entry in self._entries.values()
        }
        documents[MANIFEST_FILENAME] = canonical_json(self.manifest())
        return dict(sorted(documents.items()))

    def write_to(self, directory: Path) -> tuple[Path, ...]:
        directory.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        for name, text in self.documents().items():
            path = directory / name
            path.write_text(text, encoding="utf-8")
            paths.append(path)
        return tuple(paths)

    def check_drift(self, directory: Path) -> DriftReport:
        missing: list[str] = []
        changed: list[str] = []
        for name, expected in self.documents().items():
            path = directory / name
            if not path.is_file():
                missing.append(name)
                continue
            if path.read_text(encoding="utf-8") != expected:
                changed.append(name)
        return DriftReport(tuple(missing), tuple(changed))


def canonical_json(value: Any) -> str:
    """Return deterministic, human-reviewable JSON text."""
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load_schema(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractViolationError(
            "Contract schema could not be loaded",
            context={"file": path.name},
        ) from exc
    if not isinstance(value, dict):
        raise ContractViolationError(
            "Contract schema must be a JSON object",
            context={"file": path.name},
        )
    return value


def build_default_registry() -> ContractSchemaRegistry:
    """Register the foundational contracts that exist today."""
    registry = ContractSchemaRegistry()
    registry.register(
        ContractIdentity(name="waxprep.error.detail", version=ContractVersion(1, 0, 0)),
        ErrorDetail,
    )
    registry.register(
        ContractIdentity(name="waxprep.operation.result", version=ContractVersion(1, 0, 0)),
        OperationResult,
    )
    return registry
