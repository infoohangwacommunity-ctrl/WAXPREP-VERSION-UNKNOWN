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
src/waxprep/contracts/compatibility.py
src/waxprep/contracts/models/__init__.py
src/waxprep/contracts/models/base.py
src/waxprep/contracts/models/result.py
contracts/README.md
contracts/schemas/manifest.json
contracts/schemas/waxprep.error.detail@1.0.0.schema.json
contracts/schemas/waxprep.operation.result@1.0.0.schema.json
contracts/baseline/manifest.json
contracts/baseline/waxprep.error.detail@1.0.0.schema.json
contracts/baseline/waxprep.operation.result@1.0.0.schema.json
contracts/compatibility-decisions.toml
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
tests/contract/test_compatibility_enforcement.py
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
.github/workflows/quality-gate.yml  contract schema drift + compatibility steps
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
| Models | strict/frozen/deep-immutability policy, required status discriminator, four result variants, bounded detail, safe error detail |
| Envelope | valid round-trip, UTC normalization, invalid identity/version/producer/kind, metadata regex, FrozenDict mutation attempts, strict payload bound, schema determinism |
| Validation | valid/invalid JSON, bytes/TypeAdapter, limits, duplicate keys, NaN/Infinity, unicode/surrogates, sanitized errors, deterministic output |
| Versioning | version/identity parsing and bumps, every change classification, refs, enums/consts, bounds, additionalProperties, variants, recursive refs, unsupported constructs fail safely |
| Compatibility | baseline unchanged/new/removed/regressed, same-version rewrite, major-bump rule, conditional decisions, report output, CLI |
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
| `mypy src/` (strict) | PASS (74 files) |
| `import-linter` | 5 contracts kept |
| `contracts.cli check` / `enforce` | schemas in sync; compatibility passes |
| Semgrep (12 rules) | 0 findings |
| Hardcoding detector | 0 blocking |
| Supply chain | PASSED |
| Workflow audit | PASSED |
| `uv lock --check` | PASS |
| `pytest` | **1299 passed, 1 skipped, 9 xfailed** |
| Coverage | **100.00%** (4,888 statements, 0 missed) |

## 7. Remaining limitations / deferred

- No concrete Tutor/Judge/Notebook/Context contracts exist because those
  components do not exist. The registry is ready for them.
- No streaming transport; only the typed capability Protocol.
- No external event transport or CloudEvents/AsyncAPI runtime; envelope follows
  the metadata discipline but remains an internal Pydantic model.
- The compatibility comparator covers the constructs used by current contracts
  and fails safely on unsupported/unexamined constructs. A new JSON Schema
  construct still needs an explicit comparator case and test before a contract
  relies on it; until then it is reported as breaking, never silently compatible.
- Semantic meaning changes cannot be auto-detected; they are documented as
  breaking and require a major version.
- No mutation-testing framework; the suite uses targeted adversarial and
  synthetic-violation tests.
- Schemathesis is deferred until a public HTTP contract exists.

## 8. CI evidence

**Implementation commit:** `d750af6945eb08e9253f830d248bdabe949d03b0`.

| Workflow | Result | Run |
|---|---|---|
| CI — Quality Gate | success | https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/actions/runs/46089690810 |
| Dependency Security | success | https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/actions/runs/46089690798 |

The quality-gate run includes the new contract schema drift step, Semgrep
contract-bypass rules, import-linter contract isolation and the full contract
test suite. Local green results are not a substitute for these runs.

## 9. Correction pass (post-review)

The independent review accepted the architecture and required five corrections.
No transport or future product contracts were added.

### 9.1 Envelope metadata format

The declared `_METADATA_KEY` regex is now enforced with `re.fullmatch` for every
key: `x-` plus 1–32 lower-case letters, digits or hyphens. Tests cover uppercase,
whitespace, punctuation, empty suffixes, Unicode and valid forms.

### 9.2 Genuine immutability

- `FrozenDict` is the read-only metadata representation; every mutation method
  raises `TypeError`, and deep copies/pickling remain valid.
- `ContractModel` now rejects mutable list/dict/set values and arbitrary
  `BaseModel` fields at construction. Collections must be tuples/frozensets or
  nested frozen contract models.
- `ContractRootModel` is the frozen/strict base for RootModel unions; the
  envelope payload is bounded to `ContractModel | ContractRootModel`.
- Tests attempt metadata mutation, nested mutable payload fields, arbitrary
  Pydantic payloads and frozen-model assignment.

### 9.3 Required discriminator

Every `OperationResult` variant now requires `status` (no defaults). The
regenerated schemas list `status` in `required` with the correct `const`; tests
prove missing/invalid discriminators are rejected by Pydantic and that the
schema carries the same requirement.

### 9.4 Automatic compatibility enforcement

`contracts/compatibility.py` and `contracts.cli enforce` compare the current
registry with `contracts/baseline/`:

- same version + changed schema → forbidden unless an explicit decision;
- breaking change → requires a major version increment;
- conditional change → requires a decision in
  `contracts/compatibility-decisions.toml`;
- removal/version regression → forbidden without a decision;
- new contract → compatible addition;
- machine-readable report written to CI evidence.

The quality gate now runs both `check` (drift) and `enforce` (compatibility).
`contracts/baseline/` is the last accepted published set; historical schema
files are retained.

### 9.5 Comparator hardening

The comparator now fails safely for unsupported/unexamined constructs:

- missing/newly introduced `properties` sections;
- `pattern`/`format` changes;
- array `items` presence/schema/tuple changes;
- `uniqueItems` changes;
- `oneOf` ↔ `anyOf` changes;
- conditional/unsupported keywords (`if`, `then`, `else`, `allOf`, `not`,
  `contains`, `patternProperties`, etc.);
- unresolved reference changes;
- semantic keys (`default`, `discriminator`, `mapping`, `deprecated`,
  `readOnly`, `writeOnly`).

These are classified as `unsupported_change` or a semantic/validation change and
are breaking; an unexamined change is never silently compatible.

### 9.6 Correction files

```
src/waxprep/contracts/models/base.py        FrozenDict, deep immutability, ContractRootModel
src/waxprep/contracts/models/result.py      required status discriminators
src/waxprep/contracts/envelopes.py          metadata regex, FrozenDict, strict payload
src/waxprep/contracts/versioning.py         unsupported-change detection
src/waxprep/contracts/compatibility.py      baseline enforcement and report
src/waxprep/contracts/cli.py                enforce command
src/waxprep/contracts/interfaces.py         strict contract payload bounds
contracts/baseline/                         published baseline
contracts/compatibility-decisions.toml      explicit decision register
contracts/schemas/                          regenerated schemas
tests/contract/*                            metadata, immutability, discriminator,
                                            compatibility, comparator and CLI tests
docs/INTERNAL_COMMUNICATION_CONTRACTS.md    corrected policy
docs/CONTRACT_EVOLUTION.md                  baseline enforcement
docs/CONTRACT_TESTING.md                    correction verification
Makefile, justfile, quality-gate.yml        enforce in the gate
```

### 9.7 Correction results

Local suite: **1299 passed, 1 skipped, 9 xfailed**, **100% coverage (4,888
statements)**. The full `make check` gate passes, including schema drift,
baseline compatibility, Semgrep, import-linter and the full test suite.

### 9.8 Correction CI evidence

**Final correction commit:** `e33efc6b646e4b2147427e5a223401d2cf3f03b9`.

| Workflow | Result | Run |
|---|---|---|
| CI — Quality Gate | success | https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/actions/runs/46093842446 |
| Dependency Security | success | https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/actions/runs/46093842410 |

An intermediate correction commit (`0545a17`) passed every quality-gate job but
failed `CI Acceptance` because the compatibility report was written into
`ci-evidence/`, which the acceptance verifier treats as job evidence. The final
commit moves the report to `artifacts/contract-compatibility.json` and uploads
it as its own artifact; acceptance passes.

Both workflows above are bound to the final correction commit.
