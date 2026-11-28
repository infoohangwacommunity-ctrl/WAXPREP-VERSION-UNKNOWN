"""Base contract models and genuine immutability policy (Stage 17).

``ContractModel`` is strict, frozen and rejects unknown fields. Pydantic's
``frozen=True`` only prevents field assignment; it does not freeze a mutable
dict/list stored in a field. This module therefore adds a real immutability
policy:

* contract fields may contain only immutable values (scalars, enums, UUID,
  datetimes, tuples, frozensets, frozen contract models);
* mutable ``list``/``dict``/``set``/arbitrary ``BaseModel`` values are rejected;
* envelope metadata uses ``FrozenDict``, a read-only dict representation;
* ``RootModel`` unions use ``ContractRootModel``, which carries the same frozen
  and strict configuration.

A contract author who needs a collection uses a tuple, or introduces a nested
frozen contract model. This is deliberate: a received contract cannot change
underneath another component.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, RootModel, model_validator


class FrozenDict(dict[str, str]):
    """Read-only ``dict`` representation used for bounded metadata.

    Subclassing ``dict`` keeps Pydantic's JSON Schema and serialization natural;
    every mutation entry point is disabled.
    """

    def __setitem__(self, key: str, value: str) -> None:
        raise TypeError("contract metadata is immutable")

    def __delitem__(self, key: str) -> None:
        raise TypeError("contract metadata is immutable")

    def clear(self) -> None:
        raise TypeError("contract metadata is immutable")

    def pop(self, key: str, default: Any = None) -> str:
        raise TypeError("contract metadata is immutable")

    def popitem(self) -> tuple[str, str]:
        raise TypeError("contract metadata is immutable")

    def setdefault(self, key: str, default: str = "") -> str:
        raise TypeError("contract metadata is immutable")

    def update(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("contract metadata is immutable")

    def __ior__(self, other: Any) -> FrozenDict:  # type: ignore[misc, override]
        raise TypeError("contract metadata is immutable")

    def __copy__(self) -> FrozenDict:
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> FrozenDict:
        del memo
        return self


_IMMUTABLE_SCALARS = (
    str,
    int,
    float,
    bool,
    bytes,
    type(None),
    Enum,
    date,
    datetime,
    time,
    timedelta,
    UUID,
    Decimal,
    MappingProxyType,
)


def _assert_immutable(value: Any, path: str) -> None:
    if isinstance(value, (FrozenDict, ContractModel, ContractRootModel)):
        return
    if isinstance(value, _IMMUTABLE_SCALARS):
        return
    if isinstance(value, (tuple, frozenset)):
        for index, item in enumerate(value):
            _assert_immutable(item, f"{path}[{index}]")
        return
    raise ValueError(
        f"Contract field {path!r} must be immutable; "
        "use scalars, tuples, frozensets, FrozenDict or nested contract models"
    )


class ContractModel(BaseModel):
    """Immutable, strictly validated base for communication DTOs."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        validate_default=True,
        allow_inf_nan=False,
    )

    @model_validator(mode="after")
    def _enforce_deep_immutability(self) -> Self:
        for name, value in self.__dict__.items():
            _assert_immutable(value, name)
        return self


class ContractRootModel[RootT](RootModel[RootT]):
    """Frozen, strict root wrapper for discriminated contract unions."""

    model_config = ConfigDict(frozen=True, strict=True)
