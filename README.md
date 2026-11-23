# WaxPrep Foundation

**IMPORTANT: This repository contains the WaxPrep engineering foundation (Stages 01 through 07).**

Stage 07 adds the consolidated CI quality gate (`.github/workflows/quality-gate.yml`) with blocking checks (ruff, ruff format, mypy, import-linter, semgrep, tests, 100% coverage gate, smoke test) and advisory checks (pyright, vulture). Pip-audit runs with a single tracked exception (GHSA-53pm-wgxf-c6qf); all other dependency vulnerabilities fail the gate.

**Stage 07 completion does not mean the WaxPrep AI tutoring product is complete.** This is still a foundation project. Real WhatsApp/Telegram handlers, database infrastructure, tutor logic, and the intelligence layer are not implemented.

## Stage 01: Programming Language
- Python 3.14+ (tested on 3.14; compatibility with later versions not proven)
- uv for dependency management
- Pydantic v2 for data validation
- Static type checking (mypy/pyright)

## Stage 02: Runtime and Execution Environment
- ASGI application (FastAPI + Uvicorn)
- Registry pattern with fake adapters (proves architecture)
- Explicit registry registration (no import-time side effects)
- Graceful shutdown (ASGI server-managed via lifespan; no custom signal handler)
- Application state isolated in AppState container (not module-global)
- Health endpoints (liveness ≠ readiness, readiness checks registry state)
- Structured logging with correlation IDs (middleware-bound, context properly restored)
- Request ID validation (incoming IDs validated before trust)
- Global exception handling (no stack traces leaked; HTTP exceptions sanitized)

## Stage 03: Project Architecture and Structural Boundaries

- Package structure with explicit domain boundaries
- `core/` - Pure logic & protocols (no infrastructure imports)
- `messaging/` - Message handling & conversation flow (placeholder - no implementation)
- `context/` - Understanding the learner (placeholder - no implementation)
- `services/` - Light orchestration (placeholder - no implementation)
- Boundary rules documented and enforced via import-linter
- Dependency direction: Outer → Inner. Never the reverse.
- "Land not house" philosophy - architecture enables future builds without dictating them

### Package Structure (Stage 03)

```
src/waxprep/
├── main.py              # ASGI app, health endpoints, lifespan, middleware
├── config.py            # Settings (configurable defaults, not hardcoded)
├── id.py                # UUIDv7 identity generation (Stage 04 identity foundation)
├── core/                # Pure logic & protocols (NO infrastructure imports)
│   ├── __init__.py      # Boundary rules, purpose statement
│   ├── protocols.py     # Message/MessageHandler/ContextProvider protocols
│   └── pure.py          # Pure functions (normalize_text, extract_keywords, etc.)
├── messaging/           # Message handling & conversation flow (placeholder - no implementation)
│   └── __init__.py      # Boundary rules, reserved architectural area
├── context/             # Understanding the learner (placeholder - no implementation)
│   └── __init__.py      # Boundary rules, reserved architectural area
├── services/            # Light orchestration (placeholder - no implementation)
│   └── __init__.py      # Boundary rules, reserved architectural area
├── middleware/          # Request ID and base middleware patterns
│   ├── __init__.py
│   ├── request_id.py    # Correlation ID middleware
│   └── base.py          # Middleware skeletons (unimplemented - not active protection)
├── registries/          # Channel, Model, Tool registries
│   ├── __init__.py
│   ├── base.py          # BaseRegistry[T] - generic registry
│   ├── channel.py       # ChannelRegistry + ChannelAdapter protocol
│   ├── model.py         # ModelRegistry + ModelAdapter protocol
│   └── tool.py          # ToolRegistry + Tool protocol
└── adapters/            # Fake adapter implementations (source of truth)
    ├── __init__.py
    ├── fake_channel.py  # FakeChannelAdapter
    ├── fake_model.py    # FakeModelAdapter
    └── fake_tool.py     # FakeTool
```
src/waxprep/
├── main.py              # ASGI app, health endpoints, lifespan, middleware
├── config.py            # Settings (NO hardcoded values)
├── id.py                # UUIDv7 identity generation (Stage 04 identity foundation)
├── core/                # Pure logic & protocols (NO infrastructure imports)
│   ├── __init__.py      # Boundary rules, purpose statement, Message/MessageHandler/ContextProvider
│   ├── protocols.py     # Protocol re-exports and boundary guard
│   └── pure.py          # Pure functions (normalize_text, extract_keywords, etc.)
├── messaging/           # Message handling & conversation flow (placeholder)
│   └── __init__.py      # Boundary rules, placeholder for future code
├── context/             # Understanding the learner (placeholder)
│   └── __init__.py      # Boundary rules, open land - internal shape TBD
├── services/            # Light orchestration (placeholder)
│   └── __init__.py      # Boundary rules, composition layer
├── middleware/          # Request ID and base middleware patterns
│   ├── __init__.py
│   ├── request_id.py    # Correlation ID middleware
│   └── base.py          # Middleware skeletons for future use
├── registries/          # Channel, Model, Tool registries
│   ├── __init__.py
│   ├── base.py          # BaseRegistry[T] - generic registry
│   ├── channel.py       # ChannelRegistry + ChannelAdapter protocol
│   ├── model.py         # ModelRegistry + ModelAdapter protocol
│   └── tool.py          # ToolRegistry + Tool protocol
└── adapters/            # Fake adapter implementations (source of truth)
    ├── __init__.py
    ├── fake_channel.py  # FakeChannelAdapter
    ├── fake_model.py    # FakeModelAdapter
    └── fake_tool.py     # FakeTool

tests/
├── unit/
│   ├── __init__.py
│   ├── test_core_pure.py              # Pure function logic
│   ├── test_id.py                     # UUIDv7 correctness, monotonicity, mass uniqueness, format validation
│   └── test_middleware_skeletons.py   # Middleware skeleton validation
├── integration/
│   ├── __init__.py
│   ├── test_exception_handlers.py     # Exception handler integration
│   ├── test_foundation.py             # Foundation stability + middleware + correlation IDs
│   ├── test_main.py                   # Health endpoints
│   └── test_registries.py            # Registry behavior
├── contract/
│   ├── __init__.py
│   └── test_core_protocols.py         # Protocol compliance
├── lifecycle/
│   ├── __init__.py
│   └── test_lifecycle.py              # Startup/shutdown, failure paths
├── architecture/
│   ├── __init__.py
│   └── test_boundaries.py             # Architectural boundary enforcement
├── configuration/
│   ├── __init__.py
│   └── test_config.py                 # Proves NO hardcoded values
├── regression/
│   ├── __init__.py
│   └── (regression tests)
├── conftest.py                        # Shared fixtures
├── test_exception_handler_pattern.py  # Exception handler pattern tests
└── test_final_coverage.py             # Final coverage verification
```

**Old flat test files → new locations:**

| Old file | New location |
|---|---|
| `tests/test_config.py` | `tests/configuration/test_config.py` |
| `tests/test_registries.py` | `tests/integration/test_registries.py` |
| `tests/test_main.py` | `tests/integration/test_main.py` |
| `tests/test_foundation.py` | `tests/integration/test_foundation.py` |
| `tests/test_boundaries.py` | `tests/architecture/test_boundaries.py` |
| `tests/test_id.py` | `tests/unit/test_id.py` |

### Boundary Rules

**Dependency Direction: Outer → Inner (ONE WAY)**

```
Outer layers (infrastructure, orchestration) may import Inner layers.
Inner layers (core, protocols) MUST NOT import Outer layers.

messaging/ ──→ core/, registries/
context/   ──→ core/
services/  ──→ core/, messaging/, context/, registries/
main.py    ──→ config, registries, middleware, adapters
adapters/  ──→ registry protocols (NOT core/, NOT registries/)
registries/-→ base, typing (defines protocols; imports concrete fakes for defaults)
core/      ──→ Nothing from waxprep (pure logic only)

NEVER reverse this: core/ must not import from messaging/, services/, adapters/, or anywhere that contains infrastructure details.
```

Note: The registry layer contains protocols and imports concrete fake adapters for default registration. This is a deliberate design choice using structural typing (runtime_checkable Protocol). Adapters must NOT import from registries/ - they implement the protocols defined there.

### Package Naming Rules
- ❌ NO packages named after student types (e.g., "beginners", "advanced")
- ❌ NO packages named after academic levels (e.g., "high_school", "college")
- ❌ NO packages named after subjects (e.g., "math", "science")
- ❌ NO packages named after ability categories
- ✅ Packages named after ARCHITECTURAL ROLES (core, messaging, context, services)

### What Each Package May Import

| Package | May Import From | May NOT Import From |
|---------|-----------------|---------------------|
| `core/` | standard library only | adapters, channels, FastAPI, SDKs, any waxprep.* |
| `messaging/` | core/, registries/ | concrete adapters, direct SDKs, context/, services/ |
| `context/` | core/ | messaging/, services/, concrete adapters |
| `services/` | core/, messaging/, context/, registries/ | adapters directly (use registries) |
| `main.py` | FastAPI, config, registries, middleware, adapters | core/ (framework-agnostic) |
| `adapters/` | registry protocols (structural typing), SDKs | core/, registries/, other adapters, messaging/, context/, services/ |
| `registries/` | registries/base, typing | messaging/, context/, services/ |

Adapters depend on registry protocols via structural typing (duck typing). They do not import from the registries/ package.

### What is NOT included (later stages):
- ❌ NO WhatsApp handlers
- ❌ NO Telegram handlers  
- ❌ NO database schema
- ❌ NO docker-compose files
- ❌ NO PostgreSQL/Redis configuration
- ❌ NO tutor logic
- ❌ NO intelligence layer
- ❌ NO message router
- ❌ NO student context manager
- ❌ NO model orchestrator
- ❌ NO tool executor
- ❌ NO Prometheus/OpenTelemetry
- ❌ NO production deployment

## Stage 04: Identity Foundation (Wax ID)

- `src/waxprep/id.py` — UUIDv7 identity generation (`generate_id()`, `is_valid_id()`)
- Centralized, reusable identity capability for system entities and objects
- Uses standard UUID string format, no semantic prefixes
- Time-sortable (UUIDv7, RFC 9562), suitable for distributed systems
- Designed so future components can safely consume it
- `tests/test_id.py` — UUIDv7 correctness, monotonicity, mass uniqueness, format validation

## Stage 05: Testing

Seven test categories with dedicated directories under `tests/`:

- **unit/** — pure logic, single function/class
- **integration/** — component interactions  
- **contract/** — protocol compliance
- **lifecycle/** — startup/shutdown, failures
- **architecture/** — boundary enforcement
- **configuration/** — config loading
- **regression/** — behavior preservation (directory present; no tests currently pinned)

```bash
uv run pytest tests/unit/ -v          # run unit tests
uv run pytest tests/integration/ -v   # run integration tests
# etc.
```

**Markers alternative:** Use `@pytest.mark.unit` etc. on test functions instead of directory nesting. Run with `pytest -m unit`.

## Stage 06: Static Analysis

Static-analysis tooling added and configured:

- **Ruff** — linting + format checking (blocking)
- **Mypy** — strict type checking (blocking)
- **Pyright** — strict type checking (advisory)
- **Import Linter** — architecture import contracts (blocking, 4 contracts in `.importlinter`)
- **Semgrep** — security pattern scanning (blocking, `--config auto --error`)
- **Vulture** — dead code detection (advisory)

Configuration lives in `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`, `[tool.pyright]`, `[tool.vulture]`) and `.importlinter`.

## Stage 07: Quality Gate

Consolidated CI quality gate in `.github/workflows/quality-gate.yml`:

**Trigger:** push to `main` and pull requests targeting `main`.

**Blocking jobs** (all must pass):
- `quality-setup` — uv sync + shared package cache
- `quality-gate` — ruff lint, ruff format, mypy (strict), import-linter, semgrep, pip-audit
- `tests` — matrix of unit, integration, contract, lifecycle, architecture, configuration
- `coverage-gate` — full suite with `--cov-fail-under=100`
- `smoke-test` — app boot + liveness/readiness health checks

**Advisory jobs** (run independently, do not block the gate):
- `pyright` — strict type check (`|| true`)
- `vulture` — dead code report (`|| true`)

**Aggregate job** (`gate-aggregate`) reports the blocking job status and fails if any blocking job fails or is cancelled.

**Pip-audit exception:** `GHSA-53pm-wgxf-c6qf` (wcmatch 8.5.2) is tracked and ignored via `pip-audit --ignore-vuln`. All other vulnerabilities still fail the gate.

**Local equivalent:** `make check` (Makefile) or `just check` (Justfile) run the same blocking checks locally.

## Stage 08: Universal Hardcoding Detection System

Independent, deterministic source-code detection system that identifies prohibited hardcoded conversational behavior in WaxPrep.

**Purpose:** The detector investigates HOW source code makes decisions about student messages, not just what words appear in the code. It prevents developers and AI coding agents from quietly introducing fixed input-dependent behavior into parts of WaxPrep where decisions are expected to be contextual, flexible, or delegated to an approved intelligence layer.

**Key characteristics:**
- Development-time tool only — not part of the production tutor response pipeline
- Operates deterministically without AI or network access
- Uses Python AST analysis and Semgrep structural rules
- Integrates with the existing Quality Gate
- Does not rely on a manually maintained forbidden-word list

**Detection rules (Living Specification):** See `docs/DETECTOR_SPECIFICATION.md`

| Rule ID | Description | Severity |
|---------|-------------|----------|
| WHD-001 | Fixed-string comparisons against student input | HIGH |
| WHD-002 | Fixed vocabulary membership tests | HIGH |
| WHD-003 | Fixed decision trees (if/elif chains) | MEDIUM |
| WHD-004 | Regex-based phrase detection | MEDIUM |
| WHD-005 | Word-to-action dictionary lookups | MEDIUM |
| WHD-006 | Deeply nested conditional structures | LOW |
| WHD-007 | Predetermined string responses | MEDIUM |
| WHD-008 | Hardcoded vocabularies | MEDIUM |
| WHD-009 | JSON string-to-string mappings | MEDIUM |
| WHD-010 | Vocabulary lists in data files | LOW |
| WHD-011 | Response templates in Markdown | LOW |

**Protected modules** (hardcoded conversational behavior prohibited):
- `waxprep.messaging` — Message handling & conversation flow
- `waxprep.context` — Understanding the learner
- `waxprep.services` — Light orchestration

**Usage:**
```bash
# Run the detector
python -m waxprep.detector [path] [format]

# Run as quality gate check
python -m waxprep.detector.quality_gate [path] --format summary
```

**Test suite:** `tests/detector/` contains unit tests, adversarial tests, mutation tests, and property-based tests.

## Supporting Documentation

- CONTRIBUTING.md — How developers should contribute
- docs/ENGINEERING-STANDARDS.md — Engineering rules and conventions
- PR_REVIEW_CHECKLIST.md — What reviewers should check before approving changes
- STAGE_03_ARCHITECTURE.md — Stage 03 architectural decisions and boundaries
- ARCHITECTURE_BOUNDARIES.md — Package dependency rules and what each layer may import

## Configuration Policy

WaxPrep uses configurable defaults via environment variables (WAXPREP_ prefix).

### What Must Be Configurable
- Environment name
- Host binding
- Port
- Log level

### What Are Acceptable Fixed Defaults
- Development defaults (e.g., default log level "info", default environment "development")
- Standard HTTP status codes
- UUID validation rules
- Response structures

### What Is Legacy (Removed)
- shutdown_grace_period (removed; shutdown is ASGI server-managed)

### What Is Not Hardcoding
- A configurable default is not a hardcoded value
- Test constants are not operational hardcoding
- Architectural invariants (e.g., HTTP methods, status codes) are not configuration

### What Would Be Hardcoding (Forbidden)
- Operational values that should vary across environments without configuration
- Model names, API keys, credentials
- Channel identifiers that should be configurable
- Student levels, greetings, keyword routes that are domain-specific

Configuration lives in environment variables via Pydantic Settings.

## Registry Pattern

Each adapter type (channels, models, tools) has a registry that:
- Accepts adapters via `register(name, adapter)`
- Validates adapters conform to the protocol
- Retrieves by name with `get(name)` (raises KeyError if missing)
- Lists all registered with `list_all()`
- Checks registration with `is_registered(name)`

**Important: Registries are NOT populated at import time.** 
Use `register_defaults()` explicitly in the application lifespan to populate with fake adapters for testing.

In Stages 01-02, each registry contains ONE fake adapter to prove the pattern works.

## Land Not House Philosophy

Stage 03 is about preparing the land, not building a house.

**We are building:**
- ✅ Clear package boundaries
- ✅ Dependency direction rules
- ✅ Protocol definitions
- ✅ Placeholders for future layers

**We are NOT building:**
- ❌ Complete domain entity hierarchy
- ❌ Full application service layer
- ❌ Real infrastructure implementations
- ❌ Production-ready adapter implementations

**Why "Land Not House":**
A house dictates exactly what goes where. A house is hard to remodel.
Land with clear boundaries, utilities, and foundations:
- Can accommodate any house design
- Easy to change the house without changing the land
- Multiple houses can share the same land

For WaxPrep:
- The domain boundaries we establish now will outlast any specific implementation
- When we add identity generation (Stage 04 Wax ID), it fits into the existing structure
- When we add AI models, they fit into the existing adapter structure
- The architecture enables change without requiring architectural changes

## Running Tests

Prerequisite (sync dev dependencies once):

```bash
uv sync --extra dev
```

Full suite:

```bash
uv run pytest tests/ -v
```

With coverage:

```bash
uv run pytest tests/ -v --cov=waxprep --cov-report=term-missing
```

Local quality gate (matches CI blocking checks):

```bash
make check
# or
just check
```


## Running the Application

```bash
uv run uvicorn waxprep.main:get_app --host 0.0.0.0 --port 8000
```

With auto-reload during development:
```bash
uv run uvicorn waxprep.main:get_app --host 0.0.0.0 --port 8000 --reload
```

Or run as module:
```bash
uv run python -m waxprep.main
```

## Configuration (WAXPREP_ prefix)

All configuration uses the `WAXPREP_` prefix to avoid conflicts with sandbox environment variables.

| Variable | Default | Description |
|----------|---------|-------------|
| `WAXPREP_ENVIRONMENT` | development | Environment name (development/testing/production) |
| `WAXPREP_HOST` | 0.0.0.0 | Bind host |
| `WAXPREP_PORT` | 8000 | Bind port |
| `WAXPREP_LOG_LEVEL` | info | Log level (debug/info/warning/error/critical) |

Note: `WAXPREP_SHUTDOWN_GRACE_PERIOD` has been removed. Graceful shutdown is managed by the ASGI server (uvicorn) lifecycle.

## Health Endpoints

### Liveness (`GET /health/liveness`)
Returns whether the process is alive. Always returns 200 if the app is running.

```json
{"status": "alive"}
```

### Readiness (`GET /health/readiness`)
Returns whether the application is ready to serve requests. Checks:
- Configuration has a non-empty environment value
- Registries are initialized
- Default adapters are registered in each registry

Reports only what the application can independently verify. Does not include middleware status since that is not independently checked.

```json
{
  "status": "ready",
  "checks": {
    "configuration": "ok",
    "channel_registry": "ok",
    "model_registry": "ok",
    "tool_registry": "ok"
  }
}
```

If not ready, returns 503 with reason.

## Correlation ID Middleware

Every request receives a correlation ID:
- Generated as UUID if `X-Request-ID` header not provided
- Propagated from `X-Request-ID` header if provided
- Bound to structlog context for request lifetime
- Added to response headers as `X-Request-ID`

This enables request tracing in logs without requiring distributed tracing infrastructure.

## Exception Handling

The application includes global exception handlers:
- **HTTP exceptions**: Return clean JSON with status code and path
- **Validation errors**: Return structured error list (sanitized)
- **Unhandled exceptions**: Return generic 500 error, log full details server-side

No stack traces are leaked to clients.
