"""Contract failures integrated with the Stage 15 error taxonomy (Stage 17).

A contract failure is not a new error universe: it is a bounded category with a
stable code, a retryability decision and a safe public message. The distinction
between external malformed data and an internal guarantee violation is explicit.

* ``ContractValidationError`` — incoming/outgoing data does not conform. This is
  expected at trust boundaries and is not automatically a programming defect.
* ``ContractVersionError`` — the peer does not support the requested contract
  version.
* ``ContractSerializationError`` — controlled JSON serialization failed.
* ``ContractViolationError`` — an internal component bypassed or broke its
  guaranteed contract. This is a programming defect.
"""

from __future__ import annotations

from typing import ClassVar

from waxprep.errors.taxonomy import ErrorCategory, WaxPrepError


class ContractError(WaxPrepError):
    """Base class for contract-layer failures."""

    code: ClassVar[str] = "WAX-5000"
    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL_INVARIANT
    default_message: ClassVar[str] = "A communication contract failed"


class ContractValidationError(ContractError):
    """Data did not satisfy a contract schema or semantic rule."""

    code: ClassVar[str] = "WAX-5001"
    category: ClassVar[ErrorCategory] = ErrorCategory.VALIDATION
    default_message: ClassVar[str] = "The contract payload is invalid"


class ContractVersionError(ContractError):
    """The requested contract version is unsupported or malformed."""

    code: ClassVar[str] = "WAX-5002"
    category: ClassVar[ErrorCategory] = ErrorCategory.VALIDATION
    default_message: ClassVar[str] = "The contract version is not supported"


class ContractSerializationError(ContractError):
    """A value could not be serialized under the contract rules."""

    code: ClassVar[str] = "WAX-5003"
    category: ClassVar[ErrorCategory] = ErrorCategory.INTERNAL_INVARIANT
    default_message: ClassVar[str] = "The contract payload could not be serialized"


class ContractViolationError(ContractError):
    """An internal component violated a guaranteed contract boundary."""

    code: ClassVar[str] = "WAX-5004"
    category: ClassVar[ErrorCategory] = ErrorCategory.PROGRAMMING_DEFECT
    default_message: ClassVar[str] = "A component violated its communication contract"
