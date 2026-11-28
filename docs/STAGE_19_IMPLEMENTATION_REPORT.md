# Stage 19 Implementation Report — Background Execution

**Base:** `8cfe193` (main).
**Scope:** open-world job registration/submission, Taskiq integration, broker
selection, independent worker consumption, middleware and lifecycle integration.
**Not implemented:** product jobs, scheduler, custom queue/broker, retry engine,
dashboard, cost control, workflow engine.

---

## 1. Implemented

- `JobRegistry`/`JobHandler`: typed, open-world task registration and dispatch by
  `MessageEnvelope.message_type`, with duplicate/missing-handler and signature
  validation.
- `BackgroundRuntime` submission boundary; fail-open unavailable implementation.
- `TaskiqBackgroundRuntime`: generic dispatcher, envelope serialization, optional
  middleware, broker start/stop, real Taskiq `Receiver` consumption for workers.
- `JobContributor` and `CompositionRoot(job_contributors=...)`: components
  register handlers in both app and worker registries; no fixed job catalogue.
- `WorkerDependencies` and `waxprep.worker`: independent worker entrypoint using
  Stage 18 composition and Stage 16 lifecycle, no FastAPI.
- Broker policy: in-memory only in development/test; staging/production require
  an explicit `background_factory`/override or degrade to unavailable.
- Middleware path: `background_middlewares` reaches the runtime; Taskiq
  `SmartRetryMiddleware` is demonstrated.
- Errors reuse Stage 15; cancellation and unexpected exceptions propagate for
  framework policy; known WaxPrep errors become safe `OperationResult` failures.
- Boundaries: import-linter, AST and Semgrep checks for background/composition/
  worker isolation; tests for producer/independent-worker interoperability.

## 2. Corrections from the independent review

| Finding | Correction |
|---|---|
| Worker only started broker and waited | Worker now runs Taskiq `Receiver.consume` against the broker; stops accepting before broker/resource shutdown |
| InMemoryBroker automatic production default | InMemory restricted to development/test; staging/production return unavailable unless an explicit broker factory/override is supplied |
| Empty worker registry | `JobContributor` generic registration path; worker refuses to start with no registered handlers |
| No producer/worker interoperability test | Separate processes exchange a job through a test-only ZeroMQ broker; handler writes a marker |
| Middleware not configured | `background_middlewares` composition path; SmartRetryMiddleware retry test |
| Lifecycle ownership | Worker consumes, then Stage 16 stops broker/resources in reverse order; test covers start/stop |
| Failure tests | Handler failure propagation, typed failure result, cancellation, retry, empty registry, worker interruption/stop |
| Documentation | Architecture/worker/broker/registration docs and this report added; stage references corrected |

## 3. Files

Added:
```
src/waxprep/background/__init__.py
src/waxprep/background/errors.py
src/waxprep/background/registration.py
src/waxprep/background/registry.py
src/waxprep/background/runtime.py
src/waxprep/background/taskiq.py
src/waxprep/worker.py
tests/unit/test_background_registry.py
tests/integration/test_background_runtime.py
docs/BACKGROUND_EXECUTION.md
docs/STAGE_19_IMPLEMENTATION_REPORT.md
```
Modified: composition bundles/root/application/exports, pyproject/uv.lock,
import-linter, Semgrep, architecture/standards/checklist/tests docs, README.

## 4. Tests

- Registration/duplicate/missing handlers, typed/sync/signature validation.
- Envelope and payload validation; non-serializable/unknown fields; failure and
  cancellation handling.
- Taskiq submission, InMemory rejection for workers, receiver path, middleware.
- SmartRetryMiddleware retry through composition.
- Production/staging broker unavailability and explicit factory selection.
- JobContributor worker registry population and empty-registry refusal.
- Worker lifecycle start/stop; FastAPI isolation; runpy entrypoint.
- Separate-process producer/worker over ZeroMQ with a shared envelope contract.
- Existing architecture, composition, lifecycle, contract and security gates.

## 5. Local results

| Gate | Result |
|---|---|
| ruff/format | PASS |
| mypy strict | PASS (89 files) |
| import-linter | 8 contracts kept |
| contracts drift/compatibility | PASS |
| Semgrep | 0 findings |
| hardcoding detector | 0 blocking |
| supply chain | PASSED |
| workflow audit | PASSED |
| pytest | **1,404 passed**, 1 skipped, 9 xfailed |
| coverage | **100.00%** (5,481 statements) |

## 6. Limitations

- The default in-memory broker is local/test only and not durable.
- No production broker package is committed; supply Redis/RabbitMQ/NATS through
  `background_factory`/composition override.
- The independent-worker test uses ZeroMQ as a real transport but not a durable
  production broker; durable redelivery/disconnection are deferred.
- Duplicate delivery is expected; handlers must be idempotent where required. No
  exactly-once claim.
- No product job handlers exist; the worker refuses to start empty, so a future
  product stage must supply a `JobContributor`.
- No scheduler, dashboard, cost control, workflow engine, custom queue/broker or
  retry engine.

## 7. CI evidence

Recorded after the final push.
