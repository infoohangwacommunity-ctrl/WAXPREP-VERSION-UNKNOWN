"""Standard communication envelope (Stage 17).

The envelope is used where durable, asynchronous or independently deployed
communication needs identity and lifecycle metadata. Ordinary same-process
function calls use typed request/response objects directly; they do not carry a
redundant envelope.

Field semantics are deliberately distinct:

* ``message_id`` identifies this message;
* ``correlation_id`` groups one logical operation across components;
* ``causation_id`` identifies the message that caused this one;
* the HTTP request ID remains a transport-level concept and is not substituted
  for any of the above.

``metadata`` is an allowlisted extension point: keys must be namespaced
``x-...``, are bounded in count and length, and values must be strings.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from waxprep.contracts.models.base import ContractModel, ContractRootModel, FrozenDict
from waxprep.contracts.versioning import ContractVersion, InvalidContractVersionError

_NAME_PATTERN = r"^[a-z][a-z0-9]*(\.[a-z0-9]+)+$"
_PRODUCER_PATTERN = r"^[a-z][a-z0-9_.-]{0,63}$"
_VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+$"
_METADATA_KEY = r"^x-[a-z0-9-]{1,32}$"
_METADATA_KEY_PATTERN = re.compile(_METADATA_KEY)
MAX_METADATA_ENTRIES = 16
MAX_METADATA_VALUE = 256


class MessageKind(StrEnum):
    """Bounded communication pattern discriminator."""

    REQUEST = "request"
    RESPONSE = "response"
    COMMAND = "command"
    EVENT = "event"
    STREAM = "stream"


class MessageEnvelope[PayloadT: ContractModel | ContractRootModel[Any]](ContractModel):
    """Versioned metadata surrounding one typed contract payload."""

    message_id: UUID
    message_kind: MessageKind
    message_type: str = Field(pattern=_NAME_PATTERN, max_length=128)
    contract_version: str = Field(pattern=_VERSION_PATTERN, max_length=32)
    correlation_id: UUID
    causation_id: UUID | None = None
    created_at: datetime
    producer: str = Field(pattern=_PRODUCER_PATTERN)
    payload: PayloadT
    metadata: dict[str, str] = Field(default_factory=FrozenDict)

    @field_validator("contract_version")
    @classmethod
    def version_must_be_semver(cls, value: str) -> str:
        try:
            ContractVersion.parse(value)
        except InvalidContractVersionError as exc:
            raise ValueError("contract_version must be strict major.minor.patch") from exc
        return value

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_utc_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        return value.astimezone(UTC)

    @field_validator("metadata")
    @classmethod
    def metadata_must_be_allowlisted(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > MAX_METADATA_ENTRIES:
            raise ValueError("metadata has too many entries")
        for key, item in value.items():
            if _METADATA_KEY_PATTERN.fullmatch(key) is None:
                raise ValueError(
                    "metadata keys must match 'x-' followed by 1-32 lower-case "
                    "letters, digits or hyphens"
                )
            if len(item) > MAX_METADATA_VALUE:
                raise ValueError("metadata value is too long")
        return FrozenDict(value)


def envelope_schema(contract: type[BaseModel]) -> dict[str, Any]:
    """Return the JSON Schema for an envelope specialised to a payload type."""
    from pydantic import TypeAdapter

    return TypeAdapter(MessageEnvelope[contract]).json_schema()  # type: ignore[valid-type]
