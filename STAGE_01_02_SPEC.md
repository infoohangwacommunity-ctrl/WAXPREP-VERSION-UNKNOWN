# WaxPrep Foundation - Stage 01-02 Specification

**Extracted from source code:** `/workspaces/WAXPREP-VERSION-UNKNOWN`
**Version:** 0.1.0
**Python Requirement:** >=3.14, <3.16

---

## 1. What the Application Does

The WaxPrep Foundation is a **minimal ASGI runtime foundation** that establishes the architectural patterns for a multi-channel AI tutoring system. It does **NOT** implement any business logic.

### Core Functionality (from code):

1. **ASGI Application** (`main.py`)
   - FastAPI application with lifespan context manager
   - Exposes health endpoints and root endpoint
   - Handles graceful shutdown via signal handlers

2. **Registry System** (`registries/`)
   - Generic `BaseRegistry[T]` abstract base class
   - Three specialized registries: `ChannelRegistry`, `ModelRegistry`, `ToolRegistry`
   - Each registry uses Protocol-based adapter contracts
   - Pre-seeded with fake adapters to prove architecture

3. **Configuration** (`config.py`)
   - Pydantic Settings-based configuration
   - All values from environment variables (WAXPREP_ prefix)
   - No hardcoded values anywhere

4. **Fake Adapters** (`adapters/`)
   - `FakeChannelAdapter` - proves channel registry works
   - `FakeModelAdapter` - proves model registry works
   - `FakeTool` - proves tool registry works
   - These are NOT real implementations; they exist only to validate the registry pattern

---

## 2. What Stage 01-02 Includes

### Stage 01: Programming Language Foundation
- Python 3.14+ runtime
- uv for dependency management
- Pydantic v2 for data validation
- Static type checking (mypy/pyright with strict mode)
- hatchling build system

### Stage 02: Runtime and Execution Environment

**Application Structure:**
```
src/waxprep/
├── __init__.py          # Version declaration, scope statement
├── main.py              # FastAPI ASGI app, health endpoints, shutdown
├── config.py            # Pydantic Settings configuration
├── registries/
│   ├── __init__.py
│   ├── base.py          # BaseRegistry[T] abstract class
│   ├── channel.py       # ChannelRegistry + ChannelAdapter protocol
│   ├── model.py         # ModelRegistry + ModelAdapter protocol
│   └── tool.py          # ToolRegistry + Tool protocol
├── adapters/
│   ├── __init__.py
│   ├── fake_channel.py  # FakeChannelAdapter
│   ├── fake_model.py    # FakeModelAdapter
│   └── fake_tool.py     # FakeTool
└── services/
    └── __init__.py      # Empty placeholder
```

**Dependencies:**
- `fastapi>=0.109.0`
- `uvicorn[standard]>=0.27.0`
- `pydantic>=2.5.0`
- `pydantic-settings>=2.1.0`
- `httpx>=0.26.0`
- `structlog>=23.2.0`
- `python-dotenv>=1.0.0`

**Dev Dependencies:**
- `pytest>=9.2.0`
- `pytest-asyncio>=1.4.1.post1`
- `mypy>=1.8.0` (strict mode)
- `pyright>=1.1.0` (strict mode)
- `ruff>=0.1.0`

---

## 3. What's Explicitly Excluded

### From README.md and Code:

**NOT included (later stages):**
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

### From __init__.py Scope Statement:
> "NO tutor logic. NO channel adapters. NO database schema. Only the foundation for the foundation."

### From main.py Scope Statement:
> "NO tutor logic. NO real adapters. Only foundation."

### NO Hardcoding Rule (from README.md):
- ❌ NO model names hardcoded
- ❌ NO API keys hardcoded
- ❌ NO ports hardcoded
- ❌ NO timeouts hardcoded
- ❌ NO grace periods hardcoded
- ❌ NO channel identifiers hardcoded
- ❌ NO student levels hardcoded
- ❌ NO greetings hardcoded
- ❌ NO keyword routes hardcoded

> "All configuration lives in environment variables or test fixtures."

---

## 4. Registry Pattern Contract

### BaseRegistry Generic Contract (`registries/base.py`):

```python
class BaseRegistry(ABC, Generic[T]):
    """Base registry class. NO hardcoded adapters."""

    def __init__(self) -> None:
        self._items: Dict[str, T] = {}

    @abstractmethod
    def register(self, name: str, item: T) -> None:
        """Register an item. Must validate before registering."""
        pass

    def get(self, name: str) -> T:
        """Get a registered item by name."""
        if name not in self._items:
            raise KeyError(f"No item registered with name: {name}")
        return self._items[name]

    def list_all(self) -> List[str]:
        """List all registered item names."""
        return list(self._items.keys())

    def is_registered(self, name: str) -> bool:
        """Check if an item is registered."""
        return name in self._items
```

**Contract Requirements:**
1. `__init__` initializes empty `Dict[str, T]`
2. `register()` is abstract - subclasses MUST implement validation
3. `get()` raises `KeyError` if not found (not returning None)
4. `list_all()` returns `List[str]` of keys
5. `is_registered()` returns `bool`

### ChannelRegistry Contract (`registries/channel.py`):

**Protocol Requirements:**
```python
@runtime_checkable
class ChannelAdapter(Protocol):
    name: str
    async def handle_message(self, message: dict) -> dict: ...
```

**Validation in register():**
- Adapter MUST have `name` attribute
- Adapter MUST have `handle_message` method
- Raises `ValueError` if validation fails

**Default Registry:**
- Pre-seeded with `FakeChannelAdapter()` under name "fake"
- Singleton pattern via module-level `_default_channel_registry`

### ModelRegistry Contract (`registries/model.py`):

**Protocol Requirements:**
```python
@runtime_checkable
class ModelAdapter(Protocol):
    name: str
    async def generate(self, prompt: str) -> str: ...
```

**Validation in register():**
- Adapter MUST have `name` attribute
- Adapter MUST have `generate` method
- Raises `ValueError` if validation fails

**Default Registry:**
- Pre-seeded with `FakeModelAdapter()` under name "fake"
- Singleton pattern via module-level `_default_model_registry`

### ToolRegistry Contract (`registries/tool.py`):

**Protocol Requirements:**
```python
@runtime_checkable
class Tool(Protocol):
    name: str
    async def execute(self, **kwargs) -> dict: ...
```

**Validation in register():**
- Tool MUST have `name` attribute
- Tool MUST have `execute` method
- Raises `ValueError` if validation fails

**Default Registry:**
- Pre-seeded with `FakeTool()` under name "fake_tool"
- Singleton pattern via module-level `_default_tool_registry`

### Adapter Contracts (from fake adapters):

**FakeChannelAdapter:**
- `name = "fake"` (class attribute)
- `async def handle_message(self, message: dict) -> dict`
- Returns: `{"status": "fake_processed", "message_id": ..., "channel": "fake"}`

**FakeModelAdapter:**
- `name = "fake"` (class attribute)
- `async def generate(self, prompt: str) -> str`
- Returns: `f"Fake response to: {prompt[:50]}..."`

**FakeTool:**
- `name = "fake_tool"` (class attribute)
- `async def execute(self, **kwargs) -> dict`
- Returns: `{"status": "fake_executed", "input": kwargs, "tool": "fake_tool"}`

---

## 5. Configuration Requirements

### Settings Class (`config.py`):

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="WAXPREP_",  # All env vars must use WAXPREP_ prefix
    )

    # Application
    environment: str = Field(default="development")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)

    # Shutdown - configurable, NOT hardcoded
    shutdown_grace_period: int = Field(default=30)

    # Logging
    log_level: str = Field(default="info")
```

**Required Environment Variables (all optional with defaults):**

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `WAXPREP_ENVIRONMENT` | str | "development" | Runtime environment |
| `WAXPREP_HOST` | str | "0.0.0.0" | Bind host |
| `WAXPREP_PORT` | int | 8000 | Bind port |
| `WAXPREP_SHUTDOWN_GRACE_PERIOD` | int | 30 | Grace period in seconds |
| `WAXPREP_LOG_LEVEL` | str | "info" | Logging level |

**Critical Configuration Contract:**
- `shutdown_grace_period` MUST be configurable (test proves this)
- Hardcoded `asyncio.sleep(30)` is FORBIDDEN
- All values load from `.env` file or environment
- `WAXPREP_` prefix prevents conflicts with sandbox env vars

---

## 6. Health Endpoint Behavior

### Endpoints Defined (`main.py`):

#### GET `/health/liveness`
- **Purpose:** "Is the process alive?"
- **Response:** `200 OK` with `{"status": "alive"}`
- **Implementation:** Always returns 200 if process is running
- **Semantic:** Process-level health check

#### GET `/health/readiness`
- **Purpose:** "Is the application ready?"
- **Response:** `200 OK` with `{"status": "ready"}`
- **Implementation:** In Stages 01-02, always returns 200
- **Semantic:** Application-level readiness (later stages will check dependencies)
- **Key Distinction:** Liveness ≠ Readiness (proven by test)

#### GET `/`
- **Purpose:** Root endpoint proving app is running
- **Response:** `200 OK` with:
  ```json
  {
    "message": "WaxPrep Foundation - Stages 01-02 ONLY",
    "stages": ["01", "02"],
    "status": "running"
  }
  ```

### Health Endpoint Test Requirements (`test_main.py`):

1. `test_liveness_endpoint`: Returns 200 with `{"status": "alive"}`
2. `test_readiness_endpoint`: Returns 200 with `{"status": "ready"}`
3. `test_liveness_not_equal_readiness`: Proves endpoints are distinct
   - Both return 200 in Stages 01-02
   - Different JSON payloads
   - Different purposes (documented in code)

---

## 7. Graceful Shutdown Behavior

### Implementation (`main.py`):

**Global State:**
```python
_app: Optional[FastAPI] = None
_shutting_down: bool = False
```

**Lifespan Context Manager:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup sequence:
    # 1. Load configuration
    # 2. Initialize registries (channel, model, tool)
    # 3. External clients - NONE in Stages 01-02
    # 4. Background services - NONE in Stages 01-02
    # 5. Log startup

    yield

    # Shutdown sequence:
    _shutting_down = True
    logger.info("Stage 02: Shutdown started")
    logger.info("Stage 02: Shutdown complete")
```

**Signal Handlers:**
```python
def handle_shutdown(signum: int, frame: object) -> None:
    """Handle SIGTERM for graceful shutdown."""
    global _shutting_down
    if _shutting_down:
        return  # Prevent duplicate handling
    
    _shutting_down = True
    logger.info("SIGTERM received - graceful shutdown initiated")
    sys.exit(0)  # In real ASGI server, this triggers lifespan shutdown
```

**Registered Signals:**
- `signal.SIGTERM` → `handle_shutdown`
- `signal.SIGINT` → `handle_shutdown`

### Shutdown Contract Requirements:

1. **Idempotent handling:** If `_shutting_down` is already True, return immediately
2. **Logging:** Log shutdown start and completion
3. **Configuration:** Grace period from `settings.shutdown_grace_period` (NOT hardcoded)
4. **Stage 01-02 scope:** No external client cleanup, no background service shutdown (none exist)

### Test Requirement:
- `test_shutdown_grace_period_not_hardcoded` proves grace period is configurable
- Must be able to change via `WAXPREP_SHUTDOWN_GRACE_PERIOD` environment variable

---

## 8. Testing Requirements

### Test Files:

#### `tests/test_config.py` - Configuration Tests

**Class: `TestNoHardcoding`**
- `test_port_not_hardcoded`: Proves port is configurable
- `test_host_not_hardcoded`: Proves host is configurable  
- `test_shutdown_grace_period_not_hardcoded`: **Critical** - proves grace period is NOT hardcoded
- `test_environment_not_hardcoded`: Proves environment is configurable
- `test_log_level_not_hardcoded`: Proves log level is configurable

#### `tests/test_main.py` - Application Tests

**Fixture:** `client` - TestClient for FastAPI app

**Class: `TestHealthEndpoints`**
- `test_liveness_endpoint`: Liveness returns `{"status": "alive"}`
- `test_readiness_endpoint`: Readiness returns `{"status": "ready"}`
- `test_liveness_not_equal_readiness`: Proves conceptual distinction

**Class: `TestRootEndpoint`**
- `test_root_endpoint`: Root returns foundation info with stages ["01", "02"]

#### `tests/test_registries.py` - Registry Tests

**Class: `TestChannelRegistry`**
- `test_fake_adapter_has_name`: FakeChannelAdapter has `name = "fake"`
- `test_fake_adapter_has_handle_message`: Has callable `handle_message`
- `test_channel_registry_register`: Can register adapters
- `test_channel_registry_get`: Can retrieve by name
- `test_channel_registry_list_all`: Can list all names
- `test_default_channel_registry_has_fake`: Default registry has "fake"

**Class: `TestModelRegistry`**
- `test_fake_adapter_has_name`: FakeModelAdapter has `name = "fake"`
- `test_fake_adapter_has_generate`: Has callable `generate`
- `test_model_registry_register`: Can register adapters
- `test_default_model_registry_has_fake`: Default registry has "fake"

**Class: `TestToolRegistry`**
- `test_fake_tool_has_name`: FakeTool has `name = "fake_tool"`
- `test_fake_tool_has_execute`: Has callable `execute`
- `test_tool_registry_register`: Can register tools
- `test_default_tool_registry_has_fake`: Default registry has "fake_tool"

### Testing Infrastructure:
- pytest with pytest-asyncio
- FastAPI TestClient for HTTP tests
- No real external dependencies (all fake)

---

## 9. Implicit Contracts (What Code Requires to Work)

### Startup Order Contract:
1. Configuration MUST load before registries initialize
2. Registries MUST be initialized during lifespan startup
3. All three registries (channel, model, tool) MUST be available after startup

### Registry State Contract:
- Default registries are singletons created at module import time
- Default registries are pre-seeded with fake adapters
- `get_*_registry()` functions return the singleton instances

### Adapter Validation Contract:
- All adapters MUST be validated before registration
- Validation checks for required attributes and methods
- Invalid adapters raise `ValueError`, not silent failure

### Error Handling Contract:
- `BaseRegistry.get()` raises `KeyError` for missing items (not returning None)
- Registry `register()` raises `ValueError` for invalid adapters

### Signal Handling Contract:
- SIGTERM and SIGINT both trigger graceful shutdown
- Shutdown handler is idempotent (safe to call multiple times)
- Signal handlers registered at module import time

### Logging Contract:
- structlog configured with JSONRenderer
- Context vars merged into all log entries
- Startup/shutdown events logged with stage information

---

## 10. File Manifest (Stage 01-02)

```
waxprep-foundation/
├── .env.example              # Example environment variables
├── .gitignore
├── pyproject.toml            # Project config, dependencies
├── README.md                 # Scope statement, exclusions
├── src/waxprep/
│   ├── __init__.py           # Version, scope statement
│   ├── main.py               # ASGI app, health endpoints, shutdown
│   ├── config.py             # Pydantic Settings
│   ├── registries/
│   │   ├── __init__.py
│   │   ├── base.py           # BaseRegistry[T]
│   │   ├── channel.py        # ChannelRegistry + ChannelAdapter
│   │   ├── model.py          # ModelRegistry + ModelAdapter
│   │   └── tool.py           # ToolRegistry + Tool
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── fake_channel.py   # FakeChannelAdapter
│   │   ├── fake_model.py     # FakeModelAdapter
│   │   └── fake_tool.py      # FakeTool
│   └── services/
│       └── __init__.py       # Empty placeholder
└── tests/
    ├── __init__.py
    ├── test_config.py        # Configuration tests
    ├── test_main.py          # App/health tests
    └── test_registries.py    # Registry tests
```

---

## Summary: Stage 01-02 Foundation Contract

The WaxPrep Foundation Stage 01-02 provides:

1. **A verified Python 3.14+ runtime environment** with strict type checking
2. **An ASGI application skeleton** (FastAPI + uvicorn) with ordered startup/shutdown
3. **Three registry patterns** (channel, model, tool) with Protocol-based contracts
4. **Fake adapters** that prove the registry architecture works without real implementations
5. **Configuration via environment** with NO hardcoded values (explicitly tested)
6. **Health endpoints** that distinguish liveness from readiness
7. **Graceful shutdown** via signal handlers with configurable grace period
8. **Structured logging** with JSON output and correlation support

**This foundation MUST NOT be extended with:**
- Real channel implementations (WhatsApp, Telegram)
- Real model providers (AI APIs)
- Real tools (executors)
- Tutor business logic
- Database schemas
- Student domain logic

**Upgrades to later stages MUST preserve:**
- The registry pattern contracts (BaseRegistry, protocols, validation)
- The configuration system (WAXPREP_ prefix, no hardcoded values)
- The health endpoint distinction (liveness ≠ readiness)
- The graceful shutdown mechanism (signal handlers, configurable grace period)
- The test coverage proving these contracts
