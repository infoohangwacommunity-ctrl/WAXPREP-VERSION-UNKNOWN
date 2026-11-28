# Internal Communication Contracts (Stage 17)

**Owner:** contract identity, typed interfaces, DTOs, envelopes, validation,
serialization, schema publication, compatibility and error mapping.
**Does not cover:** transport infrastructure (queues, brokers, RPC), concrete
Tutor/Judge/Notebook components, or HTTP API documentation.

---

## 1. The rule

A component must never have to guess what another component means. A contract
defines the information, its structure, field meaning, required/optional fields,
types, failure representation, identity and compatibility policy.

Stage 17 establishes the machinery and conventions. It does **not** invent
components that do not exist. The only concrete published contracts today are
the operation result and the safe error detail.

## 2. One authoritative definition per interface

The existing interfaces remain authoritative where they are:

- `core/protocols.py` — `Message`, `MessageHandler`, `ContextProvider` for the
  current foundation boundaries;
- `registries/*.py` — `ChannelAdapter`, `ModelAdapter`, `Tool` for registered
  adapters.

`contracts/interfaces.py` adds **generic typed capability Protocols**:

| Protocol | Responsibility |
|---|---|
| `RequestHandler[RequestT, ResponseT]` | One typed request -> one typed response |
| `CommandHandler[CommandT, ResultT]` | One imperative command -> one typed result |
| `EventPublisher[EventT]` | Publish one typed event |
| `StreamingHandler[RequestT, ChunkT]` | Ordered typed chunks for one request |

These do not redefine the existing protocols. When a real component adopts a
typed contract, its concrete types are supplied as Protocol parameters. There is
no universal component interface.

## 3. Six logical responsibilities

| Layer | Implementation | Responsibility |
|---|---|---|
| Interfaces | `contracts/interfaces.py` | What a component must implement |
| Data contracts | `contracts/models/` | Exact typed information exchanged |
| Envelope | `contracts/envelopes.py` | Identity/correlation metadata where needed |
| Validation | `contracts/validation.py` | Safe parsing, limits, strict validation |
| Versioning | `contracts/versioning.py` | Identity, compatibility policy |
| Schemas | `contracts/schema.py` | Deterministic JSON Schema publication/drift |
| Errors | `contracts/errors.py` | Contract failures in the Stage 15 taxonomy |

These are one package, not six subsystems.

## 4. Data contract policy

`ContractModel` is:

- **strict** — `"1"` is not accepted as `1` in Python construction;
- **frozen** — a received request cannot be mutated;
- **extra=forbid** — unknown structural fields are rejected;
- **finite-only** — NaN/Infinity are rejected.

Forward-compatible extensions are introduced as a new contract revision with an
explicit field. There is no global `extra="ignore"`.

Existing concrete contracts:

- `ErrorDetail` — `code` (`WAX-####`), bounded `category`, `retryable`; no
  exception message or input.
- `OperationResult` — discriminated union: `success`, `failed`, `rejected`,
  `deferred`. The discriminator is `status`; consumers cannot guess a variant
  from whichever fields happen to exist.

### Answer to the unknown-field decision

The policy is explicit per boundary: contract DTOs reject unknown fields. An
envelope's `metadata` is the documented extension point: keys must be namespaced
`x-...`, bounded in number/length, and values are strings. Unknown payload fields
are never silently accepted.

### Answer to the version-every-call decision

Published contracts have a stable identity and version. Ordinary same-process
function calls do not carry a redundant version field; they use the typed DTO.
The envelope carries `contract_version` where durable/asynchronous/independent
deployment can coexist with older revisions.

## 5. Message envelope

`MessageEnvelope[PayloadT]` is used for events, queue/persisted messages,
cross-process communication and asynchronous workflows. It is not added to every
local function call.

| Field | Meaning |
|---|---|
| `message_id` | This message |
| `message_kind` | request/response/command/event/stream |
| `message_type` | lower-case dot identity, e.g. `waxprep.operation.result` |
| `contract_version` | strict `major.minor.patch` of the payload contract |
| `correlation_id` | one logical operation across components |
| `causation_id` | the message that caused this one (optional) |
| `created_at` | UTC, timezone-aware |
| `producer` | bounded originating component identity |
| `payload` | typed contract DTO |
| `metadata` | `x-` namespaced, bounded string map |

HTTP request IDs remain a transport concern and are not substituted for
`message_id`, `correlation_id` or `causation_id`.

## 6. Communication patterns

Request/response, command, event and streaming are distinct. They share contract
conventions, not one universal method. A streaming protocol exists, but no
streaming transport is implemented because no component needs one yet. A command
is a request for something to happen; an event states that something happened.

## 7. Validation and safety

`validate_contract` accepts only text/bytes and enforces:

- payload size limit (default 256 KiB);
- JSON only — never pickle/marshal/arbitrary Python objects;
- no NaN/Infinity;
- no duplicate JSON keys;
- bounded nesting depth (default 32) and item count (default 10,000);
- UTF-8 validity, including rejecting lone surrogates;
- strict Pydantic validation;
- sanitized errors (location + type only; no input values).

`dump_contract` serializes through Pydantic, uses deterministic sorted JSON,
rejects non-finite values, and re-checks the size limit.

`ValidationLimits` centralizes the bounds. These controls apply even to data from
another internal component: components can contain bugs.

## 8. Errors

Contract failures use Stage 15 types and codes:

| Failure | Code | Category | Retryable |
|---|---|---|---|
| `ContractValidationError` | WAX-5001 | validation | no |
| `ContractVersionError` | WAX-5002 | validation | no |
| `ContractSerializationError` | WAX-5003 | internal invariant | no |
| `ContractViolationError` | WAX-5004 | programming defect | no |

External malformed data is a validation failure, not automatically a programming
defect. An internal component bypassing a guaranteed contract is a violation.

## 9. Schema publication

`ContractSchemaRegistry` produces deterministic JSON Schema Draft 2020-12 with a
stable `$id` per identity. Committed schemas live in `contracts/schemas/`:

- `manifest.json` lists the current name/version/file;
- each contract has one `name@version.schema.json`;
- a version bump adds a new file; old schema files are not overwritten.

CI runs `python -m waxprep.contracts.cli check --schemas contracts/schemas`.
Model changes without regenerated schemas fail the gate. `generate` rewrites the
current files; review the diff before committing.

## 10. Compatibility and versioning

See `CONTRACT_EVOLUTION.md`. Structural changes are classified by
`compare_schemas`; semantic meaning changes are never auto-classified as safe and
must be treated as major. A change being accepted by Python is not evidence of
compatibility.

## 11. Adding a real contract

1. Define a `ContractModel` (or a documented `RootModel` union) with bounded
   fields and semantic docstrings.
2. Add a stable identity and initial `1.0.0` version to `build_default_registry`.
3. Add contract tests: valid/invalid data, serialization round-trip, limits,
   adversarial input and property tests.
4. Generate schemas: `uv run python -m waxprep.contracts.cli generate`.
5. Commit the model, tests, schema files and manifest.
6. For a change, run `compat` against the previous schema and record the
   compatibility decision.

## 12. Prohibited / deferred

Not adopted: MCP as the internal protocol, Protocol Buffers, Avro, Kafka,
RabbitMQ, Redis messaging, microservices, CloudEvents runtime dependency,
AsyncAPI runtime dependency, Schemathesis (no public HTTP contract yet).
These remain future options when distribution or external exposure justifies
them.

The envelope borrows CloudEvents-style metadata discipline without adding a
dependency. AsyncAPI/CloudEvents documents can describe future external
interfaces; they are not runtime dependencies.

## 13. Verification

- `tests/contract/` covers models, envelope, validation, versioning,
  compatibility, schema registry, CLI, protocols, properties and adversarial
  input.
- `make check` includes the schema drift check and Semgrep rules against
  `model_construct`/`model_copy(update=...)` bypasses.
- Import-linter keeps `contracts/` inner-layer.
