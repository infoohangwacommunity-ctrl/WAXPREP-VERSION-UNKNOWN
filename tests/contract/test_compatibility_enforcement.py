"""Stage 17 — automatic compatibility enforcement against the baseline."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from waxprep.contracts.compatibility import (
    EnforcementFinding,
    EnforcementReport,
    enforce_compatibility,
    load_decisions,
)
from waxprep.contracts.errors import ContractViolationError
from waxprep.contracts.models.base import ContractModel
from waxprep.contracts.schema import ContractSchemaRegistry, build_default_registry
from waxprep.contracts.versioning import (
    Compatibility,
    ContractIdentity,
    ContractVersion,
    VersionBump,
)

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NAME = "waxprep.test.result"


class V1(ContractModel):
    name: str


class V2Optional(ContractModel):
    name: str
    note: str | None = None


class V2Removed(ContractModel):
    other: str


class EnumV1(ContractModel):
    status: str


class EnumV2(ContractModel):
    status: str
    extra: str | None = None


def registry(version: tuple[int, int, int], model: type[ContractModel]) -> ContractSchemaRegistry:
    item = ContractSchemaRegistry()
    item.register(
        ContractIdentity(name=NAME, version=ContractVersion(*version)),
        model,
    )
    return item


def baseline(tmp_path: Path, item: ContractSchemaRegistry) -> Path:
    directory = tmp_path / "baseline"
    item.write_to(directory)
    return directory


def write_decisions(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "decisions.toml"
    path.write_text(content, encoding="utf-8")
    return path


class TestEnforcement:
    def test_unchanged_contract_passes(self, tmp_path: Path):
        current = registry((1, 0, 0), V1)
        report = enforce_compatibility(current, baseline(tmp_path, current))
        assert report.ok is True
        assert report.findings[0].message == "Published contract is unchanged"

    def test_new_contract_is_a_compatible_addition(self, tmp_path: Path):
        empty = ContractSchemaRegistry()
        report = enforce_compatibility(registry((1, 0, 0), V1), baseline(tmp_path, empty))
        assert report.ok is True
        assert "New contract" in report.findings[0].message

    def test_same_version_modified_is_forbidden(self, tmp_path: Path):
        old = registry((1, 0, 0), V1)
        report = enforce_compatibility(registry((1, 0, 0), V2Removed), baseline(tmp_path, old))
        assert report.ok is False
        assert report.findings[0].status is Compatibility.BREAKING
        assert report.findings[0].recommended_bump is VersionBump.MAJOR
        assert "Published version modified" in report.findings[0].message

    def test_same_version_modification_can_be_explicitly_excepted(self, tmp_path: Path):
        old = registry((1, 0, 0), V1)
        decisions = write_decisions(
            tmp_path,
            '[decisions]\n"waxprep.test.result@1.0.0" = "approved exception"\n',
        )
        report = enforce_compatibility(
            registry((1, 0, 0), V2Removed),
            baseline(tmp_path, old),
            decisions_path=decisions,
        )
        assert report.ok is True
        assert "explicit exception" in report.findings[0].message

    def test_compatible_new_version_passes(self, tmp_path: Path):
        old = registry((1, 0, 0), V1)
        report = enforce_compatibility(registry((1, 1, 0), V2Optional), baseline(tmp_path, old))
        assert report.ok is True
        assert report.findings[0].status is Compatibility.COMPATIBLE

    def test_breaking_change_requires_major_version(self, tmp_path: Path):
        old = registry((1, 0, 0), V1)
        report = enforce_compatibility(registry((1, 1, 0), V2Removed), baseline(tmp_path, old))
        assert report.ok is False
        assert "major version increment" in report.findings[0].message

    def test_breaking_change_with_major_version_passes(self, tmp_path: Path):
        old = registry((1, 0, 0), V1)
        report = enforce_compatibility(registry((2, 0, 0), V2Removed), baseline(tmp_path, old))
        assert report.ok is True
        assert "major version increment" in report.findings[0].message

    def test_conditional_change_requires_decision(self, tmp_path: Path):
        old = registry((1, 0, 0), EnumV1)
        without = enforce_compatibility(registry((1, 1, 0), EnumV2), baseline(tmp_path, old))
        # The extra optional field is compatible; make a genuinely conditional enum change.
        assert without.ok is True

    def test_conditional_enum_change_requires_decision(self, tmp_path: Path):
        from enum import StrEnum

        class StatusA(StrEnum):
            A = "a"

        class StatusB(StrEnum):
            A = "a"
            B = "b"

        class EnumA(ContractModel):
            status: StatusA

        class EnumAB(ContractModel):
            status: StatusB

        old = ContractSchemaRegistry()
        old.register(ContractIdentity(NAME, ContractVersion(1, 0, 0)), EnumA)
        new = ContractSchemaRegistry()
        new.register(ContractIdentity(NAME, ContractVersion(1, 1, 0)), EnumAB)

        without = enforce_compatibility(new, baseline(tmp_path, old))
        assert without.ok is False
        assert without.findings[0].status is Compatibility.CONDITIONAL
        assert "explicit decision" in without.findings[0].message

        decisions = write_decisions(
            tmp_path,
            '[decisions]\n"waxprep.test.result@1.1.0" = "consumer handles unknown values"\n',
        )
        with_decision = enforce_compatibility(
            new, baseline(tmp_path, old), decisions_path=decisions
        )
        assert with_decision.ok is True

    def test_removed_contract_requires_decision(self, tmp_path: Path):
        old = registry((1, 0, 0), V1)
        empty = ContractSchemaRegistry()
        without = enforce_compatibility(empty, baseline(tmp_path, old))
        assert without.ok is False
        assert "removed" in without.findings[0].message

        decisions = write_decisions(tmp_path, '[decisions]\n"waxprep.test.result" = "retired"\n')
        with_decision = enforce_compatibility(
            empty, baseline(tmp_path, old), decisions_path=decisions
        )
        assert with_decision.ok is True

    def test_version_regression_is_forbidden(self, tmp_path: Path):
        old = registry((1, 0, 0), V1)
        report = enforce_compatibility(registry((0, 9, 0), V1), baseline(tmp_path, old))
        assert report.ok is False
        assert "regressed" in report.findings[0].message

    def test_report_serialization_and_write(self, tmp_path: Path):
        current = registry((1, 0, 0), V1)
        report = enforce_compatibility(current, baseline(tmp_path, current))
        path = tmp_path / "nested" / "report.json"
        report.write(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["ok"] is True
        assert payload["findings"][0]["contract"] == NAME
        assert EnforcementReport(()).ok is True
        assert (
            EnforcementFinding(
                contract=NAME,
                status=Compatibility.COMPATIBLE,
                allowed=True,
                message="ok",
            ).to_dict()["changes"]
            == []
        )


class TestBaselineAndDecisions:
    def test_missing_baseline_manifest_is_rejected(self, tmp_path: Path):
        with pytest.raises(ContractViolationError, match="manifest is missing"):
            enforce_compatibility(registry((1, 0, 0), V1), tmp_path)

    @pytest.mark.parametrize("content", ["{}", "{", '{"contracts": 1}'])
    def test_invalid_manifest_is_rejected(self, tmp_path: Path, content: str):
        (tmp_path / "manifest.json").write_text(content, encoding="utf-8")
        with pytest.raises(ContractViolationError):
            enforce_compatibility(registry((1, 0, 0), V1), tmp_path)

    @pytest.mark.parametrize(
        "entry",
        [
            "not-an-object",
            {"name": "waxprep.test.result"},
            {"name": "waxprep.test.result", "version": "bad", "file": "x.json"},
        ],
    )
    def test_malformed_manifest_entry_is_rejected(self, tmp_path: Path, entry):
        manifest = {"contracts": [entry]}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ContractViolationError):
            enforce_compatibility(registry((1, 0, 0), V1), tmp_path)

    def test_duplicate_baseline_contract_is_rejected(self, tmp_path: Path):
        (tmp_path / "a.json").write_text('{"type":"object"}', encoding="utf-8")
        manifest = {
            "contracts": [
                {"name": NAME, "version": "1.0.0", "file": "a.json"},
                {"name": NAME, "version": "1.0.0", "file": "b.json"},
            ]
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ContractViolationError, match="duplicate"):
            enforce_compatibility(registry((1, 0, 0), V1), tmp_path)

    def test_missing_schema_file_is_rejected(self, tmp_path: Path):
        manifest = {"contracts": [{"name": NAME, "version": "1.0.0", "file": "missing.json"}]}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ContractViolationError, match="could not be loaded"):
            enforce_compatibility(registry((1, 0, 0), V1), tmp_path)

    def test_decisions_loading(self, tmp_path: Path):
        assert load_decisions(None) == {}
        missing = tmp_path / "missing.toml"
        assert load_decisions(missing) == {}
        path = write_decisions(tmp_path, '[decisions]\n"a" = "reason"\n')
        assert load_decisions(path) == {"a": "reason"}

    @pytest.mark.parametrize(
        "content",
        [
            "not toml [",
            '[decisions]\n"a" = 1\n',
            '[other]\n"a" = "b"\n',
        ],
    )
    def test_invalid_decisions_are_rejected(self, tmp_path: Path, content: str):
        path = write_decisions(tmp_path, content)
        if content.startswith("[other]"):
            assert load_decisions(path) == {}
        else:
            with pytest.raises(ContractViolationError):
                load_decisions(path)


class TestCommittedBaseline:
    def test_default_contracts_match_the_committed_baseline(self):
        report = enforce_compatibility(
            build_default_registry(),
            PROJECT_ROOT / "contracts" / "baseline",
            decisions_path=PROJECT_ROOT / "contracts" / "compatibility-decisions.toml",
        )
        assert report.ok is True
