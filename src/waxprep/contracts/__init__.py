"""Internal communication contracts (Stage 17).

Contract-first building blocks for independent WaxPrep components:

* typed capability Protocols (``interfaces``);
* strict, immutable Pydantic DTOs (``models``);
* a versioned message envelope (``envelopes``);
* bounded validation/serialization (``validation``);
* semantic contract identity and compatibility policy (``versioning``);
* deterministic JSON Schema publication and drift detection (``schema``);
* contract failures integrated with the Stage 15 taxonomy (``errors``).

The package is inner-layer: it may import the error taxonomy and Pydantic, but
not concrete adapters, registries, middleware, configuration or the application.
"""

from waxprep.contracts.envelopes import MessageEnvelope, MessageKind
from waxprep.contracts.errors import (
    ContractError,
    ContractSerializationError,
    ContractValidationError,
    ContractVersionError,
    ContractViolationError,
)
from waxprep.contracts.interfaces import (
    CommandHandler,
    EventPublisher,
    RequestHandler,
    StreamingHandler,
)
from waxprep.contracts.models import (
    ContractModel,
    ErrorDetail,
    OperationDeferred,
    OperationFailure,
    OperationRejected,
    OperationResult,
    OperationStatus,
    OperationSuccess,
)
from waxprep.contracts.schema import (
    ContractSchemaRegistry,
    DriftReport,
    build_default_registry,
    canonical_json,
    load_schema,
)
from waxprep.contracts.validation import (
    ValidationLimits,
    dump_contract,
    validate_contract,
)
from waxprep.contracts.versioning import (
    ChangeType,
    Compatibility,
    CompatibilityReport,
    ContractIdentity,
    ContractVersion,
    InvalidContractVersionError,
    SchemaChange,
    VersionBump,
    classify_change,
    compare_schemas,
)

__all__ = [
    "ChangeType",
    "CommandHandler",
    "Compatibility",
    "CompatibilityReport",
    "ContractError",
    "ContractIdentity",
    "ContractModel",
    "ContractSchemaRegistry",
    "ContractSerializationError",
    "ContractValidationError",
    "ContractVersion",
    "ContractVersionError",
    "ContractViolationError",
    "DriftReport",
    "ErrorDetail",
    "EventPublisher",
    "InvalidContractVersionError",
    "MessageEnvelope",
    "MessageKind",
    "OperationDeferred",
    "OperationFailure",
    "OperationRejected",
    "OperationResult",
    "OperationStatus",
    "OperationSuccess",
    "RequestHandler",
    "SchemaChange",
    "StreamingHandler",
    "VersionBump",
    "ValidationLimits",
    "build_default_registry",
    "canonical_json",
    "classify_change",
    "compare_schemas",
    "dump_contract",
    "load_schema",
    "validate_contract",
]
