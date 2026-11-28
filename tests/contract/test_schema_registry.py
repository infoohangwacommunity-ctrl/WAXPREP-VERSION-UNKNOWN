"""Stage 17 — deterministic schema publication, registry and drift detection."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from waxprep.contracts.errors import ContractViolationError
from waxprep.contracts.models.result import (
    ErrorDetail,
    OperationResult,
    OperationStatus,
    OperationSuccess,
)
from waxprep.contracts.schema import (
    MANIFEST_FILENAME,
    SCHEMA_DIALECT,
    ContractSchemaRegistry,
    build_default_registry,
    canonical_json,
    load_schema,
)
from waxprep.contracts.versioning import ContractIdentity, ContractVersion

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def identity(name: str = "waxprep.operation.result") -> ContractIdentity:
    return ContractIdentity(name=name, version=ContractVersion(1, 0, 0))


class TestRegistry:
    def test_register_and_schema(self):
        registry = ContractSchemaRegistry()
        registry.register(identity(), OperationResult)
        schema = registry.schema_for("waxprep.operation.result")
        assert schema["$schema"] == SCHEMA_DIALECT
        assert schema["$id"] == "urn:waxprep:contract:waxprep.operation.result:1.0.0"
        assert registry.identities() == (identity(),)

    def test_register_accepts_type_adapter(self):
        from pydantic import TypeAdapter

        registry = ContractSchemaRegistry()
        registry.register(identity(), TypeAdapter(OperationResult))
        assert "oneOf" in registry.schema_for("waxprep.operation.result")

    def test_duplicate_name_rejected(self):
        registry = ContractSchemaRegistry()
        registry.register(identity(), OperationResult)
        with pytest.raises(ContractViolationError, match="already registered"):
            registry.register(identity(), ErrorDetail)

    def test_unknown_contract_rejected(self):
        with pytest.raises(ContractViolationError, match="Unknown contract"):
            ContractSchemaRegistry().entry("missing")

    def test_identities_are_sorted(self):
        registry = ContractSchemaRegistry()
        registry.register(identity("waxprep.z"), OperationResult)
        registry.register(identity("waxprep.a"), OperationResult)
        assert [item.name for item in registry.identities()] == ["waxprep.a", "waxprep.z"]

    def test_manifest_is_sorted_and_typed(self):
        registry = build_default_registry()
        manifest = registry.manifest()
        assert manifest["schema_dialect"] == SCHEMA_DIALECT
        assert [item["name"] for item in manifest["contracts"]] == [
            "waxprep.error.detail",
            "waxprep.operation.result",
        ]
        assert all(item["file"].endswith(".schema.json") for item in manifest["contracts"])

    def test_documents_are_deterministic(self):
        registry = build_default_registry()
        assert registry.documents() == registry.documents()
        assert list(registry.documents()) == sorted(registry.documents())

    def test_write_and_check_drift(self, tmp_path: Path):
        registry = build_default_registry()
        paths = registry.write_to(tmp_path)
        assert all(path.is_file() for path in paths)
        assert registry.check_drift(tmp_path).ok is True

    def test_drift_detects_missing_and_changed(self, tmp_path: Path):
        registry = build_default_registry()
        registry.write_to(tmp_path)
        (tmp_path / MANIFEST_FILENAME).unlink()
        schema_file = next(
            path
            for path in tmp_path.iterdir()
            if path.suffix == ".json" and path.name != MANIFEST_FILENAME
        )
        schema_file.write_text("{}\n", encoding="utf-8")

        report = registry.check_drift(tmp_path)
        assert report.ok is False
        assert MANIFEST_FILENAME in report.missing
        assert schema_file.name in report.changed

    def test_committed_schemas_are_current(self):
        report = build_default_registry().check_drift(PROJECT_ROOT / "contracts" / "schemas")
        assert report.ok is True, (report.missing, report.changed)


class TestCanonicalJson:
    def test_sorted_and_newline_terminated(self):
        text = canonical_json({"b": 1, "a": 2})
        assert text == '{\n  "a": 2,\n  "b": 1\n}\n'

    def test_unicode_is_preserved(self):
        assert "é" in canonical_json({"value": "é"})


class TestLoadSchema:
    def test_loads_object(self, tmp_path: Path):
        path = tmp_path / "schema.json"
        path.write_text('{"type":"object"}', encoding="utf-8")
        assert load_schema(path) == {"type": "object"}

    def test_invalid_json_rejected(self, tmp_path: Path):
        path = tmp_path / "schema.json"
        path.write_text("{", encoding="utf-8")
        with pytest.raises(ContractViolationError, match="could not be loaded"):
            load_schema(path)

    def test_non_object_rejected(self, tmp_path: Path):
        path = tmp_path / "schema.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(ContractViolationError, match="JSON object"):
            load_schema(path)

    def test_missing_file_rejected(self, tmp_path: Path):
        with pytest.raises(ContractViolationError, match="could not be loaded"):
            load_schema(tmp_path / "missing.json")


class TestDiscriminatorSchema:
    def test_every_variant_requires_status(self):
        schema = build_default_registry().schema_for("waxprep.operation.result")
        expected = {
            "OperationSuccess": "success",
            "OperationFailure": "failed",
            "OperationRejected": "rejected",
            "OperationDeferred": "deferred",
        }
        for variant, discriminator in expected.items():
            definition = schema["$defs"][variant]
            assert "status" in definition["required"]
            assert definition["properties"]["status"]["const"] == discriminator

    def test_pydantic_agrees_with_the_required_discriminator(self):
        from pydantic import ValidationError

        from waxprep.contracts.models.result import OperationResult

        with pytest.raises(ValidationError):
            OperationResult.model_validate({"detail": "missing status"})


class TestDefaultRegistry:
    def test_foundational_contracts(self):
        identities = {item.name: item.version for item in build_default_registry().identities()}
        assert identities == {
            "waxprep.error.detail": ContractVersion(1, 0, 0),
            "waxprep.operation.result": ContractVersion(1, 0, 0),
        }

    def test_schema_files_are_valid_json(self):
        directory = PROJECT_ROOT / "contracts" / "schemas"
        for path in directory.glob("*.json"):
            assert isinstance(json.loads(path.read_text(encoding="utf-8")), dict)

    def test_dump_is_stable(self):
        registry = build_default_registry()
        assert registry.documents() == registry.documents()
        assert OperationSuccess(status=OperationStatus.SUCCESS, detail="ok").detail == "ok"
