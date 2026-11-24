# PR Review Checklist — WaxPrep

Quick checklist for reviewers. Check each item before approving.

---

## 1. Naming Conventions

- [ ] **Files:** `snake_case.py` for modules, `PascalCase.py` only for CLI entry points
- [ ] **Classes:** `PascalCase` (e.g., `ChannelRegistry`, `FakeChannelAdapter`)
- [ ] **Functions/methods:** `snake_case` (e.g., `handle_message`, `register_defaults`)
- [ ] **Variables:** `snake_case`; avoid single-letter names except loop indices
- [ ] **Constants:** `UPPER_SNAKE_CASE` (e.g., `DEFAULT_REGISTRY_NAME`)
- [ ] **Private members:** prefix with `_` (e.g., `_items`, `_shutting_down`)
- [ ] **Protocol names:** end with `Adapter` or descriptive noun (e.g., `ChannelAdapter`, `ModelGenerator`)
- [ ] **Test files:** `test_<module>.py`; test classes `Test<Subject>`

---

## 2. File Organization

- [ ] **Layer placement correct:**
  - `core/` — pure logic, protocols, value objects (no infrastructure imports)
  - `messaging/` — message handling, routing (depends on core + registries only)
  - `context/` — learner state, stores (depends on core only)
  - `services/` — composition root, wiring (only place knowing concrete adapters)
  - `adapters/` — channel/model/tool implementations (implement protocols)
  - `registries/` — registration/lookup (define protocols, don't import adapters except `register_defaults`)
- [ ] **One responsibility per file** — file does one thing; split if too broad
- [ ] **`__init__.py` re-exports only what outer layers need** — use `__all__`
- [ ] **No nested packages deeper than needed** — keep flat where possible

---

## 3. Type Annotations

- [ ] **All public functions have type hints** — parameters and return types
- [ ] **Use `Protocol` for capability contracts** — not abstract base classes
- [ ] **`@runtime_checkable` on protocols** that need `isinstance` checks
- [ ] **Use `dataclass(frozen=True)` for immutable value objects** (e.g., messages)
- [ ] **Avoid `Any` unless truly necessary** — prefer specific types or `dict[str, Any]` for open schemas
- [ ] **Generics used correctly** — `BaseRegistry[T]` pattern preserved
- [ ] **`mypy --strict` passes** on changed files (check CI or run locally)

---

## 4. Error Handling

- [ ] **Use specific exception types** — `KeyError` for missing registry items, `ValueError` for invalid input
- [ ] **No bare `except:` or `except Exception:`** — catch specific errors
- [ ] **Registry `get()` raises `KeyError`** (not returning `None`) — preserves contract
- [ ] **Registry `register()` raises `ValueError`** for invalid adapters — fails fast
- [ ] **Errors include context** — message includes relevant identifiers (name, ID)
- [ ] **No silent failures** — if something fails, it should be visible
- [ ] **Async errors propagate** — don't swallow exceptions in async handlers

---

## 5. Documentation

- [ ] **Module docstrings** explain purpose and scope (what it does, what it doesn't)
- [ ] **Public classes/functions have docstrings** — at least one line describing purpose
- [ ] **Protocol docstrings** describe the contract, not implementation
- [ ] **Complex logic has inline comments** explaining *why*, not *what*
- [ ] **No outdated docstrings** — update when behavior changes
- [ ] **Exclusions are documented** — if something is explicitly NOT included, say so

---

## 6. Boundary Rules (Outer → Inner)

**The Golden Rule:** Dependencies flow inward. Inner layers MUST NOT import from outer layers.

| File Location | Can Import | Must NOT Import |
|---------------|------------|-----------------|
| `core/` | standard lib, typing | `adapters/`, `messaging/`, `services/`, FastAPI, SDKs |
| `context/` | `core/` | `messaging/`, `services/`, `adapters/`, infrastructure |
| `messaging/` | `core/`, `registries/` | `services/`, `adapters/` (use registries), SDKs, `context/` |
| `registries/` | `registries/base`, typing | `adapters/` (except `register_defaults`) |
| `adapters/` | registry protocols, SDKs | `core/`, other adapters |
| `services/` | everything | nothing (it's the outer layer) |

**Review checks:**
- [ ] Does `core/` import from `adapters/`? → **REJECT**
- [ ] Does `core/` import FastAPI or external SDKs? → **REJECT**
- [ ] Does `messaging/` import concrete adapters directly? → **REJECT**
- [ ] Does `messaging/` bypass registries? → **REJECT**
- [ ] Does `registries/` import adapters outside `register_defaults()`? → **REJECT**
- [ ] Does `adapters/` import from `core/`? → **REJECT**

---

## 7. Component Addition Checklist

When adding a new swappable component (channel, model, tool, store, etc.):

- [ ] **Protocol defined** in the correct layer (core or context, depending on type)
- [ ] **Protocol is minimal** — only what consumers need, not implementation details
- [ ] **Protocol uses `@runtime_checkable`** if `isinstance` checks are needed
- [ ] **Registry updated** (if component is registry-managed) — or new registry created
- [ ] **Fake/test implementation provided** — proves architecture works without real dependency
- [ ] **Composition root updated** — wires the component in `services/`
- [ ] **No hardcoded configuration** — all values from env vars or injected
- [ ] **Dependency direction preserved** — new component follows Outer→Inner rule
- [ ] **Swapability verified** — can replace with alternative without touching consumers

---

## 8. Tests

- [ ] **New public functionality has tests** — at least happy path + one edge case
- [ ] **Boundary tests included** if adding to `core/` or `context/` — proves no illegal imports
- [ ] **Contract tests for protocols** — verify implementations satisfy contracts
- [ ] **No test imports from outer layers into inner layers** — tests follow same rules
- [ ] **Tests are deterministic** — no flaky async tests, proper `pytest.mark.asyncio`
- [ ] **`test_boundaries.py` updated** if new boundary rules apply
- [ ] **CI passes** — `mypy`, `ruff`, `pytest` all green

---

## Quick "Smell Test" Questions

Ask these during review:

1. **Could this be tested without any infrastructure?** (If yes, it belongs in `core/`)
2. **Does this file know about a concrete adapter?** (If yes and it's not in `services/`, problem)
3. **Could I swap this component without touching other code?** (If no, coupling may be too tight)
4. **Is there anything hardcoded that should be config?** (If yes, flag it)
5. **Does this add a new dependency direction?** (If yes, verify it follows Outer→Inner)

---

## 9. Stage 08: Universal Hardcoding Detection

When modifying code in protected modules (`waxprep.messaging`, `waxprep.context`, `waxprep.services`):

- [ ] **No fixed-string comparisons against input** — WHD-001 (HIGH, blocking)
- [ ] **No vocabulary membership tests** — WHD-002 (HIGH, blocking)
- [ ] **No fixed if/elif decision trees** — WHD-003 (MEDIUM, review)
- [ ] **No regex phrase detection** — WHD-004 (MEDIUM, advisory)
- [ ] **No word-to-action dictionary lookups** — WHD-005 (MEDIUM, review)
- [ ] **No predetermined string responses** — WHD-007 (MEDIUM, review)
- [ ] **No hardcoded vocabularies** — WHD-008 (MEDIUM, review)

When modifying the detector itself (`src/waxprep/detector/`):

- [ ] **Detector syntax is valid Python 3** — exception syntax, type hints
- [ ] **CLI supports `--format` argument** — via argparse, not positional
- [ ] **Blocking findings return exit code 1** — verify in tests
- [ ] **Tests use meaningful assertions** — no `len(findings) >= 0` vacuous tests
- [ ] **Known limitations documented** — use `@pytest.mark.xfail` for unsupported patterns
- [ ] **Documentation updated** — DETECTOR_SPECIFICATION.md reflects actual implementation

When modifying Semgrep configuration (`.semgrep/config.yml`):

- [ ] **Rules validate with installed Semgrep version**
- [ ] **All intended rules load and execute**
- [ ] **False-positive exclusions verified**
- [ ] **No references to deleted rule files**

---

*Based on Stage 03 Architecture Guide and ARCHITECTURE_BOUNDARIES.md*
