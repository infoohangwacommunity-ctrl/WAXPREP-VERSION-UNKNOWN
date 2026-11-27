# Lifecycle Testing (Stage 16)

How lifecycle correctness is proven. Line coverage alone is explicitly not
accepted as evidence.

---

## 1. Where the tests live

| File | Purpose |
|---|---|
| `tests/lifecycle/test_lifecycle.py` | State machine, manager, resources, cancellation, concurrency, background tasks, ASGI integration, Hypothesis sequences |
| `tests/lifecycle/test_lifecycle_static.py` | AST ownership check: only the supervisor may create tasks |
| `tests/integration/` | Existing app/health/error tests now run against per-instance lifecycle state |
| `tests/observability/test_telemetry.py` | Metrics reset after provider shutdown and exporter lifecycle |

All lifecycle tests are marked `@pytest.mark.lifecycle`; static ownership tests
are marked `@pytest.mark.architecture`. Existing markers and the CI matrix are
unchanged.

## 2. Required behaviour categories

| Category | Examples in the suite |
|---|---|
| Startup | Valid order reaches `READY`; report records each component |
| Startup failure | Parametrized failure at every boundary; rollback reverses the acquired subset |
| Cleanup | Normal shutdown releases C, B, A |
| Cleanup failure | One failing release does not prevent the others; status is partial/failed |
| Cancellation | Startup cancellation rolls back; shutdown cancellation continues cleanup then propagates |
| Background tasks | Completion, failure, cancellation, timeout, duplicate rejection, leak visibility |
| Leaked-task policy | A task that ignores cancellation skips resource release, reports the leak and fails shutdown |
| Health | Readiness is 200 only in `READY`; `lifecycle_not_ready` otherwise |
| Concurrency | Concurrent starts: one wins; concurrent shutdowns: one cleanup |
| Isolation | Two `create_app()` instances have independent state and lifecycle |
| Telemetry | Providers shut down; instruments reset; optional degradation |
| Integration | Real ASGI lifespan, startup failure propagation, repeated lifespans |
| Regression | Metrics reset, import-time inertness, cleanup idempotency |

## 3. Lifecycle invariants

The tests assert:

- A failed startup never reaches `READY`.
- Every acquired resource receives exactly one release attempt per lifecycle
  execution.
- Release order is the reverse of acquisition order.
- A release failure does not prevent unrelated releases.
- The original startup exception survives cleanup failure.
- A stopped lifecycle cannot release resources twice.
- `CancelledError` is recorded as cancellation, never as a generic defect.
- No owned task remains after a cooperative shutdown.
- A second application instance cannot observe another instance's state.
- Importing modules or calling `create_app()` starts nothing.

## 4. Adversarial / property testing

Hypothesis generates:

- the failure boundary across a three-component startup;
- which releases fail;
- whether shutdown is repeated;
- sequences of `start` and `shutdown` operations.

The property tests assert the same invariants for every generated case. They are
not a substitute for the explicit scenarios; they catch orderings a human did not
enumerate.

## 5. Failure injection style

Failures are ordinary callables and real asyncio primitives:

- async initializers that raise;
- release callables that raise, sleep or block;
- `asyncio.Event` gates for cancellation windows;
- a supervisor task that ignores the first cancellation to exercise timeout and
  leak reporting.

No test mocks the lifecycle manager itself, so rollback and cleanup ordering are
real.

## 6. Running the checks

```bash
# Lifecycle behaviour
uv run pytest tests/lifecycle -v -m lifecycle

# Structural ownership check
uv run pytest tests/lifecycle -v -m architecture

# Full gate (includes 100% coverage and Semgrep)
make check
```

Semgrep rules reject qualified `asyncio.create_task`/`ensure_future`, direct
imports, aliases and wildcard imports outside
`src/waxprep/lifecycle/background.py`. The AST check covers the same forms and
also rejects `transition_to()` calls outside the lifecycle owner modules.
Adversarial tests prove each form is detected while a local function with the
same name is not falsely flagged.

The observability timeout is tested independently from the component timeout:
one test uses a long telemetry flush with a tiny component timeout, and another
proves a tight observability timeout is enforced.

## 7. What 100% coverage does not prove

Coverage proves every line executed at least once under the suite. Correctness
comes from the invariants above, failure injection and adversarial sequences.
A green coverage number with no cancellation or rollback tests would not satisfy
Stage 16.

## 8. Future additions

When a real component is added, add at least:

- one success path;
- one mandatory failure path that proves rollback;
- one cleanup failure path;
- one cancellation/timeout path if it does asynchronous work;
- one leak assertion if it owns tasks or handles.
