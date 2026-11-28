"""Stage 17 — contract identity, versions and compatibility policy."""

from __future__ import annotations

import pytest

from waxprep.contracts.versioning import (
    ChangeType,
    Compatibility,
    CompatibilityReport,
    ContractIdentity,
    ContractVersion,
    InvalidContractVersionError,
    SchemaChange,
    VersionBump,
    classify_change,
    compare_schemas,
)

pytestmark = pytest.mark.contract


class TestContractVersion:
    def test_parse_and_str(self):
        version = ContractVersion.parse("1.2.3")
        assert version == ContractVersion(1, 2, 3)
        assert str(version) == "1.2.3"

    def test_ordering_and_bumps(self):
        assert ContractVersion(1, 2, 3) < ContractVersion(2, 0, 0)
        assert ContractVersion(1, 2, 3).bump_major() == ContractVersion(2, 0, 0)
        assert ContractVersion(1, 2, 3).bump_minor() == ContractVersion(1, 3, 0)
        assert ContractVersion(1, 2, 3).bump_patch() == ContractVersion(1, 2, 4)

    @pytest.mark.parametrize("value", ["", "1", "1.2", "1.2.3.4", "01.2.3", "v1.2.3", "1.2.-3"])
    def test_invalid_versions_rejected(self, value):
        with pytest.raises(InvalidContractVersionError):
            ContractVersion.parse(value)

    def test_negative_components_rejected(self):
        with pytest.raises(InvalidContractVersionError):
            ContractVersion(-1, 0, 0)


class TestContractIdentity:
    def test_parse_str_and_urn(self):
        identity = ContractIdentity.parse("waxprep.notebook.lookup.request@1.0.0")
        assert identity.name == "waxprep.notebook.lookup.request"
        assert str(identity) == "waxprep.notebook.lookup.request@1.0.0"
        assert identity.urn == "urn:waxprep:contract:waxprep.notebook.lookup.request:1.0.0"

    @pytest.mark.parametrize(
        "value",
        ["", "no-version", "waxprep@1.0.0", "WaxPrep.name@1.0.0", "waxprep..name@1.0.0"],
    )
    def test_invalid_identity_rejected(self, value):
        with pytest.raises(InvalidContractVersionError):
            ContractIdentity.parse(value)


class TestChangePolicy:
    @pytest.mark.parametrize(
        ("change", "expected"),
        [
            (ChangeType.NONE, Compatibility.COMPATIBLE),
            (ChangeType.ADD_OPTIONAL_FIELD, Compatibility.COMPATIBLE),
            (ChangeType.ADD_REQUIRED_FIELD, Compatibility.BREAKING),
            (ChangeType.REQUIRED_FIELD_OPTIONAL, Compatibility.CONDITIONAL),
            (ChangeType.REMOVE_FIELD, Compatibility.BREAKING),
            (ChangeType.TYPE_CHANGE, Compatibility.BREAKING),
            (ChangeType.ENUM_VALUE_ADDED, Compatibility.CONDITIONAL),
            (ChangeType.ENUM_VALUE_REMOVED, Compatibility.BREAKING),
            (ChangeType.VALIDATION_RESTRICTED, Compatibility.BREAKING),
            (ChangeType.VALIDATION_RELAXED, Compatibility.CONDITIONAL),
            (ChangeType.ADDITIONAL_PROPERTIES_RELAXED, Compatibility.CONDITIONAL),
            (ChangeType.ADDITIONAL_PROPERTIES_RESTRICTED, Compatibility.BREAKING),
            (ChangeType.VARIANT_ADDED, Compatibility.CONDITIONAL),
            (ChangeType.VARIANT_REMOVED, Compatibility.BREAKING),
            (ChangeType.SEMANTIC_CHANGE, Compatibility.BREAKING),
            (ChangeType.SERIALIZATION_CHANGE, Compatibility.BREAKING),
        ],
    )
    def test_policy_table(self, change, expected):
        assert classify_change(change) is expected

    def test_report_classification_and_bump(self):
        assert CompatibilityReport(()).classification is Compatibility.COMPATIBLE
        assert CompatibilityReport(()).recommended_bump is VersionBump.PATCH
        conditional = CompatibilityReport((SchemaChange("$", ChangeType.ADD_OPTIONAL_FIELD, "x"),))
        assert conditional.classification is Compatibility.COMPATIBLE
        assert conditional.recommended_bump is VersionBump.PATCH
        assert SchemaChange("$", ChangeType.ENUM_VALUE_ADDED, "x").compatibility is (
            Compatibility.CONDITIONAL
        )
        conditional = CompatibilityReport((SchemaChange("$", ChangeType.ENUM_VALUE_ADDED, "x"),))
        assert conditional.classification is Compatibility.CONDITIONAL
        assert conditional.compatible is True
        assert conditional.recommended_bump is VersionBump.MINOR
        breaking = CompatibilityReport((SchemaChange("$", ChangeType.REMOVE_FIELD, "x"),))
        assert breaking.classification is Compatibility.BREAKING
        assert breaking.compatible is False
        assert breaking.recommended_bump is VersionBump.MAJOR


def object_schema(**extra):
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
        "additionalProperties": False,
    }
    schema.update(extra)
    return schema


class TestCompareSchemas:
    def test_identical_is_compatible(self):
        report = compare_schemas(object_schema(), object_schema())
        assert report.changes == ()
        assert report.classification is Compatibility.COMPATIBLE

    def test_added_optional_field(self):
        schema = object_schema()
        schema["properties"]["note"] = {"type": "string"}
        report = compare_schemas(object_schema(), schema)
        assert [change.change for change in report.changes] == [ChangeType.ADD_OPTIONAL_FIELD]

    def test_added_required_field_is_breaking(self):
        schema = object_schema()
        schema["properties"]["note"] = {"type": "string"}
        schema["required"] = ["name", "note"]
        report = compare_schemas(object_schema(), schema)
        assert ChangeType.ADD_REQUIRED_FIELD in {change.change for change in report.changes}
        assert report.classification is Compatibility.BREAKING

    def test_existing_field_becomes_required(self):
        old = object_schema()
        old["properties"]["note"] = {"type": "string"}
        new = object_schema()
        new["properties"]["note"] = {"type": "string"}
        new["required"] = ["name", "note"]
        report = compare_schemas(old, new)
        assert ChangeType.ADD_REQUIRED_FIELD in {change.change for change in report.changes}

    def test_required_becomes_optional(self):
        old = object_schema()
        new = object_schema()
        new["required"] = []
        report = compare_schemas(old, new)
        assert [change.change for change in report.changes] == [ChangeType.REQUIRED_FIELD_OPTIONAL]
        assert report.classification is Compatibility.CONDITIONAL

    def test_removed_field_is_breaking(self):
        old = object_schema()
        old["properties"]["note"] = {"type": "string"}
        report = compare_schemas(old, object_schema())
        assert [change.change for change in report.changes] == [ChangeType.REMOVE_FIELD]
        assert report.classification is Compatibility.BREAKING

    def test_type_change(self):
        new = object_schema()
        new["properties"]["name"] = {"type": "integer"}
        report = compare_schemas(object_schema(), new)
        assert ChangeType.TYPE_CHANGE in {change.change for change in report.changes}

    def test_enum_values(self):
        old = {"type": "string", "enum": ["a", "b"]}
        new = {"type": "string", "enum": ["b", "c"]}
        changes = {change.change for change in compare_schemas(old, new).changes}
        assert changes == {ChangeType.ENUM_VALUE_REMOVED, ChangeType.ENUM_VALUE_ADDED}

    def test_enum_added_only(self):
        old = {"type": "string", "enum": ["a"]}
        new = {"type": "string", "enum": ["a", "b"]}
        assert [change.change for change in compare_schemas(old, new).changes] == [
            ChangeType.ENUM_VALUE_ADDED
        ]

    def test_const_change(self):
        old = {"type": "string", "const": "a"}
        new = {"type": "string", "const": "b"}
        assert [change.change for change in compare_schemas(old, new).changes] == [
            ChangeType.ENUM_VALUE_REMOVED
        ]

    def test_equal_const_and_enum_are_unchanged(self):
        assert compare_schemas({"const": "a"}, {"const": "a"}).changes == ()
        assert (
            compare_schemas(
                {"type": "string", "enum": ["a"]}, {"type": "string", "enum": ["a"]}
            ).changes
            == ()
        )

    def test_bounds_added(self):
        old = {}
        new = {"minLength": 2}
        assert [change.change for change in compare_schemas(old, new).changes] == [
            ChangeType.VALIDATION_RESTRICTED
        ]
        assert [change.change for change in compare_schemas({}, {"maxLength": 5}).changes] == [
            ChangeType.VALIDATION_RELAXED
        ]

    def test_bounds_removed(self):
        assert [change.change for change in compare_schemas({"minLength": 2}, {}).changes] == [
            ChangeType.VALIDATION_RELAXED
        ]
        assert [change.change for change in compare_schemas({"maxLength": 5}, {}).changes] == [
            ChangeType.VALIDATION_RESTRICTED
        ]

    def test_bounds_tightened_and_relaxed(self):
        assert [
            change.change for change in compare_schemas({"minLength": 2}, {"minLength": 3}).changes
        ] == [ChangeType.VALIDATION_RESTRICTED]
        assert [
            change.change for change in compare_schemas({"maxLength": 5}, {"maxLength": 4}).changes
        ] == [ChangeType.VALIDATION_RESTRICTED]
        assert [
            change.change for change in compare_schemas({"minLength": 3}, {"minLength": 2}).changes
        ] == [ChangeType.VALIDATION_RELAXED]

    def test_non_numeric_bound_change(self):
        assert [
            change.change
            for change in compare_schemas({"minLength": "a"}, {"minLength": "b"}).changes
        ] == [ChangeType.VALIDATION_RESTRICTED]

    def test_additional_properties_policy(self):
        relaxed = compare_schemas({"additionalProperties": False}, {"additionalProperties": True})
        assert [change.change for change in relaxed.changes] == [
            ChangeType.ADDITIONAL_PROPERTIES_RELAXED
        ]
        restricted = compare_schemas(
            {"additionalProperties": True}, {"additionalProperties": False}
        )
        assert [change.change for change in restricted.changes] == [
            ChangeType.ADDITIONAL_PROPERTIES_RESTRICTED
        ]
        assert (
            compare_schemas(
                {"additionalProperties": False}, {"additionalProperties": False}
            ).changes
            == ()
        )
        assert (
            compare_schemas(
                {"additionalProperties": {"type": "string"}},
                {"additionalProperties": {"type": "integer"}},
            ).changes
            == ()
        )

    def test_variants_added_removed_and_changed(self):
        old = {
            "oneOf": [
                {"type": "object", "properties": {"kind": {"const": "a"}}},
                {"type": "object", "properties": {"kind": {"const": "b"}}},
            ]
        }
        new = {
            "oneOf": [
                {"type": "object", "properties": {"kind": {"const": "a"}}},
                {"type": "object", "properties": {"kind": {"const": "b"}}, "required": ["kind"]},
                {"type": "object", "properties": {"kind": {"const": "c"}}},
            ]
        }
        changes = {change.change for change in compare_schemas(old, new).changes}
        assert ChangeType.VARIANT_ADDED in changes
        old_removed = {
            "anyOf": [
                {"type": "string", "const": "a"},
                {"type": "string", "const": "b"},
            ]
        }
        new_removed = {"anyOf": [{"type": "string", "const": "a"}]}
        assert [change.change for change in compare_schemas(old_removed, new_removed).changes] == [
            ChangeType.VARIANT_REMOVED
        ]

    def test_variant_type_key_fallback(self):
        old = {"oneOf": [{"type": "string"}, {"type": "integer"}]}
        new = {"oneOf": [{"type": "string"}]}
        assert [change.change for change in compare_schemas(old, new).changes] == [
            ChangeType.VARIANT_REMOVED
        ]

    def test_refs_are_resolved(self):
        old = {
            "$defs": {"X": {"type": "object", "properties": {"a": {"type": "string"}}}},
            "type": "object",
            "properties": {"x": {"$ref": "#/$defs/X"}},
        }
        new = {
            "$defs": {"X": {"type": "object", "properties": {"b": {"type": "string"}}}},
            "type": "object",
            "properties": {"x": {"$ref": "#/$defs/X"}},
        }
        changes = {change.change for change in compare_schemas(old, new).changes}
        assert ChangeType.REMOVE_FIELD in changes
        assert ChangeType.ADD_OPTIONAL_FIELD in changes

    def test_unresolved_ref_is_handled(self):
        old = {"type": "object", "properties": {"x": {"$ref": "#/$defs/Missing"}}}
        new = {"type": "object", "properties": {"x": {"$ref": "#/$defs/Missing"}}}
        assert compare_schemas(old, new).changes == ()

    def test_non_defs_ref_is_not_resolved(self):
        assert compare_schemas({"$ref": "#/other"}, {"$ref": "#/other"}).changes == ()

    def test_recursive_refs_are_not_visited_twice(self):
        old = {
            "$defs": {"X": {"type": "object", "properties": {}}},
            "type": "object",
            "properties": {
                "a": {"$ref": "#/$defs/X"},
                "b": {"$ref": "#/$defs/X"},
            },
        }
        new = {
            "$defs": {"X": {"type": "object", "properties": {}}},
            "type": "object",
            "properties": {
                "a": {"$ref": "#/$defs/X"},
                "b": {"$ref": "#/$defs/X"},
            },
        }
        assert compare_schemas(old, new).changes == ()

    def test_non_mapping_schema_shape(self):
        old = {"type": "object", "properties": {"x": {"type": "string"}}}
        new = {"type": "object", "properties": {"x": []}}
        assert [change.change for change in compare_schemas(old, new).changes] == [
            ChangeType.TYPE_CHANGE
        ]

    def test_old_non_mapping_schema_shape(self):
        old = {"type": "object", "properties": {"x": []}}
        new = {"type": "object", "properties": {"x": {"type": "string"}}}
        assert [change.change for change in compare_schemas(old, new).changes] == [
            ChangeType.TYPE_CHANGE
        ]

    def test_schemas_without_properties_or_required(self):
        assert compare_schemas({"type": "string"}, {"type": "string"}).changes == ()
