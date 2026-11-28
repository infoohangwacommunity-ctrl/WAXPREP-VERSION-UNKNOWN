"""Stage 17 — strict, immutable data contracts and operation results."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from waxprep.contracts.errors import (
    ContractError,
    ContractSerializationError,
    ContractValidationError,
    ContractVersionError,
    ContractViolationError,
)
from waxprep.contracts.models.base import ContractModel
from waxprep.contracts.models.result import (
    ErrorDetail,
    OperationDeferred,
    OperationFailure,
    OperationRejected,
    OperationResult,
    OperationStatus,
    OperationSuccess,
)
from waxprep.errors.taxonomy import (
    DependencyTimeoutError,
    ErrorCategory,
    NotFoundError,
)

pytestmark = pytest.mark.contract


def not_found_detail() -> ErrorDetail:
    return ErrorDetail(code="WAX-1005", category=ErrorCategory.NOT_FOUND, retryable=False)


class TestContractModelPolicy:
    def test_model_is_frozen(self):
        result = OperationSuccess(detail="ok")
        with pytest.raises(ValidationError):
            result.detail = "changed"  # type: ignore[misc]

    def test_extra_fields_are_forbidden(self):
        with pytest.raises(ValidationError):
            OperationSuccess(detail="ok", injected="value")  # type: ignore[call-arg]

    def test_strict_mode_rejects_implicit_string_to_number(self):
        class NumberContract(ContractModel):
            value: int

        with pytest.raises(ValidationError):
            NumberContract(value="1")  # type: ignore[arg-type]

    def test_infinity_is_rejected(self):
        with pytest.raises(ValidationError):
            OperationDeferred(retry_after_seconds=float("inf"))


class TestOperationResult:
    def test_success_variant(self):
        result = OperationResult(OperationSuccess(detail="done"))
        assert result.status is OperationStatus.SUCCESS
        assert result.successful is True
        assert result.error is None
        assert result.require_success().detail == "done"

    @pytest.mark.parametrize(
        "variant",
        [
            OperationFailure(error=not_found_detail()),
            OperationRejected(error=not_found_detail()),
            OperationDeferred(retry_after_seconds=1.5),
        ],
    )
    def test_non_success_variants(self, variant):
        result = OperationResult(variant)
        assert result.successful is False
        assert result.status is variant.status
        with pytest.raises(ContractViolationError):
            result.require_success()

    def test_deferred_error_is_optional(self):
        result = OperationResult(OperationDeferred(retry_after_seconds=5, error=not_found_detail()))
        assert result.error == not_found_detail()

    def test_unknown_discriminator_is_rejected(self):
        with pytest.raises(ValidationError):
            OperationResult.model_validate({"status": "teleported"})

    def test_missing_variant_field_is_rejected(self):
        with pytest.raises(ValidationError):
            OperationResult.model_validate({"status": "failed"})

    def test_deferred_bounds(self):
        with pytest.raises(ValidationError):
            OperationDeferred(retry_after_seconds=-1)
        with pytest.raises(ValidationError):
            OperationDeferred(retry_after_seconds=86401)

    def test_success_detail_is_bounded(self):
        with pytest.raises(ValidationError):
            OperationSuccess(detail="x" * 513)


class TestErrorDetail:
    def test_from_error_copies_only_safe_bounded_fields(self):
        detail = ErrorDetail.from_error(DependencyTimeoutError("secret message"))
        assert detail == ErrorDetail(
            code="WAX-2002",
            category=ErrorCategory.DEPENDENCY_TIMEOUT,
            retryable=True,
        )
        assert "secret" not in detail.model_dump_json()

    def test_non_retryable_error(self):
        assert ErrorDetail.from_error(NotFoundError()).retryable is False

    def test_invalid_code_is_rejected(self):
        with pytest.raises(ValidationError):
            ErrorDetail(code="bad", category=ErrorCategory.UNKNOWN, retryable=False)

    def test_invalid_category_is_rejected(self):
        with pytest.raises(ValidationError):
            ErrorDetail.model_validate({
                "code": "WAX-1005",
                "category": "not-a-category",
                "retryable": False,
            })


class TestContractErrors:
    @pytest.mark.parametrize(
        ("error_type", "code", "category"),
        [
            (ContractError, "WAX-5000", ErrorCategory.INTERNAL_INVARIANT),
            (ContractValidationError, "WAX-5001", ErrorCategory.VALIDATION),
            (ContractVersionError, "WAX-5002", ErrorCategory.VALIDATION),
            (ContractSerializationError, "WAX-5003", ErrorCategory.INTERNAL_INVARIANT),
            (ContractViolationError, "WAX-5004", ErrorCategory.PROGRAMMING_DEFECT),
        ],
    )
    def test_error_taxonomy_mapping(self, error_type, code, category):
        error = error_type()
        assert error.code == code
        assert error.category is category
        assert error.safe_message
        assert error.to_fields()["error.code"] == code
