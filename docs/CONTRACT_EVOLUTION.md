# Contract Evolution and Compatibility (Stage 17)

---

## 1. Identity

Published contracts use:

```
waxprep.<domain>.<purpose>@<major>.<minor>.<patch>
```

Example: `waxprep.operation.result@1.0.0`.

- Name: lower-case dot-separated, at least two segments.
- Version: strict semantic version; no leading zeroes, no `v` prefix.
- `ContractIdentity.parse("...")` rejects malformed identities.
- `$id` in the published schema is `urn:waxprep:contract:<name>:<version>`.

A schema revision is independent of the application release version.

## 2. Compatibility classes

| Class | Meaning | Deployment guidance |
|---|---|---|
| `compatible` | Existing producers/consumers continue to work | Patch/minor revision |
| `conditional` | Works only if the documented consumer policy handles the change | Minor revision + explicit consumer review |
| `breaking` | Old or new peer can fail or misinterpret data | Major revision and migration |

The comparator is conservative: if it cannot prove compatibility, it reports
conditional or breaking rather than assuming safety.

## 3. Change policy

| Change | Classification |
|---|---|
| Add optional field | compatible |
| Add a field and make it required | breaking |
| Existing optional field becomes required | breaking |
| Required field becomes optional | conditional |
| Remove a field | breaking |
| Change a field type | breaking |
| Add enum value | conditional |
| Remove/change enum value or `const` | breaking |
| Add a validation bound | breaking |
| Remove a validation bound | conditional |
| Relax `additionalProperties` | conditional |
| Restrict `additionalProperties` | breaking |
| Add a union variant | conditional |
| Remove a union variant | breaking |
| Change field meaning | breaking (manual) |
| Change serialization semantics | breaking (manual) |

Semantic changes cannot be detected from JSON Schema. A contract owner who
changes what a field means must record it as breaking and increment the major
version. Do not rely on the comparator to catch meaning changes.

## 4. Direction matters

Backward compatibility (new consumer reads old producer) and forward
compatibility (old consumer reads new producer) are different promises. The
comparator classifies the structural change; the owning contract must document
which direction it promises. A conditional result in CI requires an explicit
decision in the pull request.

## 5. Historical schemas

`schema.generate` writes `name@version.schema.json`. A version bump adds a file;
it does not rewrite an older one. Keep historical files so persisted/queued
messages can still be understood.

CI's `check` verifies that the current models match the current published files.
A manually edited schema or a model change without regeneration fails.

## 6. Migration

1. Publish the new major contract revision.
2. Keep the old revision readable for the documented retention window.
3. Translate at the boundary; never silently reinterpret old payloads.
4. Update producers and consumers independently.
5. Remove the old revision only after stored/queued data can no longer exist.
6. Record the migration and any data rewrite.

## 7. Automatic baseline enforcement

`contracts/baseline/` holds the last accepted published schema set.
`contracts/compatibility-decisions.toml` records reviewed exceptions and
conditional decisions.

The quality gate runs `waxprep.contracts.cli enforce` and fails when:

- a published version is modified without an explicit exception;
- a breaking change does not increment the major version;
- a conditional change has no explicit decision;
- a contract is removed or its version regresses without a decision;
- the baseline manifest/schema set is missing or malformed.

New contracts are compatible additions. The command writes a machine-readable
report (`ci-evidence/contract-compatibility.json` in CI).

## 8. CLI

```bash
# Publish current schemas
uv run python -m waxprep.contracts.cli generate

# Verify committed schemas match models (CI)
uv run python -m waxprep.contracts.cli check --schemas contracts/schemas

# Enforce compatibility against the published baseline (CI)
uv run python -m waxprep.contracts.cli enforce \
  --baseline contracts/baseline \
  --decisions contracts/compatibility-decisions.toml \
  --report ci-evidence/contract-compatibility.json

# Compare an old and a new schema manually
uv run python -m waxprep.contracts.cli compat \
  --old contracts/schemas/waxprep.operation.result@1.0.0.schema.json \
  --new /tmp/new-operation-result.schema.json
```

`enforce` and `compat` exit non-zero for policy violations and print the
recommended semantic version bump.

## 9. Unsupported schema constructs

The comparator handles the constructs used by current contracts and explicitly
reports unsupported or unexamined structural changes as breaking. This includes
`if`/`then`/`else`, `allOf`, `not`, `contains`, `patternProperties`,
`prefixItems`, `dependentSchemas`, `patternProperties`, `oneOf`/`anyOf` swaps,
array `items` changes, `uniqueItems`, `pattern`/`format`, defaults,
discriminators and unresolved references. A new construct must get a comparator
case and test before a contract relies on it.

## 8. Deprecation

Mark a field deprecated in the model/schema description before removal. A
deprecated field is still part of the contract; removal is a breaking change.
There is no silent deprecation path.

## 9. Compatibility tests

`tests/contract/test_versioning.py` covers every structural change class,
reference resolution, enum/const changes, bounds, additional properties,
discriminated variants and recommended bumps. Add a case for each new class of
schema construct before relying on the comparator for that construct.
