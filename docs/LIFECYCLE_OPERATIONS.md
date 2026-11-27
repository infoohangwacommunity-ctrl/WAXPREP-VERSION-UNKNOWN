# Lifecycle Operations (Stage 16)

Operational behaviour for startup failure, cancellation, shutdown and diagnosis.
Companion documents: `APPLICATION_LIFECYCLE.md`, `OPERATIONS_RUNBOOK.md`.

---

## 1. Startup

1. The ASGI server opens the lifespan.
2. `ApplicationLifecycle.start()` transitions `NEW -> STARTING`.
3. Components initialize in order: configuration → registries → telemetry.
4. Successful mandatory initialization transitions to `READY`.
5. Readiness returns 200 only in `READY`.

If startup fails, the process should be restarted after correcting the cause.
The server receives the original exception; partial resources are already
released.

### Startup failure diagnosis

Search structured logs for:

- `lifecycle_startup_failed` — includes `error_type` and state.
- `lifecycle_component_failed` — includes component name, outcome and whether it
  was mandatory.
- `lifecycle_rollback_started` / `lifecycle_rollback_completed` — confirms
  reverse-order cleanup ran.
- `lifecycle_cleanup_failed` — a release also failed; the original startup
  exception is still the one propagated.
- `lifecycle_component_degraded` — an optional component failed; the app may
  still be `READY`.

A failed startup never reports readiness. Check `LifecycleReport` in tests or the
`startup_error_type` field in diagnostics.

## 2. Readiness semantics

| State | Readiness |
|---|---|
| `NEW`, `STARTING`, `DRAINING`, `STOPPING`, `STOPPED`, `FAILED` | 503 `lifecycle_not_ready` |
| `READY` + registries healthy | 200 `ready` |
| `READY` + registry/config problem | 503 with the specific bounded reason |

Optional degradation (for example, telemetry exporter unavailable) does not
change readiness. Mandatory failure does.

## 3. Shutdown

On lifespan shutdown:

1. The lifespan sets `shutting_down` and calls `ApplicationLifecycle.shutdown()`.
2. `READY -> DRAINING`; readiness is false.
3. Owned background tasks are cancelled and awaited within
   `background_stop_seconds`.
4. `DRAINING -> STOPPING`; resources release in reverse acquisition order.
5. Telemetry flushes and exporters shut down using the dedicated
   `observability_seconds` timeout; metrics instruments are reset.
6. Final state is `STOPPED` (clean) or `FAILED` (cleanup failure/interruption).
7. `app_state` references are cleared.

If a supervised task ignores cancellation and is reported `timed_out`, the
manager records it in `leaked_tasks`, sets `cleanup_skipped`, marks shutdown
`FAILED`, and does **not** release application resources or observability. This
avoids closing resources a live task may still use. The worker process must be
terminated by its supervisor; that is the final resource-reclamation boundary.

Repeated shutdown is safe and idempotent; resources are not released twice.

## 4. Cancellation

- Cancellation during startup rolls back acquired resources and re-raises
  `CancelledError`.
- Cancellation during shutdown records the interrupted release, continues
  releasing remaining resources, then re-raises `CancelledError`.
- A cancellation is not a readiness failure signal by itself; the process is
  terminating.
- Do not swallow cancellation to make a deploy finish. Let the server's
  lifecycle complete.

## 5. Background tasks

No production background services exist yet. When one is added:

- start it through `BackgroundTaskSupervisor`;
- give it a unique name;
- make cancellation cooperative;
- do not create sibling tasks directly;
- record failures through the supervisor's error callback or logs;
- verify `active_tasks` is empty after shutdown.

A task that ignores cancellation appears as `timed_out` and remains in
`active_tasks`; that is a leak signal, not a silent success. Resource cleanup is
skipped for that shutdown (see the policy above), the final state is `FAILED`,
and the process supervisor must terminate the worker.

## 6. Timeout tuning

Defaults are defined in `LifecycleTimeouts`. To change a deadline, change the
single source and document why; do not scatter literals. Keep component timeout
smaller than the startup budget, and ensure the telemetry timeout is compatible
with the collector's latency.

## 7. Restart policy

An application instance supports an explicit new lifecycle execution after
`STOPPED` or `FAILED`. The test suite exercises repeated lifespans. Production
restarts should still create a fresh process; re-entry exists for embedding and
tests, not as a substitute for process supervision.

## 8. Common scenarios

| Symptom | Likely cause | Action |
|---|---|---|
| Pod never ready, logs show `lifecycle_component_failed` with `mandatory=true` | Mandatory init failure | Fix component/config; restart |
| Ready is 503 `lifecycle_not_ready` | Lifespan not started, draining or failed | Inspect lifecycle logs/state |
| Ready 503 `registries_not_initialized` | Registry component did not complete | Check startup logs; restart |
| Shutdown hangs | A release ignores cancellation or exceeds timeout | Inspect `lifecycle_cleanup_failed`/`timed_out`; fix component |
| Shutdown reports leaked tasks | A background task ignored cancellation | Inspect `lifecycle_background_tasks_leaked`; fix the task's cancellation handling; terminate/restart the worker |
| Telemetry missing but app ready | Optional telemetry degraded | Check `telemetry_configured` and `metrics_reason` |
| Cleanup failure after a startup failure | One release failed | Original startup exception is still the cause; fix release separately |

## 9. Log event reference

`lifecycle_starting`, `lifecycle_component_ready`,
`lifecycle_component_failed`, `lifecycle_component_degraded`,
`lifecycle_component_cancelled`, `lifecycle_ready`, `lifecycle_draining`,
`lifecycle_cleanup_started`, `lifecycle_resource_released`,
`lifecycle_cleanup_failed`, `lifecycle_cleanup_cancelled`,
`lifecycle_cleanup_completed`, `lifecycle_cleanup_interrupted`,
`lifecycle_stopped`, `lifecycle_startup_failed`, `lifecycle_rollback_started`,
`lifecycle_rollback_completed`, `background_task_failed`,
`background_tasks_stopped`.

Fields are bounded names, outcomes and error types. Secrets and student content
are never logged.
