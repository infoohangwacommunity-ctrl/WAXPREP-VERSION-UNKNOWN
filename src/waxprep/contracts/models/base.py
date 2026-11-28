"""Base contract model and policy (Stage 17).

Every typed contract DTO derives from ``ContractModel`` unless it is a
``RootModel`` union wrapper. The defaults are deliberate:

* **strict** — no implicit ``"1"`` -> ``1`` conversion at a contract boundary;
* **frozen** — a request cannot be mutated after another component receives it;
* **extra="forbid"** — unknown fields are rejected rather than silently dropped;
* **allow_inf_nan=False** — JSON cannot carry NaN/Infinity into a contract.

Forward-compatible extensions, where justified, are introduced as a new
contract revision with an explicit field, not by accepting arbitrary keys.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ContractModel(BaseModel):
    """Immutable, strictly validated base for communication DTOs."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        validate_default=True,
        allow_inf_nan=False,
    )
