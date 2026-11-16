# WaxPrep Engineering Standards

**Version:** 1.0.0  
**Date:** November 2026  
**Scope:** Python/FastAPI codebase at `/workspaces/WAXPREP-VERSION-UNKNOWN`

---

## Table of Contents

1. [Overview](#overview)
2. [What's Already Excellent](#whats-already-excellent)
3. [Naming Conventions](#naming-conventions)
4. [File Organization](#file-organization)
5. [Type Safety](#type-safety)
6. [Error Handling](#error-handling)
7. [Documentation Requirements](#documentation-requirements)
8. [Architectural Boundaries](#architectural-boundaries)
9. [Adding New Components](#adding-new-components)
10. [Testing Standards](#testing-standards)
11. [Tooling & Configuration](#tooling--configuration)
12. [Best Practices to Adopt](#best-practices-to-adopt)
13. [Quick Reference](#quick-reference)

---

## Overview

This document captures the engineering standards for the WaxPrep Python/FastAPI project. It synthesizes:

- **Existing patterns** already established in the codebase
- **Gaps** that need to be documented or addressed
- **Industry best practices** for Python/FastAPI projects

The codebase follows a **hexagonal/clean architecture** pattern with clear dependency direction: outer layers (adapters, main) depend on inner layers (core, registries), never the reverse.

---

## What's Already Excellent

The WaxPrep codebase demonstrates strong engineering practices that should be preserved and documented:

### 1. Architecture & Boundaries

| Practice | Evidence |
|----------|----------|
| **Clear dependency direction** | `ARCHITECTURE_BOUNDARIES.md` defines strict rules; `tests/test_boundaries.py` enforces them via AST scanning |
| **Protocol-based abstractions** | `core/protocols.py` uses `typing.Protocol` with `@runtime_checkable` for formality |
| **No import-time side effects** | Registries are empty at import; `register_defaults()` must be called explicitly |
| **Pure functions isolated** | `core/pure.py` contains I/O-free algorithms testable in isolation |

### 2. Configuration

| Practice | Evidence |
|----------|----------|
| **No hardcoded values** | `config.py` uses `pydantic-settings` with `WAXPREP_` prefix |
| **Environment-driven** | All config from environment, validated via Pydantic |

### 3. Observability

| Practice | Evidence |
|----------|----------|
| **Structured logging** | `structlog` configured with JSON renderer in `main.py` |
| **Correlation IDs** | `RequestIdMiddleware` generates/propagates `X-Request-ID`, binds to structlog context |
| **No stack trace leaks** | Exception handlers return sanitized JSON, log full details server-side |

### 4. Health Endpoints

| Practice | Evidence |
|----------|----------|
| **Liveness vs. Readiness distinction** | `/health/liveness` (process alive) vs. `/health/readiness` (dependencies ready) |
| **Explicit readiness checks** | Readiness verifies config, registries, and adapter registration |

### 5. Tooling

| Practice | Evidence |
|----------|----------|
| **Strict type checking** | `pyproject.toml` enables `mypy --strict` and `pyright` with `typeCheckingMode = "strict"` |
| **Linting** | `ruff` configured with line-length 100, target py314 |
| **Modern packaging** | `hatchling` build backend, `uv` for dependency management |

---

## Naming Conventions

### PEP 8 Compliance (Already Followed)

| Element | Convention | Examples in Code |
|---------|------------|------------------|
| **Modules/files** | `snake_case` | `request_id.py`, `fake_channel.py`, `pure.py` |
| **Functions/methods** | `snake_case` | `register_defaults()`, `get_channel_registry()`, `normalize_text()` |
| **Variables** | `snake_case` | `_channel_registry`, `request_id`, `shutting_down` |
| **Classes** | `PascalCase` | `RequestIdMiddleware`, `ChannelRegistry`, `FakeChannelAdapter` |
| **Protocols** | `PascalCase` + "Protocol" suffix | `ChannelAdapter`, `ModelAdapter`, `MessageHandler` |
| **Constants** | `UPPER_SNAKE_CASE` | *(none currently; future: `MAX_RETRIES`, `DEFAULT_TIMEOUT`)* |
| **Type variables** | Single uppercase letter | `T` in `base.py` |

### Guidelines

1. **Module names**: lowercase, descriptive, no underscores unless necessary for clarity
2. **Function names**: verb-first for actions (`register`, `handle`, `normalize`), noun-first for getters (`get_`, `list_`)
3. **Private members**: prefix with single underscore (`_items`, `_shutting_down`)
4. **Protocol names**: describe the role, not the implementation (`ChannelAdapter` not `WhatsAppAdapterProtocol`)

### Future Considerations

- **Exception classes**: `PascalCase` with "Error" or "Exception" suffix (`ConfigurationError`, `RegistryError`)
- **Pytest fixtures**: descriptive snake_case (`client`, `channel_registry`)
- **Environment variables**: `WAXPREP_` prefix (already established)

---

## File Organization

### Current Structure (Good)

```
src/waxprep/
├── __init__.py           # Package docstring + version
├── main.py               # FastAPI app, lifespan, exception handlers
├── config.py             # Pydantic Settings
├── middleware/
│   ├── __init__.py       # Re-exports
│   └── request_id.py     # Single responsibility
├── registries/
│   ├── __init__.py       # Re-exports all registries
│   ├── base.py           # Generic base class
│   ├── channel.py        # Channel protocol + registry
│   ├── model.py          # Model protocol + registry
│   └── tool.py           # Tool protocol + registry
├── adapters/
│   ├── __init__.py       # Re-exports fake adapters
│   ├── fake_channel.py   # Fake implementation
│   ├── fake_model.py     # Fake implementation
│   └── fake_tool.py      # Fake implementation
├── core/
│   ├── __init__.py       # Boundary rules documented
│   ├── protocols.py      # Domain protocols
│   └── pure.py           # Pure functions
├── messaging/            # Placeholder (Stage 03)
├── context/              # Placeholder (Stage 03)
└── services/             # Placeholder (Stage 03)

tests/
├── __init__.py
├── test_foundation.py    # App creation, health, middleware, exceptions
├── test_config.py        # Configuration tests
├── test_registries.py    # Registry behavior with fakes
├── test_boundaries.py    # Architectural boundary enforcement
└── test_main.py          # Main app tests
```

### Principles Established

| Principle | Implementation |
|-----------|----------------|
| **One responsibility per file** | Each file has a single clear purpose |
| **Thin `__init__.py`** | Re-exports only; no logic |
| **Tests mirror packages** | Test files correspond to source modules |
| **Boundary rules in `__init__.py`** | Each package's `__init__.py` documents what it can/cannot import |

### Gap: Test Structure Doesn't Fully Mirror Source

Currently, tests are flat in `tests/` rather than mirroring the `src/waxprep/` package structure. As the codebase grows, consider:

```
tests/
├── test_config.py
├── test_main.py
├── middleware/
│   └── test_request_id.py
├── registries/
│   ├── test_base.py
│   ├── test_channel.py
│   ├── test_model.py
│   └── test_tool.py
├── adapters/
│   ├── test_fake_channel.py
│   ├── test_fake_model.py
│   └── test_fake_tool.py
├── core/
│   ├── test_protocols.py
│   └── test_pure.py
├── test_boundaries.py  # Kept at top level (cross-cutting)
└── test_foundation.py  # Kept at top level (integration)
```

---

## Type Safety

### Current Configuration (Excellent)

```toml
# pyproject.toml
[tool.mypy]
python_version = "3.14"
strict = true

[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
```

### Practices in Use

| Practice | Evidence |
|----------|----------|
| **Strict mode** | Both mypy and pyright in strict mode |
| **Protocol types** | `typing.Protocol` with `@runtime_checkable` for duck-typed interfaces |
| **Generic base classes** | `BaseRegistry[ChannelAdapter]` uses TypeVar for type safety |
| **Explicit return types** | All functions have `-> ReturnType` annotations |
| **Avoid `Any` where possible** | Protocols use specific types; `Any` only in type aliases |

### Guidelines

1. **Never use `Any` for public APIs** — use `Protocol` or concrete types
2. **Type variables for generics** — `T = TypeVar('T')` for reusable containers
3. **Runtime-checkable protocols** — use `@runtime_checkable` when you need `isinstance()` checks
4. **Type aliases for complex types** — e.g., `MessageResult = Any` (document why `Any` is used)

### Future Considerations

- **Typed dictionaries** — use `TypedDict` for structured dict returns (e.g., message dicts)
- **Pydantic models for external boundaries** — request/response schemas at API boundaries
- **Type stubs for untyped dependencies** — create `*.pyi` files if needed

---

## Error Handling

### Current Implementation (Excellent)

**In `main.py`:**

```python
# HTTP exceptions - sanitized
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning("HTTP exception", status_code=exc.status_code, path=request.url.path)
    return JSONResponse(..., content={"detail": exc.detail if exc.detail else "HTTP error", ...})

# Validation errors - sanitized
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(...) -> JSONResponse:
    logger.warning("Validation error", ...)
    return JSONResponse(..., content={"detail": "Validation error", "errors": [...]})

# Unexpected exceptions - log full, return sanitized
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", ..., exc_type=type(exc).__name__)
    return JSONResponse(..., content={"detail": "Internal server error", ...})
```

**In `RequestIdMiddleware`:**

```python
try:
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
finally:
    structlog.contextvars.unbind_contextvars("request_id")
```

### Principles

| Principle | Implementation |
|-----------|----------------|
| **Never leak stack traces** | Clients see `{"detail": "..."}` not tracebacks |
| **Log full details server-side** | `logger.exception()` captures traceback in logs |
| **Specific error responses** | 404, 422, 500 each have appropriate structure |
| **Correlation IDs on all responses** | X-Request-ID header added even on error responses |
| **Context cleanup** | `finally` block ensures structlog context is cleared |

### Guidelines for New Code

1. **Define domain-specific exceptions** in appropriate packages:
   ```python
   # In registries/ or adapters/
   class RegistryError(Exception):
       """Base exception for registry operations."""
       pass

   class ItemNotFoundRegistryError(RegistryError):
       """Raised when an item is not found in the registry."""
       pass
   ```

2. **Catch at boundaries, not deep in logic** — let exceptions bubble to `main.py` handlers

3. **Include correlation ID in custom exceptions** if they cross async boundaries:
   ```python
   structlog.contextvars.get_contextvars().get("request_id")
   ```

4. **Graceful degradation** — decide per component whether to fail fast or degrade

---

## Documentation Requirements

### Current Documentation (Good)

| Location | What's Documented |
|----------|------------------|
| **Package `__init__.py`** | Purpose, stage coverage, boundary rules |
| **Module docstrings** | Stage, purpose, what's NOT included |
| **Function docstrings** | Purpose, parameters (implicit), return behavior |
| **`ARCHITECTURE_BOUNDARIES.md`** | Complete boundary rules, dependency directions, examples |
| **`README.md`** | Project overview, setup, architecture summary |

### Documentation Standards

#### 1. Package `__init__.py`

Every package's `__init__.py` must include:

```python
"""
Package Name - Stage X

Brief description of what this package does.

BOUNDARY RULES (if applicable):
- What this package can import
- What this package cannot import
- Dependency direction

This is the [innermost/middle/outer] layer. [Other packages] depend on it.
"""
```

**Examples in code:** `core/__init__.py`, `services/__init__.py`, `messaging/__init__.py`

#### 2. Module Docstrings

Every `.py` file must start with:

```python
"""
Module purpose - Stage X

Key points:
- What this module does
- What it does NOT do (explicitly)
- Any important caveats
"""
```

**Examples in code:** `main.py`, `config.py`, `request_id.py`, `fake_channel.py`

#### 3. Public Function/Class Docstrings

Use **Google-style** docstrings for consistency:

```python
def register(self, name: str, adapter: ChannelAdapter) -> None:
    """Register a channel adapter. Validates protocol compliance.

    Args:
        name: Unique name for the adapter.
        adapter: Channel adapter instance implementing ChannelAdapter protocol.

    Raises:
        ValueError: If adapter doesn't have required attributes.

    Returns:
        None
    """
```

#### 4. Architectural Decision Records (ADRs)

For significant decisions, create numbered ADRs in `docs/adr/`:

```markdown
# ADR-001: Use Protocol-based registries instead of concrete types

## Status
Accepted

## Context
We need a way to register channel adapters without coupling to concrete implementations.

## Decision
Use `typing.Protocol` with `@runtime_checkable` for adapter interfaces.

## Consequences
- Positive: Easy to add new adapter types
- Positive: Type-safe registration
- Negative: Slightly more verbose than concrete base classes
```

### Documentation Checklist for New Components

- [ ] Package `__init__.py` has boundary rules
- [ ] Module docstring explains purpose and stage
- [ ] Public functions have Google-style docstrings
- [ ] Classes have docstrings explaining responsibility
- [ ] Any "what this does NOT do" is explicitly stated
- [ ] Exceptions have docstrings explaining when they're raised

---

## Architectural Boundaries

### Established Rules (See `ARCHITECTURE_BOUNDARIES.md`)

| Package | Can Import | Cannot Import |
|---------|------------|---------------|
| `core/` | stdlib, typing | `adapters/`, FastAPI, external SDKs, any `waxprep.*` |
| `registries/` | `base`, typing, `adapters` (only in `register_defaults`) | Concrete channel/model code, FastAPI |
| `adapters/` | stdlib, registry protocols, channel SDKs | `core/`, other adapters |
| `messaging/` | `core/`, `registries/`, stdlib | Concrete adapters, direct SDK imports |
| `context/` | stdlib, typing (optional: `core/`) | `messaging/`, `services/` |
| `main.py` | FastAPI, uvicorn, `config/`, `registries/`, `middleware/`, `adapters/` | `core/` |
| `middleware/` | Starlette, stdlib | `core/`, anything beyond web framework |

### Enforcement Mechanisms

1. **Static analysis**: `mypy --strict` catches boundary violations
2. **Architectural tests**: `tests/test_boundaries.py` uses AST scanning to verify rules
3. **Code review checklist**: Documented in `ARCHITECTURE_BOUNDARIES.md`

### Adding New Boundaries

When adding a new package:

1. Create `package/__init__.py` with boundary rules
2. Add boundary tests to `tests/test_boundaries.py`
3. Update `ARCHITECTURE_BOUNDARIES.md` with the new rules
4. Update the "Quick Reference" table

---

## Adding New Components

### 6-Point Checklist

Before adding any new component (module, package, class, function):

#### 1. Determine the Layer

Which architectural layer does this belong to?

- **core/** — Pure domain logic, no I/O, no infrastructure
- **registries/** — Registration/lookup, defines protocols
- **adapters/** — Concrete implementations of protocols
- **messaging/** — Orchestration, message flow
- **context/** — Learner state, profiles
- **services/** — Application service coordination
- **main.py** — Composition root, FastAPI wiring
- **middleware/** — Request/response processing

#### 2. Verify Boundary Compliance

- What can this new component import?
- What must it NOT import?
- Add boundary rules to `__init__.py` if creating a new package

#### 3. Type Safety

- Add type annotations to all public functions/classes
- Use `Protocol` for interfaces, not concrete base classes
- Run `mypy --strict` and `pyright` to verify

#### 4. Documentation

- Add module docstring with stage and purpose
- Add docstrings to all public functions/classes
- Explicitly state what this does NOT do

#### 5. Testing

- Add tests in `tests/` mirroring the source structure
- If crossing boundaries, add a test to `test_boundaries.py`
- Ensure tests prove the intended behavior

#### 6. Review Against Standards

- Does naming follow PEP 8 conventions?
- Does file organization follow one-responsibility-per-file?
- Are error paths handled appropriately?
- Is logging adequate (correlation ID, appropriate level)?

---

## Testing Standards

### Current Practices (Good)

| Practice | Evidence |
|----------|----------|
| **Test types mirror source** | `test_config.py`, `test_registries.py`, etc. |
| **pytest fixtures** | Clean fixture usage in `test_main.py`, `test_foundation.py` |
| **TestClient for FastAPI** | Standard FastAPI testing pattern |
| **Boundary enforcement tests** | AST-based checks in `test_boundaries.py` |
| **Class-based test organization** | Tests grouped by feature in classes |

### Guidelines

1. **Test naming**: `test_<behavior>` — describe what's being proven, not implementation
2. **Test organization**: Group related tests in classes with `Test<Feature>` naming
3. **Fixtures**: Use pytest fixtures for shared setup; prefer function scope
4. **Assertions**: Use specific assertions with clear error messages
5. **No implementation testing**: Test behavior, not implementation details

### Future Considerations

- **Parametrize tests** for multiple scenarios: `@pytest.mark.parametrize`
- **Test categories**: Consider separating unit vs. integration vs. boundary tests
- **Coverage targets**: Consider adding `pytest-cov` with minimum coverage thresholds

---

## Tooling & Configuration

### Current Tooling (Excellent)

| Tool | Purpose | Configuration |
|------|---------|---------------|
| **mypy** | Static type checking | `strict = true`, Python 3.14 |
| **pyright** | Alternative type checker | `typeCheckingMode = "strict"` |
| **ruff** | Linting + formatting | line-length 100, target py314 |
| **pytest** | Testing | pytest-asyncio for async tests |
| **uv** | Package management | lockfile in `uv.lock` |
| **hatchling** | Build backend | Modern Python packaging |

### Recommended Commands

```bash
# Type checking
uv run mypy src/waxprep --strict
uv run pyright src/waxprep

# Linting
uv run ruff check src/waxprep
uv run ruff format src/waxprep --check

# Testing
uv run pytest tests/ -v
uv run pytest tests/ --cov=src/waxprep  # With coverage

# All checks (suggested Makefile target)
make check  # mypy + pyright + ruff + pytest
```

### Configuration Files

- **`pyproject.toml`**: ALL project configuration (build, deps, tool configs)
- **`uv.lock`**: Dependencies locked (commit to version control)
- **`.env.example`**: Example environment variables (already exists)

### `.env` Handling

- Use `WAXPREP_` prefix for all environment variables
- Document required variables in `.env.example`
- Validate configuration at startup (Pydantic Settings does this)

---

## Best Practices to Adopt

### Already Adopted ✅

The following are already in place and should be preserved:

1. ✅ **Structured logging with correlation IDs** — structlog + RequestIdMiddleware
2. ✅ **No stack trace leaks** — sanitized error responses
3. ✅ **Explicit registration, no import-time side effects** — registries empty until `register_defaults()`
4. ✅ **Protocol-based abstractions** — `typing.Protocol` for adapter interfaces
5. ✅ **Strict type checking** — mypy + pyright in strict mode
6. ✅ **Liveness vs. readiness distinction** — separate health endpoints
7. ✅ **Configuration from environment only** — no hardcoded values
8. ✅ **Boundary enforcement tests** — AST scanning in `test_boundaries.py`
9. ✅ **Documentation in `__init__.py`** — boundary rules in each package

### Recommended Additions

#### 1. TypedDict for Structured Dict Returns

When functions return structured dictionaries (like `build_response` in `pure.py`), consider using `TypedDict`:

```python
from typing import TypedDict, Optional

class ResponseDict(TypedDict):
    content: str
    metadata: Optional[dict[str, Any]]

def build_response(content: str, metadata: Optional[dict[str, Any]] = None) -> ResponseDict:
    ...
```

#### 2. Custom Exception Hierarchy

Define project-specific exceptions for better error handling:

```python
# src/waxprep/exceptions.py (new file)

class WaxPrepError(Exception):
    """Base exception for WaxPrep."""
    pass

class ConfigurationError(WaxPrepError):
    """Configuration is invalid or missing."""
    pass

class RegistryError(WaxPrepError):
    """Registry operation failed."""
    pass

class AdapterNotFoundError(RegistryError):
    """Requested adapter is not registered."""
    pass
```

#### 3. Pydantic Models for API Boundaries

When adding real API endpoints, use Pydantic models for request/response schemas:

```python
from pydantic import BaseModel

class MessageRequest(BaseModel):
    content: str
    channel: str
    metadata: dict[str, Any] | None = None

class MessageResponse(BaseModel):
    status: str
    message_id: str
```

#### 4. Pre-commit Hooks

Add `pre-commit` configuration for automatic checking:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [pydantic, fastapi, structlog]
```

#### 5. Makefile or Justfile for Common Tasks

```makefile
# Makefile
.PHONY: check test lint format

check:
	uv run mypy src/waxprep --strict
	uv run pyright src/waxprep
	uv run ruff check src/waxprep

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check src/waxprep tests/
	uv run ruff format src/waxprep tests/ --check

format:
	uv run ruff format src/waxprep tests/
```

#### 6. CI/CD Pipeline

Ensure CI runs all checks:

```yaml
# .github/workflows/ci.yml (example)
name: CI
on: [push, pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --dev
      - run: uv run mypy src/waxprep --strict
      - run: uv run ruff check src/waxprep
      - run: uv run pytest tests/ -v
```

#### 7. Exception Logging Context

When logging exceptions, include relevant context:

```python
logger.exception(
    "Operation failed",
    operation="registry_lookup",
    item_name=name,
    registry_type=type(self).__name__,
)
```

---

## Quick Reference

### Naming Quick Reference

| Element | Convention | Example |
|---------|------------|---------|
| Module | `snake_case` | `request_id.py` |
| Function | `snake_case` | `register_defaults()` |
| Variable | `snake_case` | `_channel_registry` |
| Class | `PascalCase` | `ChannelRegistry` |
| Protocol | `PascalCase` | `ChannelAdapter` |
| Constant | `UPPER_SNAKE_CASE` | `MAX_RETRIES` |
| TypeVar | Single uppercase | `T` |
| Exception | `PascalCase` + "Error" | `RegistryError` |
| Pydantic model | `PascalCase` + "Request/Response" | `MessageRequest` |

### Import Rules Quick Reference

| File Location | Can Import `adapters`? | Can Import `core`? | Can Import FastAPI? | Can Import SDKs? |
|---------------|------------------------|--------------------|---------------------|------------------|
| `registries/` | Only in `register_defaults()` | No | No | No |
| `adapters/` | No | No | No | Yes (for that adapter) |
| `core/` | **NO** | — | **NO** | **NO** |
| `messaging/` | No (use registries) | Yes | No | No (use registries) |
| `context/` | No | Optional | No | No |
| `main.py` | Yes | No | Yes | No (use adapters) |
| `middleware/` | No | No | Yes (Starlette) | No |

### Documentation Quick Reference

| Element | Required? | Format |
|---------|-----------|--------|
| Package `__init__.py` | ✅ | Boundary rules + purpose |
| Module docstring | ✅ | Stage + purpose + caveats |
| Public function | ✅ | Google-style docstring |
| Public class | ✅ | Responsibility + usage |
| Private function | ⚠️ | Brief comment if non-obvious |
| Exception class | ✅ | When raised |

### Checklist: Before Committing New Code

- [ ] Naming follows PEP 8 conventions
- [ ] Type annotations are complete and pass `mypy --strict`
- [ ] Code passes `ruff check` with no errors
- [ ] Module has docstring explaining purpose and stage
- [ ] Public functions have Google-style docstrings
- [ ] Boundary rules are respected (no forbidden imports)
- [ ] If new package, `__init__.py` documents boundary rules
- [ ] Tests added/updated in `tests/`
- [ ] If crossing boundaries, `test_boundaries.py` updated
- [ ] Error handling doesn't leak internals
- [ ] Logging includes appropriate context (correlation ID if applicable)

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-11-16 | Initial document based on Stage 01-03 codebase analysis |

---

*This document is a living document. Update it as the codebase evolves and new patterns are established.*
