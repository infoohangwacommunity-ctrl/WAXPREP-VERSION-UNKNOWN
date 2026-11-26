# WaxPrep Configuration Reference — Stage 11

## Overview

WaxPrep uses a single validated configuration model defined in `src/waxprep/config.py`.
All operational values are configured through `WAXPREP_` environment variables.
The same application binary runs in every environment; the hosting environment supplies
the appropriate values.

Configuration sources (in precedence order):

1. Explicit runtime or test overrides (where intentionally supported)
2. Operating-system environment variables
3. Local `.env` file
4. Validated development defaults

The application must not start with invalid configuration. Invalid configuration
produces a clear validation error without exposing secrets.

## Supported Settings

| Name | Environment Variable | Data Type | Default | Required in Production | Sensitive | Allowed Values / Validation | Purpose |
|------|---------------------|-----------|---------|----------------------|-----------|----------------------------|---------|
| Environment | `WAXPREP_ENVIRONMENT` | `Environment` enum | `development` | Yes — must be explicitly set | No | `development`, `test`, `staging`, `production` | Identifies the active deployment environment |
| Host | `WAXPREP_HOST` | `str` | `0.0.0.0` | Recommended | No | Non-empty string | Network interface to bind the ASGI server to |
| Port | `WAXPREP_PORT` | `int` | `8000` | Recommended | No | Integer 1–65535 | TCP port the ASGI server listens on |
| Log Level | `WAXPREP_LOG_LEVEL` | `LogLevel` enum | `INFO` | Recommended | No | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Structured logging verbosity (case-insensitive) |

## Validation Rules

- **Environment**: Must be one of the four recognised values. Invalid values (including
  misspellings like `producon`) are rejected at startup with a `ValidationError`.
- **Host**: Must be a non-empty string. Whitespace-only values are rejected.
- **Port**: Must be an integer between 1 and 65535 inclusive. Zero, negative, floating-point,
  and non-numeric values are rejected.
- **Log Level**: Must be one of the five recognised levels. Values are normalised to uppercase,
  so `info` and `INFO` behave identically. Invalid values are rejected.
- **Defaults**: The development defaults themselves pass validation. The application cannot
  start with invalid defaults.
- **Production**: When `WAXPREP_ENVIRONMENT=production`, the deployment must explicitly
  supply the value. A production instance must not accidentally identify itself as `development`.

## Configuration Source Precedence

1. **Explicit runtime/test overrides** — tests may set environment variables via monkeypatch.
   The running application receives values from the OS environment or `.env` file.
2. **OS environment variables** — `WAXPREP_*` variables set in the shell or container
   environment take precedence over the `.env` file.
3. **`.env` file** — A `.env` file in the working directory is loaded automatically by
   Pydantic Settings. This is for local development and controlled testing only.
4. **Validated defaults** — When no override is supplied, development defaults are used.

OS environment variables always win over `.env` file values.

## Unknown Variable Detection

Pydantic Settings ignores unknown OS environment variables by default. This means a typo
such as `WAXPREP_PORRT=8000` would silently fall back to the default port without warning.

WaxPrep addresses this with an explicit check that inspects the process environment for
unsupported `WAXPREP_` variables at import time. Known misspellings are mapped to their
correct names and produce actionable warnings.

Known misspellings detected:

| Misspelled Variable | Correct Variable |
|---------------------|------------------|
| `WAXPREP_PORRT` | `WAXPREP_PORT` |
| `WAXPREP_ENVIRONMET` | `WAXPREP_ENVIRONMENT` |
| `WAXPREP_LOG_LEVEl` | `WAXPREP_LOG_LEVEL` |
| `WAXPREP_HOSTT` | `WAXPREP_HOST` |

Warnings are written to stderr with the prefix `WAXPREP_CONFIG_WARNING`. They do not
prevent the application from starting; they alert the operator to a likely mistake.

Unrelated environment variables (e.g. `PATH`, `HOME`) are never flagged.

## Production Configuration Policy

Production deployments must:

- Explicitly set `WAXPREP_ENVIRONMENT=production`.
- Supply valid values for host, port, and log level.
- Never rely on development defaults for operational parameters.

Production secrets (API keys, database credentials, messaging credentials) are **not**
part of the current configuration model. They will be introduced alongside their
corresponding integrations in later stages.

## Error Handling

| Situation | Outcome |
|-----------|---------|
| Valid configuration supplied | Application starts normally |
| Invalid environment name | `ValidationError` at startup; application does not start |
| Invalid log level | `ValidationError` at startup; application does not start |
| Port out of range | `ValidationError` at startup; application does not start |
| Non-integer port | `ValidationError` at startup; application does not start |
| Empty host | `ValidationError` at startup; application does not start |
| Misspelled `WAXPREP_` variable | Warning printed to stderr; application continues with default |
| Unknown `WAXPREP_` variable | Warning printed to stderr; application continues with default |

Validation errors do not expose secret values. Error messages reference the field name
and the validation rule that was violated.

## Files

- `src/waxprep/config.py` — Settings model, validation, unknown-variable detection
- `.env.example` — Safe example with non-secret development defaults
- `.env` — Local overrides (excluded from Git via `.gitignore`)
- `tests/configuration/test_config.py` — Comprehensive configuration tests

## Quick Reference

```bash
# Development defaults (no environment variables needed)
uv run uvicorn waxprep.main:get_app --host 0.0.0.0 --port 8000

# Override via environment
WAXPREP_ENVIRONMENT=staging WAXPREP_PORT=9000 \
  uv run uvicorn waxprep.main:get_app --host 0.0.0.0 --port 9000

# With .env file (copy .env.example to .env and edit)
cp .env.example .env
uv run uvicorn waxprep.main:get_app
```
