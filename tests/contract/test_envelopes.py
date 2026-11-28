"""Stage 17 — versioned message envelope and metadata allowlist."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from waxprep.contracts.envelopes import (
    MAX_METADATA_ENTRIES,
    MAX_METADATA_VALUE,
    MessageEnvelope,
    MessageKind,
    envelope_schema,
)
from waxprep.contracts.models.result import OperationResult, OperationStatus, OperationSuccess

pytestmark = pytest.mark.contract

Envelope = MessageEnvelope[OperationResult]


def make_envelope(**overrides):
    values = {
        "message_id": uuid4(),
        "message_kind": MessageKind.RESPONSE,
        "message_type": "waxprep.operation.result",
        "contract_version": "1.0.0",
        "correlation_id": uuid4(),
        "created_at": datetime(2026, 1, 1, 12, 0, tzinfo=UTC),
        "producer": "waxprep.contract-test",
        "payload": OperationResult(OperationSuccess(status=OperationStatus.SUCCESS, detail="ok")),
    }
    values.update(overrides)
    return Envelope(**values)


class TestMessageEnvelope:
    def test_valid_envelope(self):
        envelope = make_envelope(metadata={"x-trace": "abc"})
        assert envelope.message_kind is MessageKind.RESPONSE
        assert envelope.payload.successful is True
        assert envelope.metadata == {"x-trace": "abc"}
        assert envelope.causation_id is None

    def test_json_roundtrip_preserves_payload_and_ids(self):
        envelope = make_envelope()
        restored = Envelope.model_validate_json(envelope.model_dump_json())
        assert restored == envelope

    def test_created_at_is_normalised_to_utc(self):
        source = datetime(2026, 1, 1, 12, 0, tzinfo=timezone(timedelta(hours=3)))
        envelope = make_envelope(created_at=source)
        assert envelope.created_at.tzinfo is UTC
        assert envelope.created_at.hour == 9

    def test_naive_datetime_is_rejected(self):
        with pytest.raises(ValidationError, match="timezone-aware"):
            make_envelope(created_at=datetime(2026, 1, 1, 12, 0))  # noqa: DTZ001

    @pytest.mark.parametrize("version", ["1.0", "1.0.0.0", "v1.0.0", "01.0.0"])
    def test_invalid_contract_version_is_rejected(self, version):
        with pytest.raises(ValidationError):
            make_envelope(contract_version=version)

    @pytest.mark.parametrize(
        "message_type",
        ["WaxPrep", "single", "waxprep..result", "waxprep.result.", "-bad.name"],
    )
    def test_invalid_message_type_is_rejected(self, message_type):
        with pytest.raises(ValidationError):
            make_envelope(message_type=message_type)

    @pytest.mark.parametrize("producer", ["", "UPPER", "has space", "x" * 65])
    def test_invalid_producer_is_rejected(self, producer):
        with pytest.raises(ValidationError):
            make_envelope(producer=producer)

    def test_unknown_message_kind_is_rejected(self):
        with pytest.raises(ValidationError):
            make_envelope(message_kind="telepathy")

    def test_metadata_requires_namespaced_keys(self):
        with pytest.raises(ValidationError, match="metadata keys must match"):
            make_envelope(metadata={"trace": "abc"})

    def test_metadata_key_is_bounded(self):
        with pytest.raises(ValidationError, match="metadata keys must match"):
            make_envelope(metadata={"x-" + "a" * 40: "v"})

    def test_metadata_value_is_bounded(self):
        with pytest.raises(ValidationError, match="too long"):
            make_envelope(metadata={"x-note": "v" * (MAX_METADATA_VALUE + 1)})

    def test_metadata_entry_count_is_bounded(self):
        metadata = {f"x-{index}": "v" for index in range(MAX_METADATA_ENTRIES + 1)}
        with pytest.raises(ValidationError, match="too many"):
            make_envelope(metadata=metadata)

    def test_metadata_values_must_be_strings(self):
        with pytest.raises(ValidationError):
            make_envelope(metadata={"x-count": 1})  # type: ignore[dict-item]

    def test_causation_id_distinct_from_correlation(self):
        parent = uuid4()
        envelope = make_envelope(causation_id=parent)
        assert envelope.causation_id == parent


class TestEnvelopeSchema:
    def test_schema_is_deterministic_and_typed(self):
        first = envelope_schema(OperationResult)
        second = envelope_schema(OperationResult)
        assert first == second
        assert first["type"] == "object"
        assert "payload" in first["properties"]
        assert "$defs" in first

    def test_schema_contains_payload_definitions(self):
        schema = envelope_schema(OperationResult)
        assert "OperationResult" in schema["$defs"]
        assert "OperationSuccess" in str(schema["$defs"])


class TestMetadataKeyFormat:
    @pytest.mark.parametrize(
        "key",
        [
            "x-UPPER",
            "x-space key",
            "x- invalid",
            "x-",
            "x-bad!",
            "x-under_score",
            "x-ünicode",
            "X-lower",
        ],
    )
    def test_invalid_metadata_keys_are_rejected(self, key):
        with pytest.raises(ValidationError, match="metadata keys must match"):
            make_envelope(metadata={key: "value"})

    @pytest.mark.parametrize("key", ["x-a", "x-0", "x-trace-id", "x-" + "a" * 32])
    def test_valid_metadata_keys_are_accepted(self, key):
        assert make_envelope(metadata={key: "value"}).metadata[key] == "value"


class TestDeepImmutability:
    def test_metadata_cannot_be_mutated(self):
        metadata = make_envelope(metadata={"x-trace": "abc"}).metadata
        with pytest.raises(TypeError):
            metadata["x-new"] = "value"  # type: ignore[index]
        with pytest.raises(TypeError):
            del metadata["x-trace"]
        with pytest.raises(TypeError):
            metadata.clear()
        with pytest.raises(TypeError):
            metadata.pop("x-trace")
        with pytest.raises(TypeError):
            metadata.popitem()
        with pytest.raises(TypeError):
            metadata.setdefault("x-new", "value")
        with pytest.raises(TypeError):
            metadata.update({"x-new": "value"})
        with pytest.raises(TypeError):
            metadata |= {"x-new": "value"}

    def test_metadata_survives_deep_copy(self):
        envelope = make_envelope(metadata={"x-trace": "abc"})
        copied = envelope.model_copy(deep=True)
        assert copied.metadata == {"x-trace": "abc"}
        assert isinstance(copied.metadata, dict)
        with pytest.raises(TypeError):
            copied.metadata["x-new"] = "value"

    def test_frozen_dict_copy_is_immutable(self):
        import copy

        frozen = make_envelope(metadata={"x-trace": "abc"}).metadata
        assert copy.copy(frozen) is frozen
        assert copy.deepcopy(frozen) is frozen

    def test_arbitrary_pydantic_payload_is_rejected_by_the_envelope(self):
        from pydantic import BaseModel

        class PlainModel(BaseModel):
            value: str

        with pytest.raises(ValidationError, match="must be immutable"):
            MessageEnvelope[PlainModel](
                message_id=uuid4(),
                message_kind=MessageKind.RESPONSE,
                message_type="waxprep.operation.result",
                contract_version="1.0.0",
                correlation_id=uuid4(),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                producer="waxprep.test",
                payload=PlainModel(value="x"),
            )

    def test_contract_model_rejects_mutable_fields(self):
        from waxprep.contracts.models.base import ContractModel

        class MutableContract(ContractModel):
            values: list[str]

        with pytest.raises(ValidationError, match="must be immutable"):
            MutableContract(values=["a"])

    def test_contract_model_rejects_arbitrary_nested_models(self):
        from pydantic import BaseModel

        from waxprep.contracts.models.base import ContractModel

        class PlainModel(BaseModel):
            value: str

        class NestedContract(ContractModel):
            nested: PlainModel

        with pytest.raises(ValidationError, match="must be immutable"):
            NestedContract(nested=PlainModel(value="x"))

    def test_contract_model_accepts_immutable_nested_data(self):
        from waxprep.contracts.models.base import ContractModel

        class Nested(ContractModel):
            name: str

        class Parent(ContractModel):
            items: tuple[Nested, ...]
            tags: frozenset[str]
            mapping: dict[str, str]

        with pytest.raises(ValidationError, match="must be immutable"):
            Parent(
                items=(Nested(name="a"),),
                tags=frozenset({"x"}),
                mapping={"x": "y"},
            )
