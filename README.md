# WaxPrep Foundation - Stages 01-02 ONLY

**IMPORTANT: This repository contains ONLY Stages 01 and 02.**

## Stage 01: Programming Language
- Python 3.14+ (compatibility proven, not assumed)
- uv for dependency management
- Pydantic v2 for data validation
- Static type checking (mypy/pyright)

## Stage 02: Runtime and Execution Environment
- ASGI application (FastAPI + Uvicorn)
- Registry pattern with fake adapters (proves architecture)
- Explicit registry registration (no import-time side effects)
- Graceful shutdown (signal handlers implemented)
- Health endpoints (liveness ≠ readiness, readiness checks registry state)
- Structured logging with correlation IDs (middleware-bound)
- Message acceptance contract (proven by test)

## What is NOT included (later stages):
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

## NO Hardcoding Rule
- ❌ NO model names hardcoded
- ❌ NO API keys hardcoded
- ❌ NO ports hardcoded
- ❌ NO timeouts hardcoded
- ❌ NO grace periods hardcoded
- ❌ NO channel identifiers hardcoded
- ❌ NO student levels hardcoded
- ❌ NO greetings hardcoded
- ❌ NO keyword routes hardcoded

All configuration lives in environment variables or test fixtures.

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

## Project Structure

```
src/waxprep/
├── main.py              # ASGI app, health endpoints, lifespan, middleware
├── config.py            # Settings (NO hardcoded values)
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
├── test_config.py       # Proves NO hardcoded values
├── test_registries.py   # Proves registry behavior
├── test_main.py         # Proves health endpoints work
└── test_foundation.py   # Proves foundation stability
```

**Key distinction:** `adapters/` contains the fake implementations. `registries/` contains only the registry logic (no adapter knowledge). The `register_defaults()` function bridges them by importing from `adapters/` and registering.

## Running Tests

```bash
uv run pytest tests/ -v
```

With coverage:
```bash
uv run pytest tests/ -v --cov=src/waxprep --cov-report=term-missing
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
| `WAXPREP_SHUTDOWN_GRACE_PERIOD` | 30 | Graceful shutdown seconds |
| `WAXPREP_LOG_LEVEL` | info | Log level (debug/info/warning/error/critical) |

## Health Endpoints

### Liveness (`GET /health/liveness`)
Returns whether the process is alive. Always returns 200 if the app is running.

```json
{"status": "alive"}
```

### Readiness (`GET /health/readiness`)
Returns whether the application is ready to serve requests. Checks:
- Configuration is loaded
- Registries are initialized
- Default adapters are registered

```json
{
  "status": "ready",
  "checks": {
    "configuration": "ok",
    "channel_registry": "ok",
    "model_registry": "ok",
    "tool_registry": "ok",
    "correlation_id_middleware": "active"
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
