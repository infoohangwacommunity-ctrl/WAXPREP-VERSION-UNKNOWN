# Operations Runbook

**Audience:** whoever is on call. Assumes no deep knowledge of the codebase.
**Companion documents:** `OBSERVABILITY_AND_LOGGING.md`, `SECURITY_AND_SECRETS.md`, `ERROR_HANDLING.md`.

---

## 1. First five minutes

1. `GET /health/liveness` → expect `200 {"status":"alive"}`.
   Failing means the process is dead or wedged. Check the platform's restart
   history, then the last log lines before exit.
2. `GET /health/readiness` → expect `200 {"status":"ready"}`.
   `503` returns a `reason`: `configuration_not_loaded`,
   `registries_not_initialized`, `channel_registry_not_initialized`,
   `model_registry_not_initialized`, `tool_registry_not_initialized`.
3. Check CPU/memory in the dashboard for a spike or a leak-shaped ramp.
4. Open logs and look for `"level":"error"`.

## 2. Triage by error category

The response body is generic by design; the **category is in the logs**. Search
by the `request_id` returned in the `X-Request-ID` header.

| `error.category` | Meaning | Action |
|---|---|---|
| `validation` | Caller sent bad input | Not an outage. Fix the caller; the response explains what was wrong. |
| `not_found` / `conflict` | Bad path or state | Not an outage. |
| `rate_limited` | Too many requests | Confirm the caller backs off. Bounded retry is safe. |
| `dependency_unavailable` | Upstream down | Check the upstream. Retry is safe and bounded. |
| `dependency_timeout` | Upstream too slow | Check upstream latency. Retry is safe and bounded. |
| `provider_rejected` | Upstream refused the request | Usually credentials, quota, or an invalid request. **Do not retry blind.** |
| `authentication` / `authorization` | Credential or permission problem | Check rotation and scope. Never retry blindly. |
| `configuration` | Bad or missing setting | Fix the value and redeploy. Startup will refuse to run. |
| `internal_invariant` / `programming_defect` | Bug | Escalate. Capture `request_id`, `trace_id`, and the log event. |
| `cancellation` | Deliberate shutdown | Expected during deploys. **Not** an error and must not be retried. |

## 3. Common scenarios

### The service will not start
Startup validates configuration and **refuses to run on invalid input**. The error
names the offending variable but never prints its value.

- `Production requires explicitly supplied configuration for: …` → set those
  `WAXPREP_*` variables in the platform, not relying on dev defaults.
- `Production startup blocked due to critical configuration misspellings: …` →
  a typo like `WAXPREP_PORRT`. Fix the name and restart.
- `telemetry_enabled is true but telemetry_endpoint is empty` → set the endpoint
  or disable telemetry.

### Requests are slow
Read p95 in the dashboard, then find the slow operation in traces by `trace_id`.
If telemetry is off, re-enable it to get traces — logs alone will not show where
time went.

### Error rate spiked
Filter logs to `"level":"error"` and group by `error.category`. A single category
climbing points at one dependency or one bad deploy; a spread across categories
points at infrastructure.

### Logs look truncated or an exporter is failing
Telemetry export problems are logged but never break requests. Confirm whether it
is the collector or the network; observability degrades independently of
availability.

### A credential may have leaked
Follow `SECURITY_AND_SECRETS.md` §7. **Revoke first, investigate second.**

## 4. Deploy and rollback

1. Merge to `main` only with green CI (see `CI_ACCEPTANCE_POLICY.md`).
2. Set required configuration in the platform **before** the deploy.
3. Watch readiness for 2 minutes after rollout.
4. Roll back by redeploying the previous good revision — configuration changes
   are separate from code and may need their own rollback.

**Never** "roll back" by re-enabling a revoked credential.

## 5. What not to do

- Do not restart repeatedly to "clear" an error — read the category first.
- Do not add `continue-on-error` or `except: pass` to make a red gate green.
- Do not retry `validation`, `authentication`, `authorization`,
  `provider_rejected` or `programming_defect`.
- Do not paste log lines containing credentials into a ticket. Redaction covers
  the application's own output; a shell echo is not redacted.
- Do not judge health from CPU graphs alone; a process can be idle and broken.
