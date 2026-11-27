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
| Host | `WAXPREP_HOST` | `str` | `0.0.0.0` | Yes — must be explicitly set | No | Non-empty string | Network interface to bind the ASGI server to |
| Port | `WAXPREP_PORT` | `int` | `8000` | Yes — must be explicitly set | No | Integer 1–65535 | TCP port the ASGI server listens on |
| Log Level | `WAXPREP_LOG_LEVEL` | `LogLevel` enum | `INFO` | Yes — must be explicitly set | No | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | Structured logging verbosity (case-insensitive) |

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
- **Production**: When `WAXPREP_ENVIRONMENT=production`, host, port, and log level must be
  supplied explicitly. Relying on development defaults in production is rejected.

## Configuration Source Precedence

1. **Explicit runtime/test overrides** — tests may set environment variables via monkeypatch.
   The running application receives values from the OS environment or `.env` file.
2. **OS environment variables** — `WAXPREP_*` variables set in the shell or container
   environment take precedence over the `.env` file.
3. **`.env` file** — A `.env` file in the working directory is loaded automatically by
   Pydantic Settings. This is for local development and controlled testing only.
4. **Validated defaults** — When no override is supplied, development defaults are used.

OS environment variables always win over `.env` file values.

Safe origin diagnostics are available via `Settings.configuration_sources()`, which reports
whether each field came from `environment`, `env_file`, or `default` without exposing values.

## Unknown Variable Detection

Pydantic Settings ignores unknown OS environment variables by default. This means a typo
such as `WAXPREP_PORRT=8000` would silently fall back to the default port without warning.

WaxPrep addresses this with an explicit check that inspects both the process environment and
the local `.env` file for unsupported `WAXPREP_` variables during `load_settings()`.
Known misspellings are mapped to their correct names and produce actionable warnings.

Known misspellings detected:

| Misspelled Variable | Correct Variable |
|---------------------|------------------|
| `WAXPREP_PORRT` | `WAXPREP_PORT` |
| `WAXPREP_ENVIRONMET` | `WAXPREP_ENVIRONMENT` |
| `WAXPREP_LOG_LEVEl` | `WAXPREP_LOG_LEVEL` |
| `WAXPREP_HOSTT` | `WAXPREP_HOST` |

Warnings are written to stderr with the prefix `WAXPREP_CONFIG_WARNING`. They include the
incorrect name, suggested correction, and source (`environment` or `env_file`). They never
include the variable's value.

Unrelated environment variables (e.g. `PATH`, `HOME`) are never flagged.

### Severity policy

- **Non-production**: unknown or misspelled `WAXPREP_` variables emit warnings; startup continues.
- **Production**: a known misspelling of a critical setting (`PORT`, `ENVIRONMENT`, `HOST`,
  `LOG_LEVEL`) blocks startup with a `ValueError` that names the misspelled variables only.

## Production Configuration Policy

Production deployments must:

- Explicitly set `WAXPREP_ENVIRONMENT=production`.
- Explicitly supply `WAXPREP_HOST`, `WAXPREP_PORT`, and `WAXPREP_LOG_LEVEL`.
- Never rely on development defaults for operational parameters.
- Correct any known critical misspellings before the process will start.

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
| Production missing explicit host/port/log level | `ValidationError` at startup; application does not start |
| Misspelled `WAXPREP_` variable (non-production) | Warning printed to stderr; application continues with default |
| Critical misspelling in production | `ValueError` at startup; application does not start |
| Unknown `WAXPREP_` variable | Warning printed to stderr; application continues with default |

Validation errors and warnings do not expose secret values. Messages reference the field or
variable name and the rule that was violated — never the configured value.

## Files

- `src/waxprep/config.py` — Settings model, validation, unknown-variable detection, source diagnostics
- `.env.example` — Safe example with non-secret development defaults
- `.env` — Local overrides (excluded from Git via `.gitignore`)
- `tests/configuration/test_config.py` — Comprehensive configuration tests

## Quick Reference

The canonical startup method is `python -m waxprep.main` (or the `waxprep`
console script). It applies the validated `WAXPREP_HOST` and `WAXPREP_PORT` to
the actual Uvicorn listener.

```bash
# Development defaults (no environment variables needed)
uv run python -m waxprep.main

# Override via environment — the server binds 0.0.0.0:9000
WAXPREP_ENVIRONMENT=staging WAXPREP_PORT=9000 \
  uv run python -m waxprep.main

# Production (all operational settings must be explicit)
WAXPREP_ENVIRONMENT=production \
WAXPREP_HOST=0.0.0.0 \
WAXPREP_PORT=8000 \
WAXPREP_LOG_LEVEL=info \
  uv run python -m waxprep.main

# With .env file (copy .env.example to .env and edit)
cp .env.example .env
uv run python -m waxprep.main
```

Invoking `uvicorn waxprep.main:get_app` directly is supported for debugging and
auto-reload, but Uvicorn's own `--host`/`--port` defaults apply unless you pass
them explicitly. Use the entrypoint above for deployments.
