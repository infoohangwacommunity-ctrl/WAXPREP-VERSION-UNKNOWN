# Stage 16 Implementation Report — Application Lifecycle Management

**Base:** `f2aded6` (main).
**Scope:** Startup, initialization order, resource ownership, rollback, shutdown,
cancellation, background-task foundation, telemetry lifecycle, lifecycle-aware
health, timeouts, observability, static enforcement and documentation.
**Public HTTP contract:** unchanged.

---

## 1. Existing functionality preserved

- FastAPI + async lifespan remains the integration point; no deprecated startup
  or shutdown events were introduced.
- Registries are still initialized explicitly with `register_defaults()`; no
  import-time registration was added.
- Telemetry remains optional, vendor-neutral and fail-open. The real OTLP
  traces/metrics pipelines and request spans from the correction pass remain.
- The public error contract and readiness/liveness paths are unchanged for a
  healthy application.
- The existing quality gate (ruff, format, mypy, import-linter, Semgrep,
  detector, supply chain, CI audit, 100% coverage) is preserved and extended.

## 2. Problems discovered

1. `AppState` documentation claimed per-instance ownership, but a module-level
   `_app_state` singleton was the actual source of readiness truth.
2. `lifespan()` had no general rollback: a failure before `yield` left earlier
   resources initialized.
3. Cleanup errors could overwrite the startup failure; there was no aggregate
   cleanup report or partial/failed classification.
4. `Metrics` kept instrument references after telemetry shutdown.
5. Readiness used registry booleans rather than one authoritative lifecycle state.
6. There was no owned background-task boundary and no structural check against
   unmanaged task creation.
7. Timeouts were not centrally defined for lifecycle work.
8. The old lifecycle tests asserted a docstring that mentioned signal handling
   and idempotency, but did not test rollback, cancellation, ordering or
   isolation.

## 3. Architectural decisions and reasons

| Decision | Reason |
|---|---|
| One `LifecycleStateMachine` with an explicit transition table | Removes ambiguous boolean combinations; invalid transitions fail before side effects |
| `AsyncExitStack` for release | Correct LIFO unwinding with incrementally acquired resources; no custom resource manager |
| Components declare `mandatory`, `depends_on`, `initialize`, `release` | Explicit ownership and dependency order without a DI framework |
| Registration order must satisfy declared dependencies | A simple, auditable composition root; no forward references or plugin scheduler |
| Optional components degrade rather than abort | Telemetry must never block a functional app |
| Cleanup wrappers catch ordinary exceptions and timeouts, record them, and continue | Failure isolation and a complete cleanup evidence trail |
| Cancellation is recorded and re-raised after cleanup | Cleanup still runs; structured concurrency is not broken |
| Telemetry cleanup runs after application resources | Exporters remain available while handlers/resources shut down; Phase D separation |
| Telemetry/metrics remain process-wide; app state is per-instance | OpenTelemetry providers are process-wide by design; only app-owned resources belong to `app.state` |
| Explicit re-entry from `STOPPED`/`FAILED` | The test suite and embedding reuse application objects; resources are fully re-acquired and re-released |
| Background task ownership via one supervisor | Prevents uncontrolled tasks; `TaskGroup` reserved for tightly coupled work |
| Structural AST + Semgrep checks | More reliable than keyword search; adversarial test proves the check fires |

## 4. Answers to the required questions

1. **Is module-level `_app_state` compatible with instance isolation?** It was
   not. Request handling now reads `app.state.app_state`; `_app_state` remains
   only as a refreshed compatibility alias to the default instance.
2. **Should lifecycle state move to `app.state`?** Yes. `app.state` holds
   `app_state`, `lifecycle` and `supervisor`; `create_app()` creates independent
   sets.
3. **Should `AsyncExitStack` be the cleanup mechanism?** Yes, wrapped with named
   release callbacks, per-release timeouts, outcome recording and cancellation
   handling.
4. **How is rollback guaranteed before `yield`?** Every successful initialization
   pushes a release callback; any failure/cancellation runs the stack before the
   original exception is re-raised.
5. **How is the original exception preserved?** Cleanup failures are recorded,
   never raised from the release wrapper; `start()` re-raises the captured
   original object.
6. **How are optional and mandatory failures distinguished?** `mandatory`
   defaults to true; optional failures are recorded in `degraded` and startup
   continues.
7. **How do telemetry's process-wide providers interact with app state?** The app
   owns the lifecycle *decision*; the providers are process-wide. Each execution
   configures new providers and shuts them down through the final observability
   callback.
8. **How is the global metrics object reset?** `Metrics.reset()` restores the
   no-op instruments and inactive flag. It runs before telemetry initialization
   and after telemetry shutdown.
9. **Is the application instance restartable?** Yes, explicitly: a new execution
   is allowed from `STOPPED` and `FAILED`. A lifecycle execution is single-use;
   cleanup is never repeated for the same execution.
10. **How are duplicate initialization/cleanup prevented?** A lifecycle lock
    serializes start/shutdown; state transitions reject invalid repeats; a
    `_cleanup_started`/`_cleanup_completed` guard makes shutdown idempotent.
11. **How are background tasks owned?** `BackgroundTaskSupervisor` names, tracks,
    cancels, awaits and reports every task; a structural test and Semgrep rule
    block other creation sites.
12. **Which future tasks use `TaskGroup`?** Tightly coupled work that must fail
    together, inside one supervised task. Independent services use one supervised
    task each. No scheduler is built.
13. **How does readiness represent `DRAINING`/`FAILED`?** It returns 503
    `lifecycle_not_ready`; only `READY` can return 200.
14. **What happens if cancellation occurs during acquisition?** The acquisition is
    recorded as cancelled, prior resources are released in reverse order, state
    becomes `FAILED`, and `CancelledError` propagates.
15. **How are leaks verified?** Tests assert the supervisor has no active tasks,
    metrics are inactive after shutdown, registries are cleared and cleanup
    counts are exact.
16. **How is behaviour tested without mocks?** Real manager, real asyncio, real
    `AsyncExitStack`, real ASGI lifespan and ordinary failure callables.
17. **Which invariants are statically enforced?** No task creation outside the
    supervisor (AST + Semgrep). Lifecycle state mutation is encapsulated in the
    manager/state machine; the architecture tests keep package boundaries intact.
18. **Can this respect existing boundaries?** Yes. The lifecycle package imports
    the typed error taxonomy and standard library/asyncio only; import-linter
    passes.

## 5. Changed files

**Added — source**
```
src/waxprep/lifecycle/__init__.py
src/waxprep/lifecycle/background.py
src/waxprep/lifecycle/components.py
src/waxprep/lifecycle/errors.py
src/waxprep/lifecycle/manager.py
src/waxprep/lifecycle/report.py
src/waxprep/lifecycle/states.py
src/waxprep/lifecycle/timeouts.py
```

**Modified — source**
```
src/waxprep/main.py                    per-app state, component composition, readiness, factory
src/waxprep/observability/metrics.py   Metrics.reset()
```

**Added — tests**
```
tests/lifecycle/test_lifecycle_static.py
```
`tests/lifecycle/test_lifecycle.py` was replaced with the Stage 16 suite.

**Modified — tests/config**
```
tests/conftest.py                      fresh default app + observability reset per test
tests/integration/test_exception_handlers.py  no overlapping second lifespan
tests/observability/test_telemetry.py  explicit metrics reset test
```

**Added — docs**
```
docs/APPLICATION_LIFECYCLE.md
docs/LIFECYCLE_OPERATIONS.md
docs/LIFECYCLE_TESTING.md
docs/STAGE_16_IMPLEMENTATION_REPORT.md
```

**Modified — docs/config**
```
README.md, docs/ENGINEERING-STANDARDS.md, docs/ARCHITECTURE_BOUNDARIES.md,
docs/PR_REVIEW_CHECKLIST.md, tests/README.md, .semgrep/config.yml,
pyproject.toml (description only)
```

## 6. Tests added

- Full state-transition matrix (allowed and rejected) and timeout validation.
- Component ownership validation (empty/duplicate/self dependencies).
- Report classifications: success/partial/failed/interrupted.
- Background supervisor: completion, failure, cancellation, timeout, duplicate,
  late start, reset, idempotent stop, error-reporter failure, leak visibility.
- Startup success, optional degradation, rollback at every boundary, retry,
  restart, timeout at component and total levels.
- Cleanup failure isolation, partial/failed status, original exception preserved,
  observability-last ordering.
- Cancellation during startup, cleanup and background stop.
- Concurrency: concurrent start, concurrent shutdown, shutdown waiting for start.
- Registration contract and invalid shutdown state.
- ASGI integration: per-instance state, two-app isolation, repeated lifespan,
  startup failure propagation, readiness lifecycle gating.
- Hypothesis rollback and operation-sequence invariants.
- Structural task-ownership and state-mutation ownership checks, each with an adversarial synthetic violation.

## 7. Local results

| Gate | Result |
|---|---|
| `ruff check src/ tests/` | PASS |
| `ruff format --check src/ tests/` | PASS |
| `mypy src/` (strict) | PASS |
| `import-linter lint` | PASS |
| Semgrep (8 rules, including lifecycle task ownership) | 0 findings |
| Hardcoding detector | 0 blocking |
| Supply-chain gate | PASSED |
| Workflow audit | PASSED |
| `uv lock --check` | PASS |
| `pytest` | **1011 passed, 1 skipped, 9 xfailed** |
| Coverage | **100.00%** (4,000 statements, 0 missed) |


## 8. Remaining limitations and deferred work

- Real database, Redis, messaging, tutor, context, notebook, judge and model
  provider lifecycles are deferred until those components exist.
- No background production service is started yet; the supervisor and its tests
  are the foundation.
- Telemetry providers are process-wide; multiple app instances in one process
  share them. This is intentional and documented, not an isolation bug.
- Lifecycle timeouts are code-level policy (`LifecycleTimeouts`), not environment
  settings yet. Centralizing them in configuration is deferred until operators
  need per-environment tuning.
- Drain of in-flight HTTP requests remains the ASGI server's responsibility.
- The static task check rejects direct `create_task`/`ensure_future`; a future
  library that hides task creation behind another API would need a matching rule.

## 9. Independent review notes

The implementation was reviewed against the actual source and the full local
gate; the acceptance rule remains: green tests are evidence of behaviour, not a
substitute for the remote GitHub Actions run. The final report intentionally does
not claim that future component lifecycles exist.

## 10. CI evidence

**Correction commit:** `ae5df06` (`main`, "feat(lifecycle): implement Stage 16 application lifecycle management").

| Workflow | Result | Run |
|---|---|---|
| CI — Quality Gate | success | https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/actions/runs/46079501263 |
| Dependency Security | success | https://github.com/infoohangwacommunity-ctrl/WAXPREP-VERSION-UNKNOWN/actions/runs/46079501350 |

The acceptance rule is unchanged: only evidence bound to the exact commit
counts. Local green results and this report are supporting evidence, not a
substitute for the runs above.


## 11. Correction pass (post-review)

The independent review accepted the architecture and required three focused
corrections. None changed the state model or resource-ownership design.

### 11.1 Observability timeout is now wired

`ApplicationLifecycle` previously routed telemetry cleanup through
`_release_named()` with `component_seconds`. The observability cleanup now passes
`timeout_seconds=self._timeouts.observability_seconds`, so the dedicated setting
is enforced independently.

Tests:

- a telemetry flush longer than `component_seconds` but shorter than
  `observability_seconds` completes;
- a telemetry flush longer than a tight `observability_seconds` is recorded as
  `timed_out` and fails shutdown.

### 11.2 Leaked background task policy

`BackgroundTaskSupervisor.stop()` already reported `timed_out` tasks. The
manager now treats a non-cooperative task as a failed, unsafe shutdown:

- `LifecycleReport.leaked_tasks` records the names;
- `cleanup_skipped` is set;
- application resources and observability cleanup are **not** released, because
  a live task may still be using them (use-after-close avoidance);
- final state is `FAILED`, `cleanup_status` is `failed`, `successful` is false;
- repeated shutdown returns the same report without releasing anything;
- the process supervisor must terminate the worker, which is the final resource
  reclamation boundary.

The adversarial test uses a real task that ignores cancellation, asserts that
the resource release was skipped and the leak remained visible, then releases the
task and proves the supervisor returns to zero active tasks.

### 11.3 Static detection covers imports and aliases

The AST checker now tracks `from asyncio import create_task`,
`from asyncio import ensure_future as spawn`, `from asyncio.tasks import ...` and
wildcard imports, in addition to qualified attribute calls. Adversarial tests
prove every form is detected while a local function with the same name is not
falsely flagged. Semgrep has matching rules for qualified calls, direct imports,
aliases and wildcard imports outside the supervisor.

### 11.4 Correction files

```
src/waxprep/lifecycle/manager.py       observability timeout + leaked-task policy
src/waxprep/lifecycle/report.py        leaked_tasks, cleanup_skipped, status
tests/lifecycle/test_lifecycle.py      timeout, leaked-task and report tests
tests/lifecycle/test_lifecycle_static.py  import/alias adversarial checks
.semgrep/config.yml                    direct/aliased/wildcard task rules
docs/APPLICATION_LIFECYCLE.md          policy and timeout documentation
docs/LIFECYCLE_OPERATIONS.md           shutdown/leak runbook
docs/LIFECYCLE_TESTING.md              correction test strategy
docs/STAGE_16_IMPLEMENTATION_REPORT.md this report
```

### 11.5 Correction results

Local suite: **1025 passed, 1 skipped, 9 xfailed**, **100% coverage (4,000
statements)**. Full `make check` passes (ruff, format, mypy, import-linter,
Semgrep with the expanded rules, detector, supply chain, workflow audit,
lockfile, tests, coverage).

Commit-bound CI evidence is recorded below after the correction commit.
