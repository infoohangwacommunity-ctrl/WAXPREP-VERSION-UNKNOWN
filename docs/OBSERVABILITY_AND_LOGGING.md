# Observability and Logging (Stages 13–14)

**Owner:** Log schema and severity policy, log correlation, telemetry configuration, metric catalogue, cardinality, exporter failure policy, dashboards.
**Does not cover:** Secret rotation (see `SECURITY_AND_SECRETS.md`) or error taxonomy (see `ERROR_HANDLING.md`).

---

## 1. Three signals, three jobs

| Signal | Answers | Cost control |
|---|---|---|
| **Logs** | What happened in this one event? | Redaction + fixed schema; no raw bodies |
| **Metrics** | What is the trend/count/rate? | Bounded labels only |
| **Traces** | Where did this one request spend time? | Sampling |

They share correlation IDs but never duplicate unlimited data.

## 2. Logging (Stage 13)

Configured once, explicitly, from validated settings — never as an import side
effect, so CLI entry points, tests and future workers share one contract.
`configure_logging()` is idempotent: repeated app-factory calls reconfigure in
place instead of stacking handlers (which would duplicate every event).

Location: `src/waxprep/observability/logging.py`.

### Event schema

```jsonc
{
  "timestamp": "2026-11-27T18:40:56.880600Z",   // UTC, ISO-8601
  "level": "info",
  "event": "startup_complete",                    // stable name, not a sentence
  "service.name": "waxprep",
  "service.version": "0.1.0",
  "deployment.environment": "production",
  "request_id": "3f2504e0-...",                   // when bound
  "trace_id": "…", "span_id": "…",                // only with an active span
  "error.code": "WAX-1005",                       // bounded, when applicable
  "error.category": "not_found"
}
```

Field names follow OpenTelemetry semantic conventions where one exists. Fields
are added only when meaningful — no null padding on every line.

### Severity policy

| Level | Use |
|---|---|
| `DEBUG` | Detailed local diagnostics. Off in production. |
| `INFO` | Lifecycle and meaningful operational events. |
| `WARNING` | Recoverable/unexpected conditions, degraded dependency, retries, rejected input. |
| `ERROR` | An operation failed and needs investigation; the process continues. |
| `CRITICAL` | The process cannot continue, or a security/invariant condition needs immediate attention. |

The layer that owns the final handling decision emits the authoritative failure
event. Lower layers do not re-log the same stack trace.

### Correlation

- `RequestIdMiddleware` validates inbound `X-Request-ID` as a UUID; invalid or
  absent IDs are replaced with a generated one. A spatial request ID is a
  **correlation value only** — never an identity or auth token.
- The effective ID is always returned in `X-Request-ID`.
- Context is bound for the request and explicitly cleared afterwards; a finished
  request cannot leak its ID into the next one (asserted by tests).
- `trace_id`/`span_id` are added by the observability middleware when a span is
  active. **Request ID ≠ trace ID ≠ span ID ≠ error code** — they are distinct and
  never overwrite each other.

### Redaction

A redaction processor sits in the structlog chain, so a secret is scrubbed
**before** it is rendered or exported. There is no second unredacted path. See
`SECURITY_AND_SECRETS.md` §3 for the layers.

Never logged: API keys, bearer tokens, passwords, cookies, private keys,
credential-bearing URLs, authorization headers, full environment dumps, request/
response bodies by default, student messages/prompts/model output, or unbounded
exception messages.

### Console vs container

JSON to stdout is the baseline; the platform collects it. Do not write rotating
log files inside ephemeral containers. `WAXPREP_LOG_JSON=false` gives readable
output for local development only — same schema, same redaction, one contract.

## 3. Telemetry (Stage 14)

**Portable pipeline:** application → OpenTelemetry SDK → OTLP/HTTP exporter →
chosen backend. The application is vendor-neutral; the backend is a deployment
choice. No backend SDK is imported by application code.

OpenTelemetry is an **optional extra**, not a base dependency:

```bash
uv sync --extra telemetry     # or pip install 'waxprep[telemetry]'
```

Absent SDK/exporter → a documented no-op with a logged reason
(`sdk_unavailable` / `exporter_unavailable`). Telemetry is **never** a startup
dependency.

### Configuration

| Setting | Default | Notes |
|---|---|---|
| `WAXPREP_TELEMETRY_ENABLED` | `false` | Master switch |
| `WAXPREP_TELEMETRY_ENDPOINT` | — | OTLP/HTTP endpoint. **Required when enabled** |
| `WAXPREP_TELEMETRY_SAMPLE_RATIO` | `1.0` | 0.0–1.0 |
| `WAXPREP_TELEMETRY_AUTH_TOKEN` | — | `SecretStr`; never logged |

Validation is split deliberately:

- **Enabled + no endpoint** → `ValueError` at startup. This is a configuration
  mistake, and silently running without telemetry would hide it.
- **Enabled + SDK missing** → degrade to `sdk_unavailable`. This is a deployment
  packaging state, not a code defect, so it must not block boot.

### Failure policy

Telemetry must never break a request. Export is batched and non-blocking; the
queue and export timeout are bounded; shutdown flushes with a bounded wait;
exporter errors are logged and swallowed. A collector outage degrades
observability, never availability. Metrics recording is wrapped so a metrics
backend failure cannot surface as a 500.

### Metric catalogue

Initial set covers the four golden signals for operations that **actually exist**:

| Metric | Type | Labels |
|---|---|---|
| `http.server.request.count` | counter | `http.request.method`, `http.route`, `http.response.status_class` |
| `http.server.request.duration` | histogram (ms) | same |
| `waxprep.error.count` | counter | `error.category`, `error.code` |
| `waxprep.readiness.count` | counter | `outcome` |

Service identity (`service.name`, `service.version`, `deployment.environment`) is
set as **resource** attributes, not per-request labels.

### Cardinality rules

- `http.route` uses the **matched route template** (`/students/{student_id}`),
  read from the Starlette scope — never the raw path. A raw identifier must never
  become a label; unmatched paths collapse to `unmatched`.
- Methods collapse to a fixed set; unknown → `OTHER`.
- Status collapses to a class (`2xx`…`5xx`); nonsense codes → `5xx`.
- Never used as labels: user IDs, phone numbers, request IDs, conversation IDs,
  exception messages, full URLs, prompt text, model output.

### Sampling

Start parent-based with a configurable ratio. Do not sample away all errors; if
volume grows, evaluate tail-based sampling at the collector rather than
in-process complexity.

**Deferred with evidence:** spans for messaging, context retrieval, tutor
orchestration, model providers, persistence and outbound delivery. Those
components do not exist. Trigger: the first real component is built — instrument
it at that point using the same boundary.

## 4. Dashboard and alerts (specification, not a build)

Panels: is it up · request rate · p50/p95/p99 latency · error rate · errors by
bounded category · CPU/memory vs limit · export failures · readiness failures ·
slowest operations (from traces).

Alert only on actionable symptoms: sustained 5xx rate, sustained p95 breach,
repeated readiness failure, memory near a known limit, repeated restarts,
persistent export failure. **Do not choose production thresholds before baseline
data exists** — record a baseline first, then document provisional thresholds.

## 5. Cost and retention

Decide and record: signals exported, sampling policy, log/trace/metric retention,
max attribute size, debug logs off in production, student content categorically
excluded, dashboard access control, credential rotation, and deletion/
retention-shortening procedure. Never use observability as a second copy of the
conversation database.

## 6. Operating procedure (non-specialist)

1. Open the hosting dashboard → confirm the deployment is healthy.
2. Check CPU and memory graphs.
3. Open application logs.
4. **Search the `request_id`** from the failed request (it is in the response
   header).
5. Read the structured error event: `error.code` + `error.category`.
6. If a trace backend is connected, follow `trace_id`.
7. Classify: transient (retryable category), configuration, or code defect.
8. Follow `OPERATIONS_RUNBOOK.md`.

## 7. Verification

`tests/observability/test_logging.py` (16) proves: valid JSON, required fields,
UTC timestamps, severity mapping and filtering, console fallback, no duplicate
events on repeated configure, log redaction (field, embedded, nested, traceback),
request-ID binding and clearing.

`tests/observability/test_telemetry.py` (52) proves: bounded label normalisers,
config validation, disabled-by-default inertness, graceful degradation when the
SDK/exporter is missing, shutdown swallowing exporter errors, real exporter path
offline, no-op span behaviour, and that `/items/SECRET-IDENTIFIER-42` labels as
`/items/{item_id}` — never the identifier.
