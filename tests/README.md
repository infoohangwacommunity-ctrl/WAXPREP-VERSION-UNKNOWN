# Tests Reference — Stage 05

Hermetic, isolated, deterministic tests. Full suite runs in under 30 seconds.

## Categories

| Category | Marker | Directory | Purpose |
|----------|--------|-----------|---------|
| **Unit** | `@pytest.mark.unit` | `tests/unit/` | Pure-function tests — no I/O, no app, no state. Fast, isolated, the foundation. |
| **Integration** | `@pytest.mark.integration` | `tests/integration/` | App + real dependencies. Tests exception handlers, registries, and the main FastAPI app end-to-end through the TestClient. |
| **Contract** | `@pytest.mark.contract` | `tests/contract/` | Interface compliance — protocols and type contracts that modules must satisfy. |
| **Lifecycle** | `@pytest.mark.lifecycle` | `tests/lifecycle/` | Startup/shutdown behavior, app lifecycle hooks, and fixture teardown correctness. |
| **Architecture** | `@pytest.mark.architecture` | `tests/architecture/` | Boundary and dependency checks — ensures modules don't import across forbidden boundaries. |
| **Configuration** | `@pytest.mark.configuration` | `tests/configuration/` | Settings and environment variable handling: config load, env precedence, defaults, and validation. |
| **Regression** | `@pytest.mark.regression` | `tests/regression/` | Pinned bug-fix tests — each test names the bug it guards against. Should never be deleted. |

Two top-level files (`test_exception_handler_pattern.py`, `test_final_coverage.py`) cover pattern documentation and final coverage assertions respectively.

## Running Tests

**Prerequisite:** sync dev dependencies once:

```bash
uv sync --extra dev
```

**Full suite:**

```bash
uv run --dev pytest tests/ -v
```

**Specific category:**

```bash
uv run --dev pytest tests/unit/           -v   # unit only
uv run --dev pytest tests/integration/    -v   # integration only
uv run --dev pytest tests/contract/       -v   # contract only
uv run --dev pytest tests/lifecycle/      -v   # lifecycle only
uv run --dev pytest tests/architecture/   -v   # architecture only
uv run --dev pytest tests/configuration/  -v   # configuration only
uv run --dev pytest tests/regression/     -v   # regression only
```

**By marker (any directory):**

```bash
uv run --dev pytest tests/ -v -m unit
uv run --dev pytest tests/ -v -m "not regression"
```

**Parallel execution** (when you have cores to burn):

```bash
uv run --dev pytest tests/ -n auto -v
```

## Fixtures (`conftest.py`)

All fixtures are opt-in — none are `autouse`. Request the ones you need.

### Time control

| Fixture | What it does |
|---------|-------------|
| `frozen_time` | Freezes time at `2026-01-01 00:00:00 UTC` via freezegun. Opt-in only — no `request.param` needed. |

### Randomness

| Fixture | What it does |
|---------|-------------|
| `seeded_random` | Seeds `random` (stdlib) at 42. Opt-in only — not autouse, so non-deterministic tests stay detectable. |

### App & client

| Fixture | What it does |
|---------|-------------|
| `app` | Returns the FastAPI app instance (`get_app()`). |
| `client` | Returns a `TestClient` wrapping `app`, with proper context-manager teardown. Depends on `app`. |

### Registries (fresh instances, never singletons)

| Fixture | What it does |
|---------|-------------|
| `fresh_channel_registry` | New `ChannelRegistry()`, no defaults. |
| `fresh_model_registry` | New `ModelRegistry()`, no defaults. |
| `fresh_tool_registry` | New `ToolRegistry()`, no defaults. |
| `populated_channel_registry` | Fresh `ChannelRegistry` with `register_defaults()` called. |
| `populated_model_registry` | Fresh `ModelRegistry` with `register_defaults()` called. |
| `populated_tool_registry` | Fresh `ToolRegistry` with `register_defaults()` called. |

### Mocks

| Fixture | What it does |
|---------|-------------|
| `mock_registry` | `MagicMock` simulating a registry. |
| `mock_adapter` | `MagicMock` simulating a registry adapter. |

### Built-in (pytest)

- **`monkeypatch`** — available everywhere. Patch env vars, attributes, `sys.path`.

## CI Workflow

File: `.github/workflows/test.yml` — **Test Suite**.

**Triggers:**
- Push to `main` or `develop`
- Pull requests targeting `main`
- Daily cron (`0 0 * * *`) — flake detection run

**Jobs (parallel, each with its own Ubuntu runner and 5-minute timeout):**

| Job | Command | Notes |
|-----|---------|-------|
| `unit-tests` | `uv run pytest tests/unit/ -v --tb=short` | `TIMEOUT=10` env |
| `integration-tests` | `uv run pytest tests/integration/ -v --tb=short` | `TIMEOUT=30` env |
| `contract-tests` | `uv run pytest tests/contract/ -v --tb=short` | |
| `lifecycle-tests` | `uv run pytest tests/lifecycle/ -v --tb=short` | |
| `architecture-tests` | `uv run pytest tests/architecture/ -v --tb=short` | |
| `configuration-tests` | `uv run pytest tests/configuration/ -v --tb=short` | |
| `full-test-suite` | `uv run pytest tests/ -v --tb=short` | Only on `main` branch, `TIMEOUT=60` |
| `flake-detection` | 10 consecutive runs of unit + integration | Only on cron schedule; fails if any run fails |

Concurrency group: `${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true`.

## Coverage

- **pytest-cov** is in the dev dependencies.
- Run with coverage: `uv run --dev pytest tests/ --cov=waxprep --cov-report=term-missing`
- `test_final_coverage.py` (top-level) asserts final coverage thresholds — it's part of the suite, not a separate step.

## Philosophy

1. **Hermetic** — Tests don't read the environment, the filesystem, network, or shared state unless they explicitly opt into it. No hidden dependencies.
2. **Isolated** — Each test gets fresh fixtures. Registries are never singletons; every test constructs its own. No test influences another.
3. **Deterministic** — Time and randomness are controlled via opt-in fixtures (`frozen_time`, `seeded_random`). Because they're not autouse, a test that doesn't request them remains visibly non-deterministic.
4. **Fast** — The full suite is designed to run in under 30 seconds so it can be run constantly.
5. **Marked** — Every test has a category marker. The CI splits categories into separate jobs so a slow integration test can't hide behind a fast unit test.
6. **Contract-first** — Interfaces are tested independently of implementations, so refactors catch surprises early.
