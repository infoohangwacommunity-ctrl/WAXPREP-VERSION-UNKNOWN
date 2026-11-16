# WaxPrep Foundation Upgrades - Implementation Plan (Stage 01-02)

## Overview

This plan implements six foundation upgrades WITHOUT adding features. All changes are internal infrastructure improvements that make the foundation more robust for future stages.

---

## PRIORITY 1: Remove Import-Time Side Effects

### Problem
Fake adapters are registered at module import time in:
- `src/waxprep/registries/channel.py` (lines 46-47)
- `src/waxprep/registries/model.py` (lines 46-47)
- `src/waxprep/registries/tool.py` (lines 46-47)

This means registries are populated BEFORE the lifespan startup, causing:
- Hidden coupling
- Hard to test without side effects
- Order-dependent initialization

### Solution
Move registration to explicit `register_defaults()` methods called during lifespan.

### Files to Modify

| File | Changes |
|------|---------|
| `src/waxprep/registries/channel.py` | Remove module-level registration; add `register_defaults()` method |
| `src/waxprep/registries/model.py` | Remove module-level registration; add `register_defaults()` method |
| `src/waxprep/registries/tool.py` | Remove module-level registration; add `register_defaults()` method |
| `src/waxprep/main.py` | Call `register_defaults()` in lifespan after getting registries |

### Implementation Steps

1. **channel.py**: 
   - Remove lines 46-47 (module-level `_default_channel_registry` and registration)
   - Add `ChannelRegistry.register_defaults()` method that registers fake adapter
   - Keep `get_channel_registry()` but return empty registry (or provide factory)

2. **model.py**: 
   - Same pattern as channel.py

3. **tool.py**: 
   - Same pattern as tool.py

4. **main.py lifespan**:
   ```python
   # After getting registries, call register_defaults()
   channel_registry = get_channel_registry()
   channel_registry.register_defaults()
   
   model_registry = get_model_registry()
   model_registry.register_defaults()
   
   tool_registry = get_tool_registry()
   tool_registry.register_defaults()
   ```

### Verification

```python
# Test that importing modules does NOT populate registries
from waxprep.registries.channel import ChannelRegistry, get_channel_registry

# Before any registration call, registry should be empty
registry = get_channel_registry()
assert len(registry.list_all()) == 0  # Passes after fix

# After register_defaults(), it should have fake
registry.register_defaults()
assert "fake" in registry.list_all()  # Passes after fix
```

### What to Commit

Commit message: `refactor: remove import-time side effects from registries`

---

## PRIORITY 2: Add Request Correlation ID Middleware

### Problem
No request identification across logs. Hard to trace requests in structured logs.

### Solution
Add middleware that:
1. Generates or propagates X-Request-ID header
2. Binds request ID to structlog context
3. Simple implementation for Stage 02

### Files to Modify/Create

| File | Action |
|------|--------|
| `src/waxprep/main.py` | Add correlation ID middleware |
| `src/waxprep/middleware.py` | **CREATE** - Middleware module (optional, could keep in main.py) |

### Implementation Steps

1. Create `src/waxprep/middleware.py` with correlation ID middleware:

```python
import uuid
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add/request correlation ID to each request."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # Process request
        response = await call_next(request)
        
        # Add header to response
        response.headers["X-Request-ID"] = request_id
        
        return response
```

2. Add middleware to FastAPI app in `main.py`:

```python
from waxprep.middleware import CorrelationIdMiddleware

_app = FastAPI(
    ...
)

_app.add_middleware(CorrelationIdMiddleware)
```

### Verification

```python
def test_correlation_id_header(client):
    """Prove X-Request-ID header is added to responses."""
    response = client.get("/health/liveness")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0

def test_correlation_id_propagation(client):
    """Prove client-provided X-Request-ID is propagated."""
    request_id = "test-12345"
    response = client.get("/health/liveness", headers={"X-Request-ID": request_id})
    assert response.headers["X-Request-ID"] == request_id
```

### What to Commit

Commit message: `feat: add request correlation ID middleware`

---

## PRIORITY 3: Make Readiness Endpoint Meaningful

### Problem
Current `/health/readiness` just returns `{"status": "ready"}` without checking anything. No distinction from liveness.

### Solution
Check that:
1. Registries are initialized
2. Configuration is loaded
3. App state indicates readiness

### Files to Modify

| File | Changes |
|------|---------|
| `src/waxprep/main.py` | Modify readiness endpoint to check actual state |
| `src/waxprep/main.py` | Store registry references in app state during lifespan |

### Implementation Steps

1. Store registries in app state during lifespan:

```python
@app = FastAPI(...)

@app.state.channel_registry = None
@app.state.model_registry = None
@app.state.tool_registry = None

async def lifespan(app: FastAPI):
    # ... existing startup ...
    
    # Store in app state
    app.state.channel_registry = channel_registry
    app.state.model_registry = model_registry
    app.state.tool_registry = tool_registry
    
    yield
    
    # Cleanup on shutdown
    app.state.channel_registry = None
    app.state.model_registry = None
    app.state.tool_registry = None
```

2. Update readiness endpoint:

```python
@app.get("/health/readiness")
async def readiness() -> JSONResponse:
    """Readiness endpoint - checks if app is truly ready."""
    # Check registries are initialized
    if app.state.channel_registry is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "channel_registry_not_initialized"}
        )
    
    if app.state.model_registry is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "model_registry_not_initialized"}
        )
    
    if app.state.tool_registry is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "tool_registry_not_initialized"}
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready"}
    )
```

### Verification

```python
def test_readiness_returns_200_when_ready(client):
    """Prove readiness returns 200 when app is fully initialized."""
    response = client.get("/health/readiness")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"

def test_readiness_includes_detailed_status(client):
    """Prove readiness response includes meaningful status."""
    response = client.get("/health/readiness")
    data = response.json()
    assert "status" in data
    # In Stage 02, should be "ready" if all checks pass
```

### What to Commit

Commit message: `feat: make readiness endpoint check actual application state`

---

## PRIORITY 4: Add Global Exception Handler

### Problem
Unhandled exceptions may leak raw tracebacks or expose internal details.

### Solution
Add global exception handler that returns structured JSON errors.

### Files to Modify

| File | Changes |
|------|---------|
| `src/waxprep/main.py` | Add exception handlers |

### Implementation Steps

1. Add exception handlers in `main.py`:

```python
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions with structured response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.status_code,
                "message": exc.detail,
            }
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with structured response."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": 422,
                "message": "Validation error",
                "details": exc.errors(),
            }
        },
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all handler to prevent traceback leakage."""
    # Log the actual error with structlog
    structlog.get_logger().exception("Unhandled exception")
    
    # Return generic error (don't expose details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": 500,
                "message": "Internal server error",
            }
        },
    )
```

### Verification

```python
def test_http_exception_returns_json(client):
    """Prove HTTP exceptions return structured JSON."""
    response = client.get("/nonexistent-endpoint")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert "code" in data["error"]

def test_validation_error_returns_structured_response(client):
    """Prove validation errors return structured JSON."""
    # Test with an endpoint that has validation
    # (may need to add a test endpoint or use existing)
    pass
```

### What to Commit

Commit message: `feat: add global exception handlers to prevent traceback leakage`

---

## PRIORITY 5: Add Middleware Skeleton

### Problem
No established pattern for adding middleware. Future middleware additions may be inconsistent.

### Solution
Create a middleware module with:
1. Base middleware pattern
2. Correlation ID middleware (from Priority 2)
3. Placeholder for future middleware

### Files to Create/Modify

| File | Action |
|------|--------|
| `src/waxprep/middleware.py` | **CREATE** - Middleware module with patterns |

### Implementation Steps

Create `src/waxprep/middleware.py`:

```python
"""
Middleware - Stage 02
Foundation middleware patterns for future extension.
"""

import uuid
from typing import Callable, Awaitable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import structlog

logger = structlog.get_logger()


class BaseMiddleware(BaseHTTPMiddleware):
    """Base middleware class for WaxPrep.
    
    Extend this class to create new middleware.
    Override `process_request` and/or `process_response`.
    """
    
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        # Pre-processing
        await self.process_request(request)
        
        # Call next middleware / route handler
        response = await call_next(request)
        
        # Post-processing
        response = await self.process_response(request, response)
        
        return response
    
    async def process_request(self, request: Request) -> None:
        """Override to add pre-processing logic."""
        pass
    
    async def process_response(self, request: Request, response: Response) -> Response:
        """Override to add post-processing logic."""
        return response


class CorrelationIdMiddleware(BaseMiddleware):
    """Middleware to add/request correlation ID to each request."""
    
    async def process_request(self, request: Request) -> None:
        # Get or generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Bind to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        
        # Store for potential use in route handlers
        request.state.request_id = request_id
    
    async def process_response(self, request: Request, response: Response) -> Response:
        # Add header to response
        response.headers["X-Request-ID"] = request.state.request_id
        return response


# Middleware registry for easy composition
MIDDLEWARE_CLASSES = [
    CorrelationIdMiddleware,
    # Add future middleware classes here
]
```

### Verification

- Middleware module exists and is importable
- BaseMiddleware can be subclassed
- CorrelationIdMiddleware works (tested in Priority 2)

### What to Commit

Commit message: `feat: add middleware skeleton with base patterns`

---

## PRIORITY 6: Add Foundation Tests

### Problem
Existing tests don't verify:
- No import-time pollution
- Lifespan startup/shutdown order
- Health endpoint behavior under various conditions
- Config loading from environment

### Solution
Add comprehensive foundation tests.

### Files to Create/Modify

| File | Action |
|------|--------|
| `tests/test_foundation.py` | **CREATE** - Foundation tests |
| `tests/test_middleware.py` | **CREATE** - Middleware tests |
| `tests/test_main.py` | Modify - Add more comprehensive tests |

### Test Categories

#### 1. Import-Time Pollution Tests (`test_foundation.py`)

```python
class TestNoImportTimeSideEffects:
    """Prove registries don't populate at import time."""
    
    def test_channel_registry_empty_after_import(self):
        """Prove channel registry is empty after module import."""
        from waxprep.registries.channel import ChannelRegistry, get_channel_registry
        registry = get_channel_registry()
        assert len(registry.list_all()) == 0
    
    def test_model_registry_empty_after_import(self):
        """Prove model registry is empty after module import."""
        from waxprep.registries.model import ModelRegistry, get_model_registry
        registry = get_model_registry()
        assert len(registry.list_all()) == 0
    
    def test_tool_registry_empty_after_import(self):
        """Prove tool registry is empty after module import."""
        from waxprep.registries.tool import ToolRegistry, get_tool_registry
        registry = get_tool_registry()
        assert len(registry.list_all()) == 0
    
    def test_register_defaults_populates_registries(self):
        """Prove register_defaults() populates registries."""
        from waxprep.registries.channel import get_channel_registry
        from waxprep.registries.model import get_model_registry
        from waxprep.registries.tool import get_tool_registry
        
        channel_reg = get_channel_registry()
        channel_reg.register_defaults()
        assert "fake" in channel_reg.list_all()
        
        model_reg = get_model_registry()
        model_reg.register_defaults()
        assert "fake" in model_reg.list_all()
        
        tool_reg = get_tool_registry()
        tool_reg.register_defaults()
        assert "fake_tool" in tool_reg.list_all()
```

#### 2. Lifespan Order Tests (`test_foundation.py`)

```python
class TestLifespanOrder:
    """Prove lifespan startup/shutdown order."""
    
    def test_startup_initializes_registries(self, client):
        """Prove registries are initialized during startup."""
        # After app starts, registries should be populated
        # (requires access to app state or registry state)
        pass
    
    def test_shutdown_clears_state(self):
        """Prove shutdown clears application state."""
        pass
```

#### 3. Health Endpoint Tests (`test_main.py` - extend)

```python
class TestReadinessWithState:
    """Test readiness behavior based on app state."""
    
    def test_readiness_returns_200_when_registered(self, client):
        """Prove readiness returns 200 when registries are initialized."""
        response = client.get("/health/readiness")
        assert response.status_code == 200
    
    def test_readiness_response_structure(self, client):
        """Prove readiness response has expected structure."""
        response = client.get("/health/readiness")
        data = response.json()
        assert "status" in data
```

#### 4. Config Loading Tests (`test_config.py` - extend)

```python
class TestConfigFromEnvironment:
    """Prove config loads from environment variables."""
    
    def test_all_settings_from_env(self, monkeypatch):
        """Prove all settings can be set via environment."""
        monkeypatch.setenv("WAXPREP_ENVIRONMENT", "production")
        monkeypatch.setenv("WAXPREP_HOST", "127.0.0.1")
        monkeypatch.setenv("WAXPREP_PORT", "9000")
        monkeypatch.setenv("WAXPREP_SHUTDOWN_GRACE_PERIOD", "60")
        monkeypatch.setenv("WAXPREP_LOG_LEVEL", "debug")
        
        from waxprep.config import Settings
        settings = Settings()
        
        assert settings.environment == "production"
        assert settings.host == "127.0.0.1"
        assert settings.port == 9000
        assert settings.shutdown_grace_period == 60
        assert settings.log_level == "debug"
```

#### 5. Middleware Tests (`test_middleware.py`)

```python
class TestCorrelationIdMiddleware:
    """Test correlation ID middleware behavior."""
    
    def test_header_added_to_response(self, client):
        """Prove X-Request-ID header is added."""
        response = client.get("/health/liveness")
        assert "X-Request-ID" in response.headers
    
    def test_client_request_id_propagated(self, client):
        """Prove client-provided X-Request-ID is used."""
        request_id = "client-123"
        response = client.get(
            "/health/liveness",
            headers={"X-Request-ID": request_id}
        )
        assert response.headers["X-Request-ID"] == request_id
    
    def test_request_id_is_uuid_format(self, client):
        """Prove generated request IDs are valid UUIDs."""
        response = client.get("/health/liveness")
        import uuid
        request_id = response.headers["X-Request-ID"]
        # Should be valid UUID (either client-provided or generated)
        try:
            uuid.UUID(request_id)
        except ValueError:
            pytest.fail(f"Invalid UUID format: {request_id}")
```

### What to Commit

Commit message: `test: add foundation tests for import-time pollution, lifespan, and config`

---

## Order of Operations

### Recommended Execution Order

1. **Priority 1: Remove Import-Time Side Effects**
   - Must be done first because tests for Priority 6 depend on this behavior
   - Changes registries to expose `register_defaults()`

2. **Priority 5: Add Middleware Skeleton** (can be done in parallel with 2)
   - Creates the module structure
   - Establishes patterns

3. **Priority 2: Add Request Correlation ID Middleware**
   - Uses the middleware skeleton
   - Simple implementation

4. **Priority 3: Make Readiness Endpoint Meaningful**
   - Depends on registries being properly initialized in lifespan (Priority 1)

5. **Priority 4: Add Global Exception Handler**
   - Independent, can be done anytime

6. **Priority 6: Add Foundation Tests**
   - Should be done last to verify all changes
   - Tests prove the fixes work

---

## File Summary

### Files to Modify

| File | Reason |
|------|--------|
| `src/waxprep/registries/channel.py` | Remove import-time registration, add `register_defaults()` |
| `src/waxprep/registries/model.py` | Remove import-time registration, add `register_defaults()` |
| `src/waxprep/registries/tool.py` | Remove import-time registration, add `register_defaults()` |
| `src/waxprep/main.py` | Add middleware, update readiness, add exception handlers, call `register_defaults()` in lifespan |

### Files to Create

| File | Purpose |
|------|---------|
| `src/waxprep/middleware.py` | Middleware module with BaseMiddleware and CorrelationIdMiddleware |
| `tests/test_foundation.py` | Tests for import-time pollution, lifespan order |
| `tests/test_middleware.py` | Tests for correlation ID middleware |

### Files to Modify (Tests)

| File | Changes |
|------|---------|
| `tests/test_main.py` | Add readiness response structure tests |
| `tests/test_config.py` | Add environment variable loading tests |

---

## Verification Checklist

After all changes:

- [ ] Importing registry modules does NOT populate them
- [ ] `register_defaults()` populates registries with fake adapters
- [ ] Lifespan calls `register_defaults()` during startup
- [ ] `/health/readiness` returns 200 when app is initialized
- [ ] `/health/readiness` returns 503 if registries not initialized
- [ ] X-Request-ID header is present on all responses
- [ ] Client-provided X-Request-ID is propagated
- [ ] Unhandled exceptions return generic 500 JSON, not tracebacks
- [ ] Validation errors return structured 422 JSON
- [ ] Tests pass: `pytest tests/ -v`
- [ ] No import-time side effects detected by tests

---

## Commit Strategy

### Commit 1: Remove Import-Time Side Effects
```
refactor: remove import-time side effects from registries

- Remove module-level fake adapter registration in channel.py, model.py, tool.py
- Add register_defaults() method to each registry
- Registries now start empty, populated explicitly during lifespan
```

### Commit 2: Add Middleware Infrastructure
```
feat: add middleware skeleton and correlation ID middleware

- Create src/waxprep/middleware.py with BaseMiddleware pattern
- Add CorrelationIdMiddleware for request ID generation/propagation
- Bind request ID to structlog context
- Add middleware to FastAPI app
```

### Commit 3: Improve Health Endpoints
```
feat: make readiness endpoint check actual application state

- Store registries in app.state during lifespan
- Readiness endpoint checks registries are initialized
- Returns 503 if not ready, 200 if ready
```

### Commit 4: Add Exception Handlers
```
feat: add global exception handlers to prevent traceback leakage

- Add HTTP exception handler with structured JSON response
- Add validation error handler with details
- Add catch-all handler that logs and returns generic 500
```

### Commit 5: Add Foundation Tests
```
test: add foundation tests for import-time pollution, lifespan, config

- Test registries are empty after import
- Test register_defaults() populates registries
- Test correlation ID middleware behavior
- Test config loads from environment variables
- Test health endpoint response structures
```
