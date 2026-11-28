# Background Execution (Stage 19)

**Owner:** job registration and dispatch, application-facing submission,
Taskiq adapter, broker selection, worker consumption, middleware extension and
worker lifecycle.
**Does not cover:** product jobs, scheduling, dashboards, cost control, workflow
orchestration, or a custom queue/broker/retry engine.

---

## 1. Boundary

| Responsibility | Owner |
|---|---|
| Application lifecycle | Stage 16 |
| In-process task supervision | Stage 16 |
| Dependency construction | Stage 18 |
| Communication envelopes | Stage 17 |
| Error taxonomy | Stage 15 |
| Logging/telemetry | Stages 13–14 |
| Job submission | Stage 19 `BackgroundRuntime` |
| Handler registration/dispatch | Stage 19 `JobRegistry` |
| Transport/consumption mechanics | Taskiq + selected broker |
| Worker entrypoint/lifecycle | Stage 19 `waxprep.worker` |

The background package does not import composition or `main.py`. The outer
worker entrypoint combines composition and background.

## 2. Handler registration (open world)

A component implements `JobContributor`:

```python
class MyJobs:
    def register_jobs(self, registry: JobRegistry) -> None:
        registry.register(
            JobHandler(
                task_name="waxprep.mycomponent.handle",
                payload_type=MyPayload,
                handler=self.handle,
            )
        )
```

`CompositionRoot(job_contributors=(MyJobs(),))` applies contributors to the app
and worker job registries. There is no fixed business-job catalogue and no
filesystem/plugin discovery. A worker refuses to start with an empty registry;
the product stage that owns a handler must supply a contributor through the
composition/bootstrap path.

Handlers are async, accept one `MessageEnvelope[PayloadT]`, and return an
`OperationResult`. Known WaxPrep errors become failure results; unexpected
exceptions propagate so the framework middleware/policy can classify/retry them.
Cancellation propagates.

## 3. Submission and envelope

`BackgroundRuntime.submit(MessageEnvelope)` serializes a validated Stage 17
envelope, submits it through the selected broker, and returns the framework job
id. The envelope's `message_type` is the stable task identity; correlation and
causation IDs are preserved in logs.

No live object, connection, request, container, secret or pickle is transmitted.

## 4. Broker selection and in-memory policy

- `InMemoryBroker` is **development/test-only**. It executes in the submitting
  process and is not distributed. The worker refuses to consume with it.
- In `development`/`test`, composition may default to the in-memory adapter for
  local tests.
- In `staging`/`production`, composition returns `UnavailableBackgroundRuntime`
  unless an explicit `background_factory` (or composition override) supplies a
  real broker-backed runtime. Submission then fails closed with
  `BackgroundUnavailableError`; the HTTP app still starts.
- `background_factory(registry, worker_process)` is the production extension
  point. Supply Taskiq Redis/RabbitMQ/NATS or another selected broker there.
- No broker package is committed as a base dependency. Taskiq is an optional
  `waxprep[background]` extra.

## 5. Worker consumption and lifecycle

`waxprep.worker.BackgroundWorker` uses the Stage 18 composition root and Stage 16
lifecycle:

1. `configuration` component loads/logs validated settings.
2. `composition` builds a worker-specific `WorkerDependencies` bundle
   (`settings`, `JobRegistry`, worker runtime, lifecycle, supervisor).
3. `background` component starts the broker/runtime.
4. `BackgroundWorker.run` checks that the registry is non-empty, then calls
   `runtime.consume(stop_event)`.
5. `TaskiqBackgroundRuntime.consume` runs Taskiq's `Receiver` with
   `run_startup=False`. Taskiq owns message consumption/dispatch; the dynamic
   dispatcher and handlers are already registered on that broker.
6. On stop, the receiver stops accepting messages and waits for active work.
7. Stage 16 then releases the background component (broker shutdown), composition
   and configuration in reverse order.

The worker never imports FastAPI. The HTTP app starts without a worker. No second
lifecycle manager or DI container exists.

## 6. Middleware / execution policy

`CompositionRoot(background_middlewares=(...))` passes Taskiq middleware into the
runtime. Retry/backoff/filtering is Taskiq's responsibility; WaxPrep does not
hardcode exception lists or build another retry engine. A test demonstrates
`SmartRetryMiddleware` retrying a failing handler through the composition path.

## 7. Observability

Submission/start/completion/failure events use the existing structured logger
with task identity, job/message ID, correlation ID, outcome and duration. No new
telemetry stack or dashboard is introduced.

## 8. Testing and limitations

The test suite covers registration, duplicate/missing handlers, envelope and
payload validation, typed failures, cancellation, submission, middleware, retry,
worker startup/shutdown, empty-registry refusal, FastAPI isolation and a real
producer/independent-worker exchange over a test-only ZeroMQ broker (separate
processes; `pyzmq` is a dev dependency). The default in-memory broker is not
durable and does not prove distributed delivery.

Duplicate delivery is expected in practical queues: handlers must be idempotent
where external effects matter. WaxPrep does not claim exactly-once execution.

Broker disconnection, durable redelivery, scheduling, dashboards, cost controls,
workflow orchestration and product jobs are deferred.
