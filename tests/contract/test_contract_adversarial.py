"""Stage 17 — adversarial contract inputs and safe rejection."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from waxprep.contracts.envelopes import MessageEnvelope
from waxprep.contracts.errors import ContractSerializationError, ContractValidationError
from waxprep.contracts.models.result import OperationSuccess
from waxprep.contracts.validation import (
    ValidationLimits,
    dump_contract,
    validate_contract,
)

pytestmark = pytest.mark.contract

SENTINEL = "SENTINEL-adversarial-77c2"


class TestAdversarialInputs:
    def test_deeply_nested_json_is_rejected_not_crashed(self):
        payload = "[" * 5000 + "]" * 5000
        with pytest.raises(ContractValidationError):
            validate_contract(OperationSuccess, payload)

    def test_structurally_deep_json_within_size_is_rejected(self):
        payload = '{"detail":' + "[" * 40 + "]" * 40 + "}"
        with pytest.raises(ContractValidationError, match="nested too deeply"):
            validate_contract(OperationSuccess, payload)

    def test_oversized_payload_is_rejected_before_parsing(self):
        payload = b"{" + b" " * 1000 + b"}"
        with pytest.raises(ContractValidationError, match="size limit"):
            validate_contract(
                OperationSuccess, payload, limits=ValidationLimits(max_payload_bytes=10)
            )

    def test_duplicate_json_keys_are_rejected(self):
        with pytest.raises(ContractValidationError, match="not valid JSON"):
            validate_contract(OperationSuccess, '{"detail":"a","detail":"b"}')

    def test_lone_surrogate_is_rejected(self):
        with pytest.raises(ContractValidationError, match="invalid unicode"):
            validate_contract(OperationSuccess, '{"detail":"\\ud800"}')

    def test_nan_and_infinity_are_rejected(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with pytest.raises(ContractValidationError, match="not valid JSON"):
                validate_contract(OperationSuccess, f'{{"detail":{constant}}}')

    def test_unknown_fields_are_forbidden(self):
        with pytest.raises(ContractValidationError):
            validate_contract(OperationSuccess, '{"detail":"ok","admin":true}')

    def test_validation_error_does_not_echo_injection_payload(self):
        payload = f'{{"detail":{SENTINEL},"admin":true}}'
        with pytest.raises(ContractValidationError) as raised:
            validate_contract(OperationSuccess, payload)
        rendered = str(raised.value) + str(raised.value.context)
        assert SENTINEL not in rendered
        assert "admin" not in rendered

    def test_unicode_text_is_preserved(self):
        result = validate_contract(OperationSuccess, '{"detail":"héllo 世界"}')
        assert result.detail == "héllo 世界"

    def test_control_characters_in_text_are_preserved(self):
        result = validate_contract(OperationSuccess, '{"detail":"line\\nnext"}')
        assert result.detail == "line\nnext"

    def test_oversized_output_is_rejected(self):
        with pytest.raises(ContractSerializationError, match="size limit"):
            dump_contract(
                OperationSuccess,
                OperationSuccess(detail="é" * 200),
                limits=ValidationLimits(max_payload_bytes=50),
            )

    def test_non_finite_output_is_rejected(self):
        class FloatModel(BaseModel):
            value: float

        with pytest.raises(ContractSerializationError, match="could not be serialized"):
            dump_contract(FloatModel, FloatModel(value=float("inf")))

    def test_envelope_rejects_unbounded_metadata(self):
        import datetime
        from uuid import uuid4

        from waxprep.contracts.models.result import OperationResult

        with pytest.raises(ValidationError):
            MessageEnvelope[OperationResult](
                message_id=uuid4(),
                message_kind="event",
                message_type="waxprep.operation.result",
                contract_version="1.0.0",
                correlation_id=uuid4(),
                created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.UTC),
                producer="waxprep.test",
                payload=OperationResult(OperationSuccess()),
                metadata={f"x-{index}": "v" for index in range(17)},
            )
