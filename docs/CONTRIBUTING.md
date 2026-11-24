# Contributing to WaxPrep

Thank you for your interest in contributing to WaxPrep! This guide covers the conventions, standards, and processes used in this codebase.

## Table of Contents

1. [Development Setup](#development-setup)
2. [Naming Conventions](#naming-conventions)
3. [File Organization](#file-organization)
4. [Type Safety](#type-safety)
5. [Error Handling](#error-handling)
6. [Documentation](#documentation)
7. [Architecture Boundaries](#architecture-boundaries)
8. [Adding New Components](#adding-new-components)
9. [Testing](#testing)
10. [Code Quality](#code-quality)

---

## Development Setup

### Prerequisites

- Python 3.14+ (compatibility proven, not assumed)
- [uv](https://github.com/astral-sh/uv) for dependency management

### Initial Setup

```bash
# Install dependencies (dev optional extra)
uv sync --extra dev

# Run tests
uv run pytest

# Type checking
uv run mypy src/

# Linting
uv run ruff check src/
uv run ruff format src/
```

### Project Structure

```
src/waxprep/
├── main.py              # ASGI app, health endpoints, lifespan, middleware
├── config.py            # Settings (configurable defaults, not hardcoded)
├── core/                # Pure logic & protocols (NO infrastructure imports)
│   ├── __init__.py      # Boundary rules, purpose statement
│   ├── protocols.py     # Domain protocols
│   └── pure.py          # Pure functions
├── messaging/           # Message handling & conversation flow
├── context/             # Understanding the learner
├── services/            # Light orchestration
├── middleware/          # Request ID and base middleware patterns
├── registries/          # Channel, Model, Tool registries
└── adapters/            # Fake adapter implementations (source of truth)

tests/
├── unit/               # Pure logic, single function/class
├── integration/        # Component interactions
├── contract/           # Protocol compliance
├── lifecycle/          # Startup/shutdown, failures
├── architecture/       # Boundary enforcement
├── configuration/      # Config loading
├── detector/           # Detector unit, adversarial, CLI tests
├── regression/         # Behavior preservation
├── conftest.py         # Shared fixtures
```

---

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Packages & modules | `snake_case` | `core/`, `protocols.py`, `request_id.py` |
| Classes | `PascalCase` | `BaseRegistry`, `MessageHandler`, `FakeChannelAdapter` |
| Functions & variables | `snake_case` | `get_context`, `register_defaults`, `correlation_id` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT` |
| Protocols | Clear noun or `XxxProtocol`/`XxxAdapter` | `Message`, `ChannelAdapter`, `ContextProvider` |
| Type variables | Single uppercase letter or descriptive | `T`, `MsgT`, `AdaptT` |

### Prohibited Names

**Never** name packages, modules, or components after:

- Student types (e.g., `beginners`, `advanced`, `novice`)
- Academic levels (e.g., `high_school`, `college`, `university`)
- Subjects (e.g., `math`, `science`, `english`)
- Ability categories (e.g., ` gifted`, `remedial`)

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

Each file should have a single, clear purpose. If you find yourself writing "and" in a file's description, consider splitting it.

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
# src/waxprep/core/__init__.py
"""
Core Package - Stage 03

Boundary rules:
- Pure logic only
- NO imports from adapters, channels, FastAPI, SDKs
- NO infrastructure dependencies

Public API:
- protocols: Domain protocols
- pure: Pure functions
"""

from waxprep.core import protocols
from waxprep.core import pure

__all__ = ["protocols", "pure"]
```

### Tests Follow Categorised Layout

Tests are organised by category in `tests/`:

- `tests/unit/` — pure logic, single function/class
- `tests/integration/` — component interactions
- `tests/contract/` — protocol compliance
- `tests/lifecycle/` — startup/shutdown, failures
- `tests/architecture/` — boundary enforcement
- `tests/configuration/` — config loading
- `tests/detector/` — Stage 08 detector tests
- `tests/regression/` — behavior preservation

Place new tests in the appropriate category directory.

---

## Type Safety

### Strict Settings

This project uses strict type checking:

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

# ❌ AVOID - missing annotations
def get_item(name):
    ...
```

### Prefer Protocol for Boundaries

Use `typing.Protocol` to define interfaces that adapters must implement:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ChannelAdapter(Protocol):
    """Adapter protocol for message channels."""

    async def send(self, message: str) -> bool:
        """Send a message. Returns True on success."""
        ...

    async def receive(self) -> str | None:
        """Receive a message. Returns None if no message available."""
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

Use `Any` only when:
- Documenting *why* it's needed
- It's truly unavoidable (e.g., callback signatures)

```python
# ✅ Documented reason
def process callback_handler(
    data: Any,  # Implementation-specific; handler decides interpretation
) -> None:
    ...

# ❌ AVOID - no justification
def handle(data: Any) -> None:
    ...
```

---

## Error Handling

### Never Leak Stack Traces

Stack traces in responses can expose internal details. Log them server-side instead.

```python
import structlog
from fastapi import Request, HTTPException

logger = structlog.get_logger()

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Log full error with correlation ID
    logger.error(
        "unhandled_exception",
        error=str(exc),
        correlation_id=request.state.correlation_id if hasattr(request.state, 'correlation_id') else "unknown",
        traceback=True,  # Full traceback logged server-side only
    )
    raise HTTPException(status_code=500, detail="Internal server error")
```

### Prefer Specific Exceptions

```python
# ✅ GOOD - specific exception
class AdapterNotRegisteredError(KeyError):
    """Raised when an adapter is not found in the registry."""
    pass

def get_adapter(name: str) -> ChannelAdapter:
    if name not in self._items:
        raise AdapterNotRegisteredError(f"No adapter registered: {name}")
    return self._items[name]

# ❌ AVOID - broad except
try:
    something()
except Exception:
    handle()
```

### Validation Errors → 422

FastAPI automatically maps Pydantic `ValidationError` to 422 Unprocessable Entity.

### Unexpected Errors → Generic 500

For unhandled exceptions, return a generic error message to clients while logging full details server-side.

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

Docstrings should explain **why** and **what**, not just **how**:

```python
def extract_keywords(text: str) -> list[str]:
    """
    Extract significant keywords from text for intent matching.

    Uses simple whitespace tokenization and stop-word filtering.
    Does NOT perform stemming or lemmatization.

    Args:
        text: Input text to process

    Returns:
        List of keyword strings in order of appearance
    """
```

### README is Source of Truth

The README.md contains:
- Current stage and scope
- Package structure
- Boundary rules
- What is NOT included (later stages)

If you change architecture, update README.md.

---

## Architecture Boundaries

### Dependency Direction: Outer → Inner (ONE WAY)

```
Outer layers (infrastructure, orchestration) may import Inner layers.
Inner layers (core, protocols) MUST NOT import Outer layers.

messaging/ ──→ core/
context/   ──→ core/
services/  ──→ core/, messaging/, context/, registries/
main.py    ──→ services/, messaging/, registries/, middleware/
adapters/  ──→ registry protocols (NOT core/)
registries/ ──→ base, typing (defines protocols that adapters implement)
core/      ──→ Nothing from waxprep (pure logic only)
```

**NEVER reverse this:** `core/` must not import from `messaging/`, `services/`, `adapters/`, or anywhere with infrastructure details.

### What Each Package May Import

| Package | May Import From | May NOT Import From |
|---------|-----------------|---------------------|
| `core/` | standard library only | adapters, channels, FastAPI, SDKs, any `waxprep.*` |
| `messaging/` | `core/`, `registries/` | concrete adapters, direct SDKs, `context/`, `services/` |
| `context/` | `core/` | `messaging/`, `services/`, concrete adapters |
| `services/` | `core/`, `messaging/`, `context/`, `registries/` | (composition root - knows about everything) |
| `main.py` | FastAPI, config, registries, middleware, adapters | `core/` (framework-agnostic) |
| `adapters/` | registry protocols, SDKs | `core/`, other adapters (except via registries) |

### No Hardcoding Rule

Operational values that should vary across environments must come from environment variables or test fixtures. Never hardcode:

- ❌ Model names
- ❌ API keys
- ❌ Channel identifiers
- ❌ Student levels
- ❌ Greetings
- ❌ Keyword routes

Acceptable defaults (for development convenience):

- ✅ Default environment name (`development`)
- ✅ Default host (`0.0.0.0`)
- ✅ Default port (`8000`)
- ✅ Default log level (`info`)
- ✅ Standard HTTP status codes
- ✅ UUID validation rules
- ✅ Response structures

---

## Adding New Components

Before adding a new component, run through this checklist:

### Architecture Fit

- [ ] Does it fit an existing package, or does it need a new one?
- [ ] Does it respect the Outer → Inner dependency direction?
- [ ] Does it avoid student categories/hardcoded domains?

### Registration (if an adapter)

- [ ] Is it registered through the appropriate registry?
- [ ] Does it implement the correct protocol?
- [ ] Is registration explicit (not import-time side effects)?

### Type Safety & Documentation

- [ ] Are types fully annotated on all public functions?
- [ ] Does it use `Protocol` for boundaries?
- [ ] Is there a docstring explaining why and what?
- [ ] Does `__init__.py` state boundary rules if it's a new package?

### Testing

- [ ] Is there at least one test?
- [ ] Does the test prove the component works correctly?
- [ ] Do tests mirror the package structure?

### No Hardcoding

- [ ] Are all configuration values from environment or fixtures?
- [ ] Is there any hardcoded model name, API key, port, timeout, etc.?

---

## Testing

### Run All Tests

```bash
uv run pytest
```

### Run with Coverage

```bash
uv run pytest --cov=waxprep --cov-report=term-missing
```

### Test Naming

- Tests for `src/waxprep/foo/bar.py` → `tests/test_foo_bar.py` or `tests/foo/test_bar.py`
- Test functions: `test_<function_name>_<scenario>`

```python
# tests/test_registries.py
def test_register_adds_item():
    """register() adds the item to the registry."""
    ...

def test_get_raises_key_error_for_missing():
    """get() raises KeyError when item not found."""
    ...
```

### Test Types
- **Unit tests** (`tests/unit/`): Test individual functions/classes
- **Integration tests** (`tests/integration/`): Test component interactions
- **Contract tests** (`tests/contract/`): Verify protocol compliance
- **Lifecycle tests** (`tests/lifecycle/`): Startup/shutdown, failure paths
- **Architecture tests** (`tests/architecture/`): Boundary enforcement
- **Configuration tests** (`tests/configuration/`): Config loading verification
- **Detector tests** (`tests/detector/`): Stage 08 rule verification
- **Regression tests** (`tests/regression/`): Behavior preservation

---

## Code Quality

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

## Questions?

Open an issue for:
- Architecture questions
- Boundary rule clarifications
- Feature proposals

For quick questions, check:
- [README.md](README.md) - Source of truth for current state
- [ARCHITECTURE_BOUNDARIES.md](ARCHITECTURE_BOUNDARIES.md) - Detailed boundary rules
- Existing tests - Show intended behavior

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See [LICENSE](LICENSE) for details.
