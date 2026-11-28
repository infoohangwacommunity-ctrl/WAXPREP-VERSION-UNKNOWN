# Engineering Standards — WaxPrep

> **Philosophy:** Standards are guardrails, not bureaucracy. The goal is readable, consistent, safe code that stays flexible as real channels, context, and teaching logic arrive later.

> **Land Not House:** We are creating land, not a finished house with pre-built rooms. Unrelated components must not become tightly coupled. Clear boundaries protect flexibility.

This document captures the engineering standards for the WaxPrep codebase. It is informed by production Python/FastAPI practice and the specific needs of this multi-channel AI tutoring system.

---

## Table of Contents

1. [Philosophy](#philosophy)
2. [Naming Conventions](#naming-conventions)
3. [File Organization](#file-organization)
4. [Type Safety](#type-safety)
5. [Error Handling](#error-handling)
6. [Documentation](#documentation)
7. [Architecture Boundaries](#architecture-boundaries)
8. [Adding New Components](#adding-new-components)
9. [Testing Standards](#testing-standards)
10. [Code Quality Tools](#code-quality-tools)
11. [PR Review Checklist](#pr-review-checklist)

---

## Philosophy

### Guardrails, Not Bureaucracy

Standards exist to:
- Make code readable quickly
- Catch type errors and bad imports early
- Handle errors consistently
- Enable new components without breaking flexibility

They do NOT exist to:
- Add unnecessary ceremony
- Lock the product into rigid categories
- Force premature structure

### Land Not House

- The AI must learn the student over time
- We must not force students into permanent categories or rigid conversational paths
- Channels, models, and tools must stay swappable
- Unrelated components must not become tightly coupled

### Dependency Direction

**Outer → Inner. Never the reverse.**

```
messaging/ ──→ core/, registries/
context/   ──→ core/
services/  ──→ core/, messaging/, context/, registries/
main.py    ──→ services/, messaging/, registries/, middleware/
adapters/  ──→ registry protocols (NOT core/)
registries/ ──→ base, typing
core/      ──→ Nothing from waxprep (pure logic only)
```

---

## Naming Conventions

### Rules

| Element | Convention | Example |
|---------|------------|---------|
| Packages & modules | `snake_case` | `core/`, `protocols.py`, `request_id.py` |
| Classes | `PascalCase` | `BaseRegistry`, `MessageHandler`, `FakeChannelAdapter` |
| Functions & variables | `snake_case` | `get_context`, `register_defaults`, `correlation_id` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT` |
| Protocols | Clear noun or `XxxAdapter` | `Message`, `ChannelAdapter`, `ContextProvider` |
| Type variables | Single letter or descriptive | `T`, `MsgT`, `AdaptT` |

### Prohibited Names

**Never** name packages, modules, or components after:

- Student types (e.g., `beginners`, `advanced`, `novice`)
- Academic levels (e.g., `high_school`, `college`)
- Subjects (e.g., `math`, `science`)
- Ability categories (e.g., `gifted`, `remedial`)

**Do** name packages after **architectural roles**:

- ✅ `core/` - Pure logic
- ✅ `messaging/` - Message handling
- ✅ `context/` - Understanding the learner
- ✅ `services/` - Orchestration
- ✅ `registries/` - Registration/lookup
- ✅ `adapters/` - External integrations

---

## File Organization

### One Clear Responsibility Per File

Each file should have a single, clear purpose.

```python
# ✅ GOOD: protocols.py - Only contains protocol definitions
# ✅ GOOD: pure.py - Only contains pure functions
# ❌ AVOID: utils.py - Contains everything
```

### Keep `__init__.py` Thin

`__init__.py` files should:
1. State boundary rules
2. Re-export public API
3. State what the package allows/disallows

```python
"""
core/ package

Purpose: Pure domain logic and protocols.

Boundary rules:
- ONLY standard library imports allowed
- NO imports from waxprep.adapters, waxprep.channels, or any infrastructure
- NO FastAPI, SDKs, or external dependencies

Imported by:
- messaging/, context/, services/ (outer layers)
"""
```

### Tests Mirror Package Structure

For `src/waxprep/foo/bar.py`, tests go in `tests/test_foo_bar.py` or `tests/foo/test_bar.py`.

---

## Type Safety

### Strict Settings

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.14"
strict = true

[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
```

### All Public Functions Need Full Type Annotations

```python
# ✅ GOOD
def get_item(name: str) -> T:
    """Get a registered item by name."""
    ...

def normalize_text(text: str, options: NormalizeOptions | None = None) -> str:
    """Normalize text content."""
    ...

# ❌ AVOID
def get_item(name):
    ...
```

### Prefer Protocol for Boundaries

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ChannelAdapter(Protocol):
    """Adapter protocol for message channels."""

    async def send(self, message: str) -> bool:
        """Send a message. Returns True on success."""
        ...

    async def receive(self) -> str | None:
        """Receive a message."""
        ...
```

### Use Pydantic for Structured Data Crossing Boundaries

```python
from pydantic import BaseModel, Field

class MessageReceived(BaseModel):
    """Incoming message data from a channel."""
    content: str = Field(..., description="Message content")
    timestamp: int = Field(..., description="Unix timestamp")
    metadata: dict[str, str] = Field(default_factory=dict)
```

### Avoid Bare `Any`

Use `Any` only with documented reason:

```python
# ✅ Documented reason
def process(data: Any) -> None:  # Implementation-specific
    ...

# ❌ AVOID
def handle(data: Any) -> None:
    ...
```

---

## Error Handling

### Never Leak Stack Traces

```python
import structlog
from fastapi import Request

logger = structlog.get_logger()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        error=str(exc),
        correlation_id=request.headers.get("X-Request-ID", "unknown"),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )
```

### Prefer Specific Exceptions

```python
# ✅ GOOD
class AdapterNotRegisteredError(KeyError):
    """Raised when an adapter is not found in the registry."""

def get_adapter(name: str) -> ChannelAdapter:
    if name not in self._items:
        raise AdapterNotRegisteredError(f"No adapter registered: {name}")
    return self._items[name]

# ❌ AVOID
try:
    something()
except Exception:
    handle()
```

### Error Classification

| Error Type | Status Code | Action |
|------------|-------------|--------|
| Validation errors | 422 | Return structured validation errors |
| Not found | 404 | Return clear "not found" message |
| Conflict | 409 | Return conflict details |
| Unexpected errors | 500 | Log full details, return generic message |

### Configuration Errors

Configuration validation failures must not expose secret values.

```python
from pydantic import ValidationError
from waxprep.config import Settings

try:
    settings = Settings()
except ValidationError as exc:
    # Log the error details server-side
    logger.error("Configuration validation failed", errors=exc.errors())
    # Exit with a clear message that does not leak secrets
    sys.exit("Application configuration is invalid. Check environment variables.")
```

Configuration error messages reference the field name and the validation rule violated.
They do not include the invalid value if the value could be sensitive.

---

## Documentation

### Every `__init__.py` States Boundary Rules

```python
"""
core/ package

Purpose: Pure domain logic and protocols.

Boundary rules:
- ONLY standard library imports allowed
- NO imports from waxprep.adapters, waxprep.channels, or any infrastructure
- NO FastAPI, SDKs, or external dependencies

Dependencies:
- Nothing from waxprep (this package is pure)

Imported by:
- messaging/, context/, services/ (outer layers)
"""
```

### Public Functions Get Short Docstrings

Docstrings explain **why** and **what**, not just **how**:

```python
def extract_keywords(text: str) -> list[str]:
    """
    Extract significant keywords from text for intent matching.

    Uses simple whitespace tokenization. Does NOT perform
    stemming or lemmatization.

    Args:
        text: Input text to process

    Returns:
        List of keyword strings
    """
```

### README is Source of Truth

The README.md contains:
- Current stage and scope
- Package structure
- Boundary rules
- What is NOT included (later stages)

Update README.md when architecture changes.

---

## Architecture Boundaries

### Dependency Direction: Outer → Inner

```
interfaces/      (outermost - adapters, HTTP, CLI)
     ↓
infrastructure/  (external services, DB, messaging)
     ↓
application/     (use cases, orchestration)
     ↓
domain/          (innermost - pure business logic)
```

### What Each Package May Import

| Package | May Import From | May NOT Import From |
|---------|-----------------|---------------------|
| `core/` | standard library only | adapters, channels, FastAPI, SDKs, any `waxprep.*` |
| `messaging/` | `core/`, `registries/` | concrete adapters, direct SDKs, `context/`, `services/` |
| `context/` | `core/` | `messaging/`, `services/`, concrete adapters |
| `services/` | `core/`, `messaging/`, `context/`, `registries/` | (composition root) |
| `main.py` | FastAPI, config, registries, middleware, adapters | `core/` (framework-agnostic) |
| `adapters/` | registry protocols, SDKs | `core/`, other adapters |

### Boundary Test Examples

```python
# tests/test_boundaries.py
def test_core_does_not_import_adapters():
    """Core must not import from adapters package."""
    # Scan core/ files for forbidden imports
    ...

def test_messaging_does_not_bypass_registries():
    """Messaging must use registries, not import adapters directly."""
    ...
```

---

## Adding New Components

### Checklist

**Architecture Fit**
- [ ] Does it fit an existing package, or does it need a new one?
- [ ] Does it respect the Outer → Inner dependency direction?
- [ ] Does it avoid student categories/hardcoded domains?

**Registration (if an adapter)**
- [ ] Is it registered through the appropriate registry?
- [ ] Does it implement the correct protocol?
- [ ] Is registration explicit (not import-time side effects)?

**Type Safety & Documentation**
- [ ] Are types fully annotated on all public functions?
- [ ] Does it use `Protocol` for boundaries?
- [ ] Is there a docstring explaining why and what?
- [ ] Does `__init__.py` state boundary rules if it's a new package?

**Testing**
- [ ] Is there at least one test?
- [ ] Does the test prove the component works correctly?
- [ ] Do tests mirror the package structure?

**No Hardcoding**
- [ ] Are all configuration values from environment or fixtures?
- [ ] Is there any hardcoded model name, API key, port, timeout, etc.?

---

## Testing Standards

### Run All Tests

```bash
uv run pytest
```

### Run with Coverage

```bash
uv run pytest --cov=waxprep --cov-report=term-missing
```

### Test Naming

- Tests for `src/waxprep/foo/bar.py` → `tests/test_foo_bar.py`
- Test functions: `test_<function_name>_<scenario>`

```python
def test_register_adds_item():
    """register() adds the item to the registry."""
    ...

def test_get_raises_key_error_for_missing():
    """get() raises KeyError when item not found."""
    ...
```

### Test Types

- **Unit tests**: Test individual functions/classes
- **Integration tests**: Test component interactions
- **Boundary tests**: Prove packages respect import rules

---

## Code Quality Tools

### Linting

```bash
# Check for issues
uv run ruff check src/ tests/

# Auto-fix what can be fixed
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Type Checking

```bash
uv run mypy src/
# Or with pyright
uv run pyright src/
```

### Pre-commit Checklist

Before pushing:

- [ ] Tests pass: `uv run pytest`
- [ ] Type check passes: `uv run mypy src/`
- [ ] Linting clean: `uv run ruff check src/`
- [ ] Code formatted: `uv run ruff format src/`
- [ ] No hardcoded values introduced
- [ ] README/boundary docs updated if architecture changed

---

## 11. Stage 16: Application Lifecycle

- One authoritative lifecycle state per application instance; do not introduce
  independent booleans that decide readiness or cleanup.
- Resources must have a named owner, an `initialize` callable, an optional
  `release` callable and explicit `depends_on` entries.
- Register cleanup through the lifecycle manager; never release a resource from
  two places.
- Mandatory startup failure must roll back every acquired resource and re-raise
  the original exception. Cleanup failure must not replace it.
- Cleanup is failure-isolated: one failed release must not prevent the rest.
- Cancellation is recorded, cleanup still runs, and `CancelledError` propagates.
- Background tasks must be started through `BackgroundTaskSupervisor`; direct
  `asyncio.create_task`/`ensure_future` in `src/` is rejected by Semgrep and the
  AST ownership test.
- Readiness returns 200 only in `READY`; optional degradation must not block a
  mandatory app.
- New timeouts belong in `LifecycleTimeouts`; do not scatter literals.
- Importing a module or calling `create_app()` must not acquire resources or
  start tasks.
- Add rollback, cleanup-failure and cancellation tests for every new resource
  owner.

---

## 12. Stage 17: Internal Communication Contracts

- Published communication data uses strict, frozen `ContractModel` DTOs. Do not
  pass arbitrary dicts across a defined contract boundary.
- One authoritative definition per interface. Do not duplicate
  `core/protocols.py` or registry protocols in `contracts/`.
- Request, command, event and streaming semantics stay distinct; do not add one
  universal component interface.
- Envelopes are for durable/asynchronous/cross-process messages, not every local
  call. Message, correlation and causation IDs are distinct from HTTP request IDs.
- Contract DTOs reject unknown fields and mutable fields; envelope metadata is
  the only namespaced, bounded, immutable extension point.
- Discriminators are required, not defaulted, so generated schemas and runtime
  validation agree.
- Validate untrusted bytes with `validate_contract` (size, JSON-only, depth,
  duplicate keys, finite numbers, safe errors). Never deserialize arbitrary
  Python objects.
- Contract failures use the Stage 15 taxonomy; external malformed data is not
  automatically a programming defect.
- A contract change requires a compatibility decision: regenerate schemas and
  pass the CI baseline enforcement. Breaking changes need a major increment;
  conditional changes need a decision entry; published versions are immutable.
- Never hand-edit `contracts/schemas/`; never overwrite a historical schema file.
- No transport/framework (Kafka, RabbitMQ, Redis, MCP, Protobuf, CloudEvents
  runtime) unless a real distribution requirement justifies it.

---

## 13. Stage 18: Dependency Injection and Composition

- One authoritative composition root. Do not scatter concrete implementation
  selection across lifecycle callbacks, modules or components.
- Declare dependencies explicitly in `ProviderSpec`/constructors. No global
  service locator, string-keyed container or hidden `resolve()` calls.
- Components never import `waxprep.composition`; inner packages receive values.
- Provide a typed bundle, not one enormous universal container or arbitrary
  dictionary.
- Declare a lifetime. A longer-lived provider cannot depend on a shorter one.
  Request/operation scopes stay policy-only until a real component exists.
- Stage 16 remains the only lifecycle manager. Composition runs as a component;
  do not add a second startup/shutdown system.
- Select concrete adapters in composition. Production code must not call
  `register_defaults()` or import concrete adapters outside the allowed paths.
- Test overrides are explicit `CompositionRoot` values, not monkey-patched
  globals.
- A composition failure must roll back through Stage 16 and expose no partial
  bundle.
- Add graph, isolation, override, lifetime, failure and static-boundary tests for
  every new provider or bundle.

---

## 14. Stage 19: Background Execution

- Submit work through `BackgroundRuntime`; components must not import Taskiq or a
  broker package.
- Register handlers through `JobRegistry` by stable task identity. Do not add a
  fixed business-job catalogue to the infrastructure.
- Job payloads cross a process boundary: use validated Stage 17 envelopes,
  bounded JSON, correlation/causation IDs and safe failure results.
- Handlers must tolerate duplicate delivery; the foundation does not advertise
  exactly-once execution.
- Do not add a custom queue, broker, scheduler, worker framework or hardcoded
  retry/error list. Use the framework's broker/middleware extension points.
- Worker startup uses the Stage 18 composition root and Stage 16 lifecycle; it
  must not import FastAPI or create a second container/lifecycle.
- Application startup must work without a worker; the background component is
  optional and degrades to an unavailable submitter when the extra is absent.
- Concrete broker selection stays in composition; the default in-memory broker
  is for foundation tests, not a production delivery guarantee.
- Add submission, execution, validation, failure, lifecycle, isolation and static
  boundary tests for every new handler or runtime.

---

## PR Review Checklist

See [PR_REVIEW_CHECKLIST.md](PR_REVIEW_CHECKLIST.md) for the concise, actionable checklist.

### Quick "Smell Test" Questions

1. **Could this be tested without any infrastructure?** (If yes, it belongs in `core/`)
2. **Does this file know about a concrete adapter?** (If yes and it's not in `services/`, problem)
3. **Could I swap this component without touching other code?** (If no, coupling may be too tight)
4. **Is there anything hardcoded that should be config?** (If yes, flag it)
5. **Does this add a new dependency direction?** (If yes, verify it follows Outer→Inner)

---

## Questions?

Open an issue for:
- Architecture questions
- Boundary rule clarifications
- Feature proposals

For quick questions, check:
- [README.md](README.md) - Source of truth for current state
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guide
- Existing tests - Show intended behavior
