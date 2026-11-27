# Stage 12–15 Correction Report

**Scope:** Required completion pass for the independent review of the merged
Stages 12–15 implementation.
**Base commit:** `8eaa251` (`main`, "docs(report): drop dashboard and alert deferrals").
**Runtime:** Python 3.14.10, `uv sync --extra dev --frozen`.
**Public HTTP error contract:** unchanged.

This was a wiring and correctness pass, not an architecture rewrite. Every
finding below was reproduced against the merged source, corrected, and covered
by a test that observes the final output rather than a helper call.

---

## 1. Findings and resolutions

| # | Finding | Severity | Resolution |
|---|---|---|---|
| 1 | Instruments were created against the global meter provider without an exporting `MeterProvider`; metrics could silently be no-ops. | Critical | `Telemetry.configure()` now builds `MeterProvider` + `PeriodicExportingMetricReader` + `OTLPMetricExporter`, registers it globally, stores it on `TelemetryState`, and shuts it down. `Metrics.configure(meter_provider=...)` binds instruments to that provider. |
| 2 | A tracer provider existed but no production request span was created. | Critical | `ObservabilityMiddleware` opens exactly one `http.server.request` span per request and attaches bounded attributes. FastAPI's native telemetry is explicitly disabled to avoid a duplicate span/metric stream. |
| 3 | `record_error()` / `record_readiness()` had no production call sites. | Critical | Typed errors record one bounded error metric (cancellation excluded); unexpected exceptions record one `programming_defect` metric; readiness records one ready/not-ready outcome. Emission is fail-open. |
| 4 | Exception handlers logged `request.url.path`, which can embed identifiers. | High (privacy) | HTTP, validation, typed-error and general handlers now log the matched route template (or fixed `unmatched`). A sentinel-in-URL regression test asserts the identifier never appears in log output. |
| 5 | The retry budget was checked only before sleeping; a hanging operation could exceed the deadline. | High | A monotonic deadline now bounds each operation via `asyncio.wait_for`, as well as delays and subsequent attempts. An over-budget operation raises `DependencyTimeoutError`; external cancellation still propagates untouched. |
| 6 | `WAXPREP_TELEMETRY_AUTH_TOKEN` was not passed to the exporter. | High | The `SecretStr` value is revealed at one call site and sent as `Authorization: Bearer <token>` on both OTLP exporters. It is excluded from `repr()` and never logged. A non-empty token is now documented as active, not reserved. |
| 7 | Dependency Review failed with HTTP 403 because it lacked PR read permission. | CI | `.github/workflows/dependency-review.yml` adds least-privilege `pull-requests: read` alongside `contents: read`; a regression test locks the permission set. |
| 8 | Dependabot could not resolve the dependency set for Python 3.15. | CI | `requires-python` is now `>=3.14,<3.15`; `uv.lock` was regenerated for the supported range. |

The optional-telemetry and fail-open policies are preserved: a missing metrics
SDK or failing metrics exporter degrades metrics only (`metrics_reason`) while
traces continue, and exporter problems never change an HTTP response.

---

## 2. What changed

### Source

- `src/waxprep/observability/telemetry.py`
  - `TelemetryConfig.metrics_endpoint`, `resolved_metrics_endpoint()`,
    `exporter_headers()` (token excluded from `repr`).
  - Real `MeterProvider` + periodic OTLP reader; independent metrics degradation
    reasons; both providers shut down.
  - `span()` uses the provider owned by `TelemetryState`, not the one-shot global.
- `src/waxprep/observability/metrics.py`
  - `configure(meter_provider=...)`; instruments attach to the exporting provider.
- `src/waxprep/middleware/observability.py`
  - One request span; bounded `method`/`route`/`status_class` attributes;
    span and metric failures are swallowed.
- `src/waxprep/main.py`
  - FastAPI native telemetry disabled to prevent duplicate instrumentation.
  - Metrics pipeline wired from settings (metrics endpoint + auth token).
  - Error metrics in the typed and catch-all handlers; readiness metrics at the
    probe; single bounded readiness-reason variable.
  - Log-safe route labels replace raw paths.
- `src/waxprep/errors/retry.py`
  - Monotonic deadline enforced around each operation and each delay.
- `src/waxprep/config.py`
  - `WAXPREP_TELEMETRY_METRICS_ENDPOINT` setting.

### CI and packaging

- `.github/workflows/dependency-review.yml` — `pull-requests: read`.
- `pyproject.toml` — `requires-python = ">=3.14,<3.15"`; description updated to
  Stages 01–15.
- `uv.lock` — regenerated for the supported Python range.

### Documentation

`OBSERVABILITY_AND_LOGGING.md`, `CONFIGURATION_REFERENCE.md`,
`SECURITY_AND_SECRETS.md`, `OPERATIONS_RUNBOOK.md`, `ERROR_HANDLING.md`,
`CI_SECURITY.md`, `CONTRIBUTING.md`, `ARCHITECTURE_BOUNDARIES.md`, `README.md`,
`.env.example`, and `STAGE_12_15_IMPLEMENTATION_REPORT.md`.

---

## 3. Tests added

- **Real metric export:** `InMemoryMetricReader` receives request count/duration,
  error count and readiness measurements with bounded attributes.
- **Provider wiring:** configured meter provider receives both instruments; the
  `Bearer` header reaches both OTLP exporters and never appears in logs or
  `repr()`; trace/metric exporter failures degrade independently.
- **Request tracing:** a real HTTP request produces exactly one exported
  `http.server.request` span; its trace/span IDs match the structured log line;
  the request ID remains distinct; route is a template.
- **Metric call sites:** typed error, unexpected exception, readiness ready and
  not-ready each record exactly one metric; cancellation records none; a failing
  metrics backend never masks the response.
- **Log privacy:** a sentinel identifier in dynamic URL paths never appears in
  HTTP, validation, typed-error or unexpected-exception log output.
- **Retry deadline:** an operation longer than the budget is stopped; an
  overrunning delay re-raises the original failure; external cancellation
  propagates without retry.
- **Configuration:** metrics endpoint default/override and auth-token startup
  wiring.
- **CI:** Dependency Review permission set.

---

## 4. Local verification

| Gate | Command | Result |
|---|---|---|
| Lint | `uv run ruff check src/ tests/` | PASS |
| Format | `uv run ruff format --check src/ tests/` | PASS (100 files) |
| Types | `uv run mypy src/` (strict) | PASS (54 files) |
| Architecture | `uv run import-linter lint --no-logo` | PASS (4 contracts kept) |
| Security | `uv run semgrep --config .semgrep --error ...` | PASS (0 findings) |
| Hardcoding | `python -m waxprep.detector.cli` | PASS (0 blocking) |
| Supply chain | `python -m waxprep.supplychain.cli check` | PASSED (0 vulnerabilities) |
| Workflow audit | `python -m waxprep.ci.cli audit` | PASSED |
| Lockfile | `uv lock --check` | PASS |
| Tests | `uv run pytest` | **918 passed**, 1 skipped, 9 xfailed |
| Coverage | `pytest --cov-fail-under=100` | **100.00%** (3,480 statements, 0 missed) |
| Vulture | advisory | clean |
| Pyright | advisory | pre-existing unknown-type findings only; no new category introduced |

Baseline before the pass: 888 passed, 100% coverage. This pass adds 30 tests.

---

## 5. GitHub Actions evidence

The acceptance rule is the same: acceptance is decided from CI evidence bound to
the exact commit. After this report's commit is pushed to `main`, the full
`CI — Quality Gate` run, the `Dependency Security` run and a re-run of
`Dependency Review` on a pull request are the remote evidence. Run links are
recorded in the repository's **Actions** tab for the correction commit.

Local green results are not a substitute for that remote evidence.

---

## 6. Remaining explicitly deferred capabilities

- **Dashboards and alert rules** — still a specification, not a build. Signals
  now export, but no monitoring backend, dashboard or alert rule is provisioned.
- **Messaging/model/persistence spans and retries** — those components do not
  exist yet; instrument them when built.
- **RFC 9457 Problem Details** — deferred until a public API contract exists.
- **Dedicated secret manager / encryption infrastructure** — not required at the
  current scale; revisit with the first real multi-service credential or
  encrypted data use case.

None of these are claimed as implemented.
