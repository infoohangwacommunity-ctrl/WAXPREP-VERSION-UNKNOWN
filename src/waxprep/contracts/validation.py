"""Runtime validation and controlled JSON serialization (Stage 17).

Rules enforced at every contract boundary:

* payload size is bounded before parsing;
* only JSON is parsed — never pickle/marshal or arbitrary Python objects;
* NaN/Infinity are rejected;
* nesting depth and total item count are bounded;
* Pydantic validates strictly;
* validation errors expose locations and error types, never raw input values;
* outgoing JSON is deterministic and re-checked against the size limit.

This module is a boundary helper, not a second validation framework. The
authoritative schema is the Pydantic contract; these checks make accepting
untrusted bytes safe.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError

from waxprep.contracts.errors import ContractSerializationError, ContractValidationError

ContractTarget = type[BaseModel] | TypeAdapter[Any]


@dataclass(frozen=True, slots=True)
class ValidationLimits:
    """Bounded validation policy applied before Pydantic sees the data."""

    max_payload_bytes: int = 256 * 1024
    max_depth: int = 32
    max_items: int = 10_000
    max_reported_errors: int = 20

    def __post_init__(self) -> None:
        for name, value in (
            ("max_payload_bytes", self.max_payload_bytes),
            ("max_depth", self.max_depth),
            ("max_items", self.max_items),
            ("max_reported_errors", self.max_reported_errors),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")


def _adapter(target: ContractTarget) -> TypeAdapter[Any]:
    return target if isinstance(target, TypeAdapter) else TypeAdapter(target)


def _reject_constant(value: str) -> Any:
    raise ValueError(f"Non-finite JSON number is not allowed: {value}")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON keys are not allowed")
        result[key] = value
    return result


def _parse_json(data: str | bytes, limits: ValidationLimits) -> tuple[Any, str]:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if not isinstance(raw, bytes):
        raise ContractValidationError("Contract payload must be text or bytes")
    if len(raw) > limits.max_payload_bytes:
        raise ContractValidationError(
            "Contract payload exceeds the size limit",
            context={"limit": limits.max_payload_bytes},
        )
    try:
        text = raw.decode("utf-8")
        return (
            json.loads(
                text,
                parse_constant=_reject_constant,
                object_pairs_hook=_reject_duplicate_keys,
            ),
            text,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        raise ContractValidationError("Contract payload is not valid JSON") from exc


def _check_structure(value: Any, limits: ValidationLimits) -> None:
    stack: list[tuple[Any, int]] = [(value, 1)]
    items = 0
    while stack:
        current, depth = stack.pop()
        items += 1
        if items > limits.max_items:
            raise ContractValidationError(
                "Contract payload has too many items",
                context={"limit": limits.max_items},
            )
        if isinstance(current, str):
            try:
                current.encode("utf-8")
            except UnicodeEncodeError as exc:
                raise ContractValidationError("Contract payload contains invalid unicode") from exc
        if isinstance(current, (dict, list)):
            if depth > limits.max_depth:
                raise ContractValidationError(
                    "Contract payload is nested too deeply",
                    context={"limit": limits.max_depth},
                )
            if isinstance(current, dict):
                stack.extend((item, depth + 1) for item in current.values())
            else:
                stack.extend((item, depth + 1) for item in current)


def _safe_errors(error: ValidationError, limits: ValidationLimits) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for item in error.errors(
        include_url=False,
        include_input=False,
        include_context=False,
    )[: limits.max_reported_errors]:
        details.append({"loc": list(item.get("loc", ())), "type": str(item.get("type", "error"))})
    return details


def validate_contract(
    target: ContractTarget,
    data: str | bytes,
    *,
    limits: ValidationLimits | None = None,
) -> Any:
    """Parse JSON, enforce structural limits, then validate strictly."""
    policy = limits or ValidationLimits()
    parsed, text = _parse_json(data, policy)
    _check_structure(parsed, policy)
    try:
        # validate_json applies JSON-strict semantics (wire enums/datetimes are
        # strings) while the model config still enforces structure/strictness.
        return _adapter(target).validate_json(text)
    except ValidationError as exc:
        raise ContractValidationError(
            "Contract validation failed",
            context={"errors": _safe_errors(exc, policy)},
        ) from exc


def dump_contract(
    target: ContractTarget,
    value: Any,
    *,
    limits: ValidationLimits | None = None,
) -> str:
    """Serialize deterministically and enforce the outgoing size limit."""
    policy = limits or ValidationLimits()
    try:
        payload = _adapter(target).dump_python(value, mode="json")
        text = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        encoded = text.encode("utf-8")
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        raise ContractSerializationError("Contract payload could not be serialized") from exc
    if len(encoded) > policy.max_payload_bytes:
        raise ContractSerializationError(
            "Serialized contract exceeds the size limit",
            context={"limit": policy.max_payload_bytes},
        )
    return text
