# Environment Setup Guide — Stage 11

## Overview

WaxPrep runs in four environments using the same application binary.
The hosting environment supplies the appropriate configuration values;
no code changes are needed between environments.

| Environment | Purpose | Configuration Source | Typical Values |
|-------------|---------|---------------------|----------------|
| Development | Local development and experimentation | `.env` file + defaults | `WAXPREP_ENVIRONMENT=development`, port 8000 |
| Testing | Automated test runs | Isolated monkeypatch env (not real env) | Controlled test values per test |
| Staging | Pre-production validation | OS environment (container/CI) | Staging host, port, log level |
| Production | Live deployment | OS environment (hosting platform) | Explicitly supplied production values |

## What Comes from Code Defaults

These values are provided as development conveniences and are validated:

- `WAXPREP_ENVIRONMENT` — defaults to `development`
- `WAXPREP_HOST` — defaults to `0.0.0.0`
- `WAXPREP_PORT` — defaults to `8000`
- `WAXPREP_LOG_LEVEL` — defaults to `INFO`

These defaults are intentionally permissive for local development. They pass validation.
If no environment variables are set and no `.env` file exists, WaxPrep starts with these values.

## What Must Be Supplied by the Deployment

Production deployments must explicitly supply:

- `WAXPREP_ENVIRONMENT=production` — identifies the active environment
- Valid `WAXPREP_HOST` — the network interface to bind to
- Valid `WAXPREP_PORT` — the TCP port to listen on
- A `WAXPREP_LOG_LEVEL` appropriate for production

These values must not be left at development defaults in production.

## Local Development

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` if you need different values.
3. Start the application:
   ```bash
   uv run uvicorn waxprep.main:get_app --reload
   ```

The `.env` file is loaded automatically from the working directory.
OS environment variables override `.env` values if both are present.

The real `.env` file is excluded from Git. Only `.env.example` is tracked.

## Testing

Tests must not rely on the developer's real environment or `.env` file.
The `tests/configuration/` suite uses the `isolated_env` fixture to strip
all `WAXPREP_*` variables before each test, then sets specific values via
`monkeypatch.setenv()`.

Do not rely on the host machine's environment variables to make tests pass.
Always set the values a test needs explicitly.

## Staging

Staging deployments supply values via the hosting environment (CI variables,
container environment, or deployment tool).

Example staging configuration:
```bash
WAXPREP_ENVIRONMENT=staging
WAXPREP_HOST=0.0.0.0
WAXPREP_PORT=8000
WAXPREP_LOG_LEVEL=INFO
```

## Production

Production deployments must explicitly identify themselves:

```bash
WAXPREP_ENVIRONMENT=production
WAXPREP_HOST=127.0.0.1
WAXPREP_PORT=8000
WAXPREP_LOG_LEVEL=WARNING
```

Production secrets (API keys, database credentials, messaging credentials)
are not part of the current configuration model. They will be introduced
alongside their corresponding integrations in later stages.

## Configuration Precedence

1. OS environment variables (`WAXPREP_*`)
2. `.env` file (working directory)
3. Validated defaults

OS environment variables always override `.env` values.

## Verifying Configuration

After startup, the readiness endpoint confirms configuration is loaded:

```bash
curl http://127.0.0.1:8000/health/readiness
```

Invalid configuration prevents startup entirely. The application logs a validation
error and exits without exposing secret values.
