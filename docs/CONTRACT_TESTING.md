# Contract Testing (Stage 17)

---

## 1. Layers of verification

| Layer | Tool | What it proves |
|---|---|---|
| Static types | mypy strict | Method signatures and field types |
| Runtime validation | Pydantic | Actual data structure and semantic rules |
| JSON Schema | schema registry + drift check | Published schema matches the model |
| Interface compliance | Protocol tests | Implementations expose required methods |
| Property-based | Hypothesis | Round-trips and invariants across generated data |
| Compatibility | `compare_schemas` tests | Structural changes obey policy |
| Adversarial | hand-written attacks | Malformed/oversized/hostile input is rejected safely |
| Architecture | import-linter + boundary tests | Contracts stay at the inner boundary |
| Bypass | Semgrep + AST test | No validated-model construction bypass |
| Drift | CI schema check | A model change cannot skip publication |

## 2. Required scenarios

- Correct data is accepted and round-trips.
- Missing required fields, invalid types, invalid enum/const values rejected.
- Unknown fields rejected; envelope metadata allowlist enforced.
- Invalid identifiers/versions/names rejected.
- Oversized payloads and outputs rejected.
- Deep nesting and excessive item counts rejected.
- Duplicate JSON keys, NaN/Infinity and lone surrogates rejected.
- Serialization is deterministic and preserves meaning.
- Validation errors contain locations/types, never raw input values.
- Every implementation satisfies the same Protocol contract.
- Version changes follow the compatibility policy.
- Breaking changes are detected.
- Cancellation/timeout results are represented, not invented as strings.
- Sensitive information is not exposed through errors.

## 3. Properties

`tests/contract/test_contract_properties.py` uses Hypothesis to generate:

- semantic versions and verify parse/bump round-trips;
- every operation-result variant and verify JSON round-trip;
- envelope payload round-trips;
- arbitrary unknown fields are rejected;
- arbitrary text is preserved in a valid string field without crashing.

## 4. Adversarial tests

`tests/contract/test_contract_adversarial.py` covers deep nesting, size limits,
duplicate keys, non-finite numbers, lone surrogates, unknown fields, injection
strings, Unicode/control characters, oversized output and unbounded metadata.

## 5. Structural checks

- `tests/architecture/test_boundaries.py` — `contracts/` cannot import outer
  layers; `core/` cannot import contracts.
- `tests/contract/test_stage17_static.py` — no `model_construct`, `construct`,
  `model_copy(update=...)` or `strict=False` validation bypass in `src/`.
- Semgrep rule `waxprep-contract-bypass-model-construction` enforces the same.
- `tests/contract/test_schema_registry.py` verifies committed schemas are in sync.

## 6. Running

```bash
# Contract suite
uv run pytest tests/contract -v -m contract

# Schema drift (also part of make check)
uv run python -m waxprep.contracts.cli check --schemas contracts/schemas

# Full gate
make check
```

## 7. Mutation-style check

The suite deliberately feeds structurally invalid variants and asserts rejection,
and `test_stage17_static.py` includes synthetic snippets that must be detected.
This is a lightweight mutation check; it does not claim a full mutation-testing
framework. A dedicated mutation tool can be added later without changing the
contracts.

## 8. Coverage is not proof

100% line coverage is required by the gate, but correctness comes from the
inventories above: invalid variants, limits, property round-trips, compatibility
classification and adversarial inputs. A green coverage number with no hostile
input tests would not satisfy Stage 17.
