# Error Handling and Exception Architecture (Stage 15)

**Owner:** Error taxonomy, propagation and ownership, public HTTP mapping, retry policy.
**Does not cover:** Logging implementation (see `OBSERVABILITY_AND_LOGGING.md`).

---

## 1. The five questions

Every failure must answer: **how is it classified, which layer owns it, should it
propagate/translate/retry, what is recorded internally, and what is exposed
externally.** If a failure cannot answer all five, it is not yet designed.

## 2. Taxonomy

Defined in `src/waxprep/errors/taxonomy.py`. Each type carries a stable `code`, a
bounded `category`, a `retryability`, and a `safe_message`.

| Category | Code | Retryable | Typical HTTP | Severity |
|---|---|---|---|---|
| `validation` | WAX-1001 | no | 422 | INFO/WARNING |
| `configuration` | WAX-1002 | no | 500 | ERROR/CRITICAL |
| `authentication` | WAX-1003 | no | 401 | WARNING |
| `authorization` | WAX-1004 | no | 403 | WARNING |
| `not_found` | WAX-1005 | no | 404 | INFO |
| `conflict` | WAX-1006 | no | 409 | WARNING |
| `dependency_unavailable` | WAX-2001 | **yes** | 503 | WARNING/ERROR |
| `dependency_timeout` | WAX-2002 | **yes** | 504 | WARNING/ERROR |
| `rate_limited` | WAX-2003 | **yes** | 429 | WARNING |
| `provider_rejected` | WAX-2004 | no | 502 | WARNING/ERROR |
| `internal_invariant` | WAX-3001 | no | 500 | ERROR/CRITICAL |
| `programming_defect` | WAX-3002 | no | 500 | ERROR |
| `cancellation` | WAX-3003 | **no** | 503 | (no error log) |
| `unknown` | — | no | 500 | ERROR |

`category` is bounded and therefore safe as a **metric label**. Exception
messages, user content and credentials are never categories.

`cancellation` is deliberately **not** retryable: retrying during shutdown
resurrects work the process is trying to stop.

## 3. Ownership by layer

| Layer | Responsibility |
|---|---|
| `core/` | Raises dependency-neutral meaning. Never imports FastAPI, Starlette or vendor SDKs. |
| `services/` | Coordinates, decides recovery, preserves causes. |
| `adapters/` | **Translates** vendor/library exceptions into WaxPrep categories. No vendor exception escapes upward. |
| HTTP boundary (`errors/http.py`) | Maps category → status, builds the sanitized body. No business logic. |
| Startup boundary | Invalid configuration fails fast with a value-free diagnostic. |
| Shutdown boundary | Handles cancellation without mislabelling it a fault. |

Dependency direction is enforced by `tests/architecture/test_boundaries.py` and
import-linter: `errors/` and `secrets/` are pure (standard library only), so they
cannot leak a vendor type into the domain.

## 4. Duplicate reporting

**Exactly one layer emits the authoritative failure event.** Lower layers add
context and raise a typed error (`raise X from cause`). They do not log and
re-raise. The HTTP handler is the single reporting point for request-path
failures; it logs once and records one bounded metric.

Anti-patterns that are explicitly rejected:

- `except Exception: pass`
- `return None` after a failed operation
- catching and logging at every layer (one stack trace becomes four)
- `raise NewError(...)` without `from cause`
- catching `CancelledError`/`KeyboardInterrupt`/`SystemExit` as normal failures
- returning a success-shaped value after failure

## 5. Public HTTP contract

Intentionally **unchanged** from the Stage 01–11 foundation, so existing clients
and tests keep working:

```jsonc
// 4xx — the safe message may be shown
{ "detail": "The requested resource was not found" }

// 5xx — always generic
{ "detail": "Internal server error", "message": "An unexpected error occurred" }
```

Rules:

- Server-side categories *always* return the generic pair, even if the exception
  carries a more specific message. `should_expose_message()` enforces this.
- Client-side categories may surface `safe_message` only.
- Every response carries `X-Request-ID`.
- Never returned: traceback, file path, exception class, database detail, secret,
  provider credential, internal configuration.

**RFC 9457 Problem Details:** evaluated and deliberately **deferred**. The current
shape is already established and locked by tests, and there is no external
consumer requiring Problem Details yet. Revisit when a public API contract is
published; migrate the handlers, tests and docs together, and do not support both
formats unpredictably.

## 6. Retry policy

`src/waxprep/errors/retry.py`. There is deliberately **no `@retry` decorator** —
retry is a decision about operation semantics, so each call site opts in
explicitly.

Requirements enforced by `RetryPolicy` and `run_with_retry`:

- Only `TRANSIENT` categories are retried. Invalid input, invalid credentials,
  permission denial and programming defects are never retried.
- Hard attempt ceiling **and** a total monotonic wall-clock budget. The budget
  covers the operation itself, every retry delay and every subsequent attempt:
  each operation runs under the remaining time, and an operation that outlives
  the deadline is cancelled and surfaced as `DependencyTimeoutError` rather than
  hanging past the promised budget.
- Exponential backoff with jitter (parallel callers do not synchronise).
- Cancellation always propagates; it is never converted into a retry or a
  timeout.
- The final failure is re-raised unchanged, so the owning boundary reports it.

Not yet applicable: no retryable operation exists in the current foundation
(registries are in-process; no outbound HTTP client is used in the request path).
The policy is implemented and tested so future adapters inherit correct
behaviour instead of inventing their own loops.

**Deferred with evidence:** channel delivery retries, model-provider retries,
queue redelivery and dead-letter handling require those components to exist.
Trigger for implementation: the first real outbound integration.

## 7. Health and readiness

- **Liveness** — is the process alive? Never depends on an optional third-party
  service, so an upstream outage cannot cause a restart loop.
- **Readiness** — is the app initialised enough to serve? Checks configuration
  and registries only. No fake database/provider probes have been added because
  those components do not exist.

Neither endpoint reveals secrets, connection strings, traces, or topology.

## 8. Verification

`tests/unit/test_error_taxonomy.py` (31 cases) and
`tests/integration/test_stage12_15_integration.py` prove: unique stable codes,
cause chaining, category→status mapping, generic 5xx bodies, no leakage of
tracebacks/class names/messages, request-ID preservation, permanent failures not
retried, attempt ceilings, budget exhaustion, and cancellation propagation.
