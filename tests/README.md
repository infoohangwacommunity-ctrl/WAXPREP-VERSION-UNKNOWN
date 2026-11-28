# Tests Reference

Hermetic, isolated, deterministic tests.

## Categories

| Category | Marker | Directory | Purpose |
|----------|--------|-----------|---------|
| **Unit** | `@pytest.mark.unit` | `tests/unit/` | Pure-function tests — no I/O, no app, no state. Fast, isolated, the foundation. Includes Stage 18 dependency-graph validation/building and Stage 19 job registration/dispatch. |
| **Integration** | `@pytest.mark.integration` | `tests/integration/` | App + real dependencies. Tests exception handlers, registries, composition/lifecycle wiring, Taskiq background runtime/worker, and the main FastAPI app through the TestClient. |
| **Contract** | `@pytest.mark.contract` | `tests/contract/` | Stage 17 typed DTOs, envelopes, validation, versioning/compatibility, schema drift, CLI, protocols, properties and adversarial inputs. |
| **Lifecycle** | `@pytest.mark.lifecycle` | `tests/lifecycle/` | Stage 16 state transitions, rollback, reverse cleanup, cancellation, background-task ownership, isolation and ASGI lifespan behaviour. `test_lifecycle_static.py` also runs under the architecture marker. |
| **Architecture** | `@pytest.mark.architecture` | `tests/architecture/` | Boundary and dependency checks — ensures modules don't import across forbidden boundaries, concrete adapters stay in composition, the worker does not import FastAPI, and no global dependency graph exists. |
| **Configuration** | `@pytest.mark.configuration` | `tests/configuration/` | Settings and environment variable handling: config load, env precedence, defaults, and validation. |
| **Regression** | `@pytest.mark.regression` | `tests/regression/` | Pinned bug-fix tests — each test names the bug it guards against. Should never be deleted. |
| **Detector** | none (not in the CI matrix) | `tests/detector/` | Stage 08 Universal Hardcoding Detector rule, adversarial, CLI, quality-gate and property tests. Executed by the full-suite coverage job. |

> **Note:** The `regression/` directory currently contains no pinned tests, and the CI test matrix does not include a separate regression job. Tests added to `tests/regression/` are still executed by the full-suite coverage job (`--cov-fail-under=100`).

Two files under `tests/integration/` (`test_exception_handler_pattern.py`, `test_final_coverage.py`) cover pattern documentation and final coverage assertions respectively.

## Running Tests

**Prerequisite:** sync dev dependencies once:

```bash
uv sync --extra dev
```

**Full suite:**

```bash
uv run pytest tests/ -v
```

**Specific category:**

```bash
uv run pytest tests/unit/           -v   # unit only
uv run pytest tests/integration/    -v   # integration only
uv run pytest tests/contract/       -v   # contract only
uv run pytest tests/lifecycle/      -v   # lifecycle only
uv run pytest tests/architecture/   -v   # architecture only
uv run pytest tests/configuration/ -v   # configuration only
uv run pytest tests/regression/     -v   # regression only
uv run pytest tests/detector/       -v   # hardcoding detector only (no category marker)
```

**By marker (any directory):**

```bash
uv run pytest tests/ -v -m unit
uv run pytest tests/ -v -m "not regression"
```

**Parallel execution** (when you have cores to burn):

```bash
uv run pytest tests/ -n auto -v
```

## Fixtures (`conftest.py`)

Most fixtures are opt-in — request the ones you need. One fixture is **autouse**:

- `_reset_main_globals` — **autouse**. Resets `waxprep.main` module globals (`_shutting_down`, `_registries_ready`, `_channel_registry`, `_model_registry`, `_tool_registry`) after every test. This guarantees test isolation so lifecycle/integration tests cannot poison each other through shared module state.

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

File: `.github/workflows/quality-gate.yml` — **Quality Gate**.

**Triggers:**
- Push to `main`
- Pull requests targeting `main`

**Jobs:**

| Job | Command | Notes |
|-----|---------|-------|
| `quality-setup` | `uv sync --extra dev` + uv cache | Runs once; warms shared package cache |
| `quality-gate` | ruff, ruff format, mypy, import-linter, semgrep, pip-audit, hardcoding detector | Blocking static analysis |
| `tests` | `pytest tests/<category> -m <category>` | Matrix: unit, integration, contract, lifecycle, architecture, configuration |
| `coverage-gate` | full suite `--cov-fail-under=100` | Blocking, 100% threshold |
| `smoke-test` | app boot + liveness/readiness health checks | Blocking |
| `pyright` | `pyright src/ || true` | Advisory — does not block |
| `vulture` | `vulture src/waxprep/ || true` | Advisory — does not block |

The `gate-aggregate` job reports blocking-job status and fails if any blocking job fails or is cancelled. Advisory jobs run independently and their results are not part of the aggregate decision.

## Coverage

- **pytest-cov** is in the dev dependencies.
- Run with coverage: `uv run pytest tests/ --cov=waxprep --cov-report=term-missing`
- `tests/integration/test_final_coverage.py` asserts final coverage thresholds — it's part of the suite, not a separate step.
- The coverage configuration excludes `waxprep/detector/quality_gate.py` (see `pyproject.toml`); that module is an integration wrapper around the detector core.

## Philosophy

1. **Hermetic** — Tests don't read the environment, the filesystem, network, or shared state unless they explicitly opt into it. No hidden dependencies.
2. **Isolated** — Each test gets fresh fixtures. Registries are never singletons; every test constructs its own. No test influences another.
3. **Deterministic** — Time and randomness are controlled via opt-in fixtures (`frozen_time`, `seeded_random`). Because they're not autouse, a test that doesn't request them remains visibly non-deterministic.
4. **Marked** — Every test has a category marker. The CI splits categories into separate jobs so a slow integration test can't hide behind a fast unit test.
5. **Contract-first** — Interfaces are tested independently of implementations, so refactors catch surprises early.
