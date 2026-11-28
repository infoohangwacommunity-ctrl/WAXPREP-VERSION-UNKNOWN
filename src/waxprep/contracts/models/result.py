"""Typed operation results and error details (Stage 17).

A discriminated union is used instead of guessing a variant from whichever
fields happen to be present. The variants cover the four documented outcomes:
success, failure, rejection and deferral.

``ErrorDetail`` carries only bounded, safe fields. Exception messages, input
values, stack traces and credentials are never part of a contract payload.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, RootModel

from waxprep.contracts.errors import ContractViolationError
from waxprep.contracts.models.base import ContractModel
from waxprep.errors.taxonomy import ErrorCategory, WaxPrepError


class OperationStatus(StrEnum):
    """Bounded operation outcome discriminator."""

    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class ErrorDetail(ContractModel):
    """Safe, bounded failure identity shared across components."""

    code: str = Field(pattern=r"^WAX-[0-9]{4}$")
    category: ErrorCategory
    retryable: bool

    @classmethod
    def from_error(cls, error: WaxPrepError) -> ErrorDetail:
        """Translate a Stage 15 error without copying its message or context."""
        return cls(
            code=error.code,
            category=error.category,
            retryable=error.is_retryable,
        )


class OperationSuccess(ContractModel):
    status: Literal[OperationStatus.SUCCESS] = OperationStatus.SUCCESS
    detail: str | None = Field(default=None, max_length=512)


class OperationFailure(ContractModel):
    status: Literal[OperationStatus.FAILED] = OperationStatus.FAILED
    error: ErrorDetail


class OperationRejected(ContractModel):
    status: Literal[OperationStatus.REJECTED] = OperationStatus.REJECTED
    error: ErrorDetail


class OperationDeferred(ContractModel):
    status: Literal[OperationStatus.DEFERRED] = OperationStatus.DEFERRED
    retry_after_seconds: float = Field(ge=0, le=86400)
    error: ErrorDetail | None = None


OperationVariant = Annotated[
    OperationSuccess | OperationFailure | OperationRejected | OperationDeferred,
    Field(discriminator="status"),
]


class OperationResult(RootModel[OperationVariant]):
    """Root wrapper for the discriminated operation-result union."""

    model_config = ConfigDict(frozen=True, strict=True)

    @property
    def status(self) -> OperationStatus:
        return self.root.status

    @property
    def successful(self) -> bool:
        return isinstance(self.root, OperationSuccess)

    @property
    def error(self) -> ErrorDetail | None:
        return getattr(self.root, "error", None)

    def require_success(self) -> OperationSuccess:
        """Return the success variant or raise a contract violation."""
        if not isinstance(self.root, OperationSuccess):
            raise ContractViolationError(
                "A successful operation was required",
                context={"status": str(self.root.status)},
            )
        return self.root
