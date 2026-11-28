"""Stage 17 — bounded, safe runtime validation and serialization."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, TypeAdapter, ValidationError

from waxprep.contracts.errors import ContractSerializationError, ContractValidationError
from waxprep.contracts.models.result import (
    ErrorDetail,
    OperationFailure,
    OperationResult,
    OperationSuccess,
)
from waxprep.contracts.validation import (
    ValidationLimits,
    dump_contract,
    validate_contract,
)
from waxprep.errors.taxonomy import ErrorCategory

pytestmark = pytest.mark.contract

SENTINEL = "SENTINEL-contract-9f2a"


class TestValidationLimits:
    @pytest.mark.parametrize(
        "field", ["max_payload_bytes", "max_depth", "max_items", "max_reported_errors"]
    )
    @pytest.mark.parametrize("value", [0, -1])
    def test_limits_must_be_positive(self, field, value):
        with pytest.raises(ValueError, match=field):
            ValidationLimits(**{field: value})


class TestValidateContract:
    def test_accepts_valid_json(self):
        result = validate_contract(
            OperationResult,
            '{"status":"success","detail":"ok"}',
        )
        assert isinstance(result, OperationResult)
        assert result.successful is True

    def test_accepts_bytes_and_a_type_adapter(self):
        adapter = TypeAdapter(OperationResult)
        result = validate_contract(adapter, b'{"status":"success","detail":"ok"}')
        assert result.status.value == "success"

    def test_rejects_non_text_input(self):
        with pytest.raises(ContractValidationError, match="text or bytes"):
            validate_contract(OperationResult, 123)  # type: ignore[arg-type]

    def test_rejects_invalid_json(self):
        with pytest.raises(ContractValidationError, match="not valid JSON"):
            validate_contract(OperationResult, '{"status":')

    def test_rejects_invalid_utf8(self):
        with pytest.raises(ContractValidationError, match="not valid JSON"):
            validate_contract(OperationResult, b"\xff\xfe")

    @pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
    def test_rejects_non_finite_numbers(self, constant):
        with pytest.raises(ContractValidationError, match="not valid JSON"):
            validate_contract(OperationSuccess, f'{{"detail": {constant}}}')

    def test_rejects_duplicate_keys(self):
        with pytest.raises(ContractValidationError, match="not valid JSON"):
            validate_contract(OperationSuccess, '{"detail":"a","detail":"b"}')

    def test_rejects_oversized_payload(self):
        limits = ValidationLimits(max_payload_bytes=10)
        with pytest.raises(ContractValidationError, match="size limit"):
            validate_contract(OperationSuccess, '{"detail":"long"}', limits=limits)

    def test_rejects_excessive_depth(self):
        limits = ValidationLimits(max_depth=2)
        data = '{"a":{"b":{"c":1}}}'
        with pytest.raises(ContractValidationError, match="nested too deeply"):
            validate_contract(OperationSuccess, data, limits=limits)

    def test_rejects_too_many_items(self):
        limits = ValidationLimits(max_items=2)
        with pytest.raises(ContractValidationError, match="too many items"):
            validate_contract(OperationSuccess, "[1,2,3]", limits=limits)

    def test_validation_errors_are_sanitized(self):
        data = (
            '{"status":"failed","error":'
            f'{{"code":"{SENTINEL}","category":"not_found","retryable":false}}'
            "}"
        )
        with pytest.raises(ContractValidationError) as raised:
            validate_contract(OperationResult, data)
        text = str(raised.value) + str(raised.value.context)
        assert SENTINEL not in text
        assert raised.value.context["errors"][0]["loc"] == ["failed", "error", "code"]
        assert raised.value.context["errors"][0]["type"]

    def test_unknown_field_is_rejected(self):
        with pytest.raises(ContractValidationError):
            validate_contract(OperationSuccess, '{"detail":"ok","extra":"x"}')

    def test_extra_unknown_fields_do_not_echo_input(self):
        with pytest.raises(ContractValidationError) as raised:
            validate_contract(OperationSuccess, f'{{"detail":"ok","extra":"{SENTINEL}"}}')
        assert SENTINEL not in str(raised.value) + str(raised.value.context)


class TestDumpContract:
    def test_dump_is_deterministic(self):
        value = OperationSuccess(detail="ok")
        first = dump_contract(OperationSuccess, value)
        second = dump_contract(OperationSuccess, value)
        assert first == second
        assert first == '{"detail":"ok","status":"success"}'

    def test_dump_roundtrips_through_validation(self):
        value = OperationResult(
            OperationFailure(
                error=ErrorDetail(
                    code="WAX-1005",
                    category=ErrorCategory.NOT_FOUND,
                    retryable=False,
                )
            )
        )
        text = dump_contract(OperationResult, value)
        restored = validate_contract(OperationResult, text)
        assert restored == value

    def test_dump_enforces_size_limit(self):
        limits = ValidationLimits(max_payload_bytes=10)
        with pytest.raises(ContractSerializationError, match="size limit"):
            dump_contract(OperationSuccess, OperationSuccess(detail="x" * 100), limits=limits)

    def test_dump_rejects_non_finite_values(self):
        class FloatModel(BaseModel):
            value: float

        with pytest.raises(ContractSerializationError, match="could not be serialized"):
            dump_contract(FloatModel, FloatModel(value=float("nan")))

    def test_dump_rejects_unserializable_value(self):
        with pytest.raises(ContractSerializationError, match="could not be serialized"):
            dump_contract(OperationSuccess, object())

    def test_dump_rejects_lone_surrogate(self):
        with pytest.raises(ContractSerializationError, match="could not be serialized"):
            dump_contract(TypeAdapter(dict), {"value": "\ud800"})

    def test_pydantic_validation_error_is_wrapped(self):
        with pytest.raises(ValidationError) as raised:
            OperationSuccess(detail=1)  # type: ignore[arg-type]
        assert raised.value.error_count() == 1
