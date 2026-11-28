"""Stage 17 — property-based contract invariants."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from waxprep.contracts.envelopes import MessageEnvelope, MessageKind
from waxprep.contracts.models.result import (
    ErrorDetail,
    OperationDeferred,
    OperationFailure,
    OperationRejected,
    OperationResult,
    OperationStatus,
    OperationSuccess,
)
from waxprep.contracts.validation import dump_contract, validate_contract
from waxprep.contracts.versioning import ContractVersion
from waxprep.errors.taxonomy import ErrorCategory

pytestmark = pytest.mark.contract


@settings(max_examples=40, deadline=None)
@given(
    major=st.integers(min_value=0, max_value=1000),
    minor=st.integers(min_value=0, max_value=1000),
    patch=st.integers(min_value=0, max_value=1000),
)
def test_version_string_roundtrip_and_bumps(major: int, minor: int, patch: int):
    version = ContractVersion(major, minor, patch)
    assert ContractVersion.parse(str(version)) == version
    assert version.bump_major().major == major + 1
    assert version.bump_minor().minor == minor + 1
    assert version.bump_patch().patch == patch + 1


def detail() -> ErrorDetail:
    return ErrorDetail(code="WAX-1005", category=ErrorCategory.NOT_FOUND, retryable=False)


@settings(max_examples=40, deadline=None)
@given(
    status=st.sampled_from(list(OperationStatus)),
    detail_text=st.one_of(st.none(), st.text(max_size=100)),
    retry_after=st.floats(min_value=0, max_value=86400, allow_nan=False, allow_infinity=False),
)
def test_operation_result_json_roundtrip(status, detail_text, retry_after):
    match status:
        case OperationStatus.SUCCESS:
            value = OperationResult(
                OperationSuccess(status=OperationStatus.SUCCESS, detail=detail_text)
            )
        case OperationStatus.FAILED:
            value = OperationResult(OperationFailure(status=OperationStatus.FAILED, error=detail()))
        case OperationStatus.REJECTED:
            value = OperationResult(
                OperationRejected(status=OperationStatus.REJECTED, error=detail())
            )
        case OperationStatus.DEFERRED:
            value = OperationResult(
                OperationDeferred(
                    status=OperationStatus.DEFERRED, retry_after_seconds=retry_after, error=detail()
                )
            )

    text = dump_contract(OperationResult, value)
    restored = validate_contract(OperationResult, text)
    assert restored == value
    assert restored.status is status


@settings(max_examples=30, deadline=None)
@given(
    version=st.tuples(
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
        st.integers(min_value=0, max_value=99),
    ),
    producer=st.from_regex(r"^[a-z][a-z0-9_.-]{0,20}$", fullmatch=True),
)
def test_envelope_json_roundtrip(version, producer):
    envelope = MessageEnvelope[OperationResult](
        message_id=uuid4(),
        message_kind=MessageKind.RESPONSE,
        message_type="waxprep.operation.result",
        contract_version=".".join(str(part) for part in version),
        correlation_id=uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        producer=producer,
        payload=OperationResult(OperationSuccess(status=OperationStatus.SUCCESS, detail="ok")),
    )
    restored = validate_contract(
        MessageEnvelope[OperationResult], dump_contract(MessageEnvelope[OperationResult], envelope)
    )
    assert restored == envelope


@settings(max_examples=30, deadline=None)
@given(
    extra=st.dictionaries(
        st.text(min_size=1, max_size=20).map(lambda key: f"extra_{key}"),
        st.text(max_size=20),
        min_size=1,
        max_size=5,
    )
)
def test_unknown_fields_are_always_rejected(extra):
    import json

    from waxprep.contracts.errors import ContractValidationError

    payload = {"status": "success", "detail": "ok", **extra}
    with pytest.raises(ContractValidationError):
        validate_contract(OperationSuccess, json.dumps(payload))


@settings(max_examples=20, deadline=None)
@given(st.text(max_size=200))
def test_arbitrary_text_is_preserved_not_crashed(text):
    import json

    result = validate_contract(OperationSuccess, json.dumps({"status": "success", "detail": text}))
    assert result.detail == text
