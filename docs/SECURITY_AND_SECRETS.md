# Security and Secret Management (Stage 12)

**Owner:** Secret lifecycle, credential classification, redaction policy, incident response.
**Does not cover:** CI workflow implementation (see `CI_SECURITY.md`) or telemetry export (see `OBSERVABILITY_AND_LOGGING.md`).

---

## 1. Classification

WaxPrep separates three things that are often conflated:

| Class | Example | Handling |
|---|---|---|
| **Operational configuration** | `WAXPREP_HOST`, `WAXPREP_PORT`, `WAXPREP_LOG_LEVEL` | Ordinary settings. May appear in logs and docs. |
| **Secret** | API key, DB password, webhook signing secret, OTLP auth token | `SecretStr`-typed. Never logged, serialized, or committed. |
| **Secret metadata** | Name, purpose, owner, rotation interval | Safe to document. Never includes the value. |

Everything a secret needs is declared in `src/waxprep/config.py` using
`pydantic.SecretStr`. That type masks the value in `repr()`, `model_dump()`,
`model_dump_json()` and `str()`. The raw value is only reachable via an explicit
`.get_secret_value()` call at the single point of use.

## 2. Source precedence

Highest priority first:

1. **OS environment variables** — injected by the hosting platform's protected
   variable store. This is the production path.
2. **Mounted secret file** — where the platform supports it; treated identically
   to an environment variable.
3. **Local `.env` file** — development only. Listed in `.gitignore` and never
   committed.
4. **No production default** — a missing required credential fails startup
   rather than silently falling back to a placeholder.

There is deliberately **no secret in source, `pyproject.toml`, docs, committed
YAML/JSON, test snapshots, or issue text.** `.env.example` contains placeholders
only.

## 3. Where secrets must never appear

Redaction is defence-in-depth, not the primary control. Callers are expected not
to emit secrets at all; `src/waxprep/secrets/redaction.py` catches what slips
through before anything reaches an output sink.

Blocked sinks: application logs, trace attributes and span events, metric
labels, HTTP error responses, health/readiness payloads, CLI diagnostics,
exception messages surfaced publicly, and test snapshots.

### Redaction layers

1. **Key-name matching** — `password`, `api_key`, `x-api-key`, `client_secret`,
   `private_key`, `authorization`, `cookie`, `dsn`, `database_url`, …
   Separators are normalised, so `x-api-key`, `x_api_key` and `X Api Key` all
   match.
2. **Structural shapes inside strings** — `Bearer <token>`, `user:pass@` URL
   segments, `KEY=value` assignments, PEM blocks, and well-known provider token
   prefixes (GitHub, Slack, AWS, Google, Stripe, JWTs).
3. **Recursive container walking** with a depth and item budget, so a
   pathological payload cannot hang the process.

Replacement is by a single `[REDACTED]` marker — never a partial mask, because a
partial mask of a short secret still leaks most of it.

Deliberate non-goals: redaction is **not** a substitute for access control,
rotation, or incident response. It also does not redact every word containing
`key` or `token`, because over-redaction destroys the diagnostics operators need.

## 4. Secret inventory

No component currently requires a runtime credential, so no secret is active
today. This table is the authoritative register; add a row **before** wiring a
new credential.

| Name | Purpose | Owner | Environments | Status | Rotation | Revocation | Notes |
|---|---|---|---|---|---|---|---|
| `WAXPREP_TELEMETRY_AUTH_TOKEN` | OTLP exporter credential | Platform/SRE | staging, production (only if the collector requires auth) | **Active** — wired into both OTLP exporters as `Authorization: Bearer <token>` | Rotate with the collector's credential; prefer short-lived tokens | Remove from platform variable store, restart service, confirm exports fail closed | Optional. Absence is not an error; no header is sent. Value is never logged or serialized, including `repr()`. |
| *(future)* DB password | Persistence | — | — | Not implemented | — | — | Do not create until a database exists. |
| *(future)* channel webhook secret | Inbound verification | — | — | Not implemented | — | — | Do not create until a channel integration exists. |

**Rule:** do not list a hypothetical secret as active. Mark future candidates
explicitly as future.

## 5. Rotation and revocation

For any credential that supports rotation:

1. Issue the new credential at the provider (keep the old one valid).
2. Update the platform's protected variable store.
3. Deploy or restart so the process picks up the new value.
4. **Verify** the new credential works (successful export / successful call).
5. Revoke the old credential at the provider.
6. Record rotation metadata (date, operator, reason) — **never the value**.
7. Confirm the old credential now fails with a classified error.

**Rollback limit:** re-enabling a *compromised* credential is not an acceptable
rollback. Fix forward instead. A revoked credential must produce a classified
failure (`AuthenticationError`/`ProviderRejectedError`) and must **not** enter an
infinite retry loop — see `RetryPolicy`, which only retries `TRANSIENT`
categories.

## 6. Encryption keys

WaxPrep does not yet encrypt application data itself. **Do not** introduce
encryption infrastructure speculatively. When a real use case exists, require a
separate design covering key generation and entropy, algorithm and purpose, key
versioning, envelope encryption, rotation and re-encryption, backup/recovery, and
compromise response. Never reuse a general API key as an encryption key merely
because it is available.

## 7. Incident response — accidental exposure

1. **Revoke first, investigate second.** Revoke the credential at the provider.
2. Assume compromise; do not rely on deleting the commit alone.
3. Purge the value from logs/traces if the platform supports deletion, and
   shorten retention for affected windows.
4. Rotate every credential that could have been co-located.
5. Record a post-incident note: what leaked, blast radius, detection path,
   and the control that failed.
6. Add a regression test that would have caught it.

## 8. Verification

Covered by `tests/secrets/test_redaction.py` (31 cases) and
`tests/configuration/test_stage12_14_settings.py`, including:

- secrets masked in `repr()`, `model_dump()` and `model_dump_json()`
- sentinel values absent from startup logs and tracebacks
- bearer tokens, URL credentials, PEM blocks and provider tokens redacted
- unrelated safe values **not** destroyed
- depth/item budgets bound adversarial payloads

Public HTTP responses are asserted to contain no traceback, file path, exception
class, or exception message (see `tests/integration/test_stage12_15_integration.py`).
