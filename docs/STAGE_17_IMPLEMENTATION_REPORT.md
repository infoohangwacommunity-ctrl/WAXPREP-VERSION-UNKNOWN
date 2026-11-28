# Stage 17 Implementation Report — Internal Communication Contracts

**Base:** `be2f740` (main).
**Scope:** contract-first typed communication machinery, schema publication,
validation, versioning/compatibility, testing and enforcement.
**Transport:** none added. WaxPrep remains a modular monolith.

---

## 1. What was implemented

| Area | Result |
|---|---|
| Interface layer | Generic typed Protocols for request, command, event and streaming capabilities |
| Data contracts | Strict, frozen `ContractModel`; `ErrorDetail`; discriminated `OperationResult` variants |
| Envelope | Versioned `MessageEnvelope[PayloadT]` with correlation/causation identity and bounded metadata |
| Validation | Size/depth/item limits, JSON-only parsing, duplicate-key/NaN/surrogate rejection, strict Pydantic validation, sanitized errors |
| Serialization | Deterministic JSON output, size re-check, non-finite rejection |
| Versioning | Strict semantic versions, contract identity, compatibility policy/comparator |
| Schema | Deterministic Draft 2020-12 generation, manifest, historical files, drift check |
| Errors | Contract failures mapped to Stage 15 taxonomy (WAX-5001..5004) |
| CLI | `generate`, `check`, `compat`, `list` |
| Enforcement | CI schema drift step, import-linter contract, Semgrep bypass rules, AST check |

## 2. Architectural decisions

1. **Do not duplicate existing interfaces.** `core/protocols.py` and registry
   protocols remain authoritative for their current boundaries. New generic
   capability Protocols do not replace them.
2. **Contract package is inner-layer.** It may import the error taxonomy and
   Pydantic; import-linter forbids adapters, registries, middleware, config,
   lifecycle, observability and the app.
3. **Strict/frozen/forbid by default.** No implicit conversion, mutation or
   silent unknown fields. Extensions are explicit revisions; envelope metadata is
   the only namespaced, bounded extension point.
4. **Discriminated results.** `OperationResult` uses a `status` discriminator and
   explicit success/failure/rejected/deferred variants.
5. **No universal component interface.** Request, command, event and streaming
   semantics stay distinct.
6. **Versioning only where coexistence is possible.** Published contracts have
   identities/versions; local typed calls do not carry redundant version fields.
7. **Schemas are committed evidence.** A model change without regenerated
   schema files fails CI.
8. **No transport.** No Kafka/RabbitMQ/Redis/CloudEvents/MCP/Protobuf/AsyncAPI
   runtime dependency was introduced.

## 3. Answers to the specification decisions

- **Unknown fields:** rejected in contract DTOs; envelope metadata is bounded and
  `x-` namespaced. No global ignore policy.
- **Version on every call:** no. Envelope carries version where durable or
  cross-process communication can coexist; local DTOs do not.
- **One universal interface:** no. Four separate capability Protocols.
- **Existing protocols:** retained in place; not copied into contracts.
- **Schema format:** JSON Schema Draft 2020-12 generated from Pydantic.
- **Immutability:** frozen contract models.
- **Errors:** Stage 15 taxonomy; external validation failures vs internal
  violations are distinct.
- **Correlation:** envelope has message/correlation/causation IDs; HTTP request
  IDs stay transport-level.
- **Transport:** in-process only.

## 4. Added files

**Source**
```
src/waxprep/contracts/__init__.py
src/waxprep/contracts/cli.py
src/waxprep/contracts/envelopes.py
src/waxprep/contracts/errors.py
src/waxprep/contracts/interfaces.py
src/waxprep/contracts/schema.py
src/waxprep/contracts/validation.py
src/waxprep/contracts/versioning.py
src/waxprep/contracts/models/__init__.py
src/waxprep/contracts/models/base.py
src/waxprep/contracts/models/result.py
contracts/README.md
contracts/schemas/manifest.json
contracts/schemas/waxprep.error.detail@1.0.0.schema.json
contracts/schemas/waxprep.operation.result@1.0.0.schema.json
```

**Tests**
```
tests/contract/test_contract_models.py
tests/contract/test_envelopes.py
tests/contract/test_validation.py
tests/contract/test_versioning.py
tests/contract/test_schema_registry.py
tests/contract/test_cli.py
tests/contract/test_interfaces.py
tests/contract/test_contract_properties.py
tests/contract/test_contract_adversarial.py
tests/contract/test_stage17_static.py
```

**Docs**
```
docs/INTERNAL_COMMUNICATION_CONTRACTS.md
docs/CONTRACT_EVOLUTION.md
docs/CONTRACT_TESTING.md
docs/STAGE_17_IMPLEMENTATION_REPORT.md
```

**Modified**
```
.github/workflows/quality-gate.yml  contract schema drift step
.importlinter                       contract isolation; core cannot import contracts
.semgrep/config.yml                 contract bypass rules
Makefile, justfile                  contracts target in check
README.md, docs/ARCHITECTURE_BOUNDARIES.md,
docs/ENGINEERING-STANDARDS.md, docs/PR_REVIEW_CHECKLIST.md,
tests/README.md, tests/architecture/test_boundaries.py, pyproject.toml
```

## 5. Test coverage

| Layer | Cases |
|---|---|
| Models | strict/frozen/extra policy, four result variants, bounded detail, safe error detail |
| Envelope | valid round-trip, UTC normalization, invalid identity/version/producer/kind, metadata allowlist, schema determinism |
| Validation | valid/invalid JSON, bytes/TypeAdapter, limits, duplicate keys, NaN/Infinity, unicode/surrogates, sanitized errors, deterministic output |
| Versioning | version/identity parsing and bumps, every change classification, refs, enums/consts, bounds, additionalProperties, variants, recursive refs |
| Schema | register/duplicate/unknown, manifest, deterministic documents, write, drift missing/changed, committed baseline |
| CLI | generate/check/list/compat, drift exit code, breaking exit code, module entrypoint |
| Protocols | request/command/event/stream compliance and missing-method rejection |
| Property | version round-trips, result variants, envelope round-trips, unknown fields, arbitrary text |
| Adversarial | deep nesting, size, duplicate keys, surrogates, injection strings, metadata bound |
| Static | no validation bypass; synthetic violations detected |

## 6. Local verification

| Gate | Result |
|---|---|
| `ruff check src/ tests/` | PASS |
| `ruff format --check src/ tests/` | PASS |
| `mypy src/` (strict) | PASS (73 files) |
| `import-linter` | 5 contracts kept |
| `contracts.cli check` | schemas in sync |
| Semgrep (12 rules) | 0 findings |
| Hardcoding detector | 0 blocking |
| Supply chain | PASSED |
| Workflow audit | PASSED |
| `uv lock --check` | PASS |
| `pytest` | **1218 passed, 1 skipped, 9 xfailed** |
| Coverage | **100.00%** (4,633 statements, 0 missed) |

## 7. Remaining limitations / deferred

- No concrete Tutor/Judge/Notebook/Context contracts exist because those
  components do not exist. The registry is ready for them.
- No streaming transport; only the typed capability Protocol.
- No external event transport or CloudEvents/AsyncAPI runtime; envelope follows
  the metadata discipline but remains an internal Pydantic model.
- The compatibility comparator covers the constructs used by current contracts
  (properties, required, types, enums/const, bounds, additionalProperties,
  variants, refs). New JSON Schema constructs need a comparator case and test
  before they are relied on.
- Semantic meaning changes cannot be auto-detected; they are documented as
  breaking and require a major version.
- No mutation-testing framework; the suite uses targeted adversarial and
  synthetic-violation tests.
- Schemathesis is deferred until a public HTTP contract exists.

## 8. CI evidence

Commit-bound runs are recorded after the push. Local green results are not a
substitute for GitHub Actions.
