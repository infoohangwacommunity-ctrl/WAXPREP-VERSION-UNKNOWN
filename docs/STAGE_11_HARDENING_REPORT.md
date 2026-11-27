# Stage 11 — Hardening Pass Report

This report records the independent review follow-up on the Stage 11 Application
Configuration System. It is a correction and hardening pass; the architecture
introduced in `da255a5` and corrected in `4763d76` is preserved.

## Scope

Reviewed and hardened:

- `src/waxprep/config.py`
- `src/waxprep/main.py`
- `tests/configuration/test_config.py`
- `tests/integration/test_startup_config.py` (new)
- `tests/integration/test_main.py`
- `pyproject.toml`
- `README.md`
- `docs/CONFIGURATION_REFERENCE.md`
- `docs/ENVIRONMENT_SETUP.md`

## Preserved design (unchanged)

1. Pydantic Settings as the single configuration system.
2. `Environment` and `LogLevel` enums.
3. Host, port and log-level validation.
4. The `WAXPREP_` environment-variable convention.
5. OS environment precedence over `.env`.
6. Validated development defaults.
7. Production explicit-setting validation.
8. Unknown-variable detection with value-safe warnings.
9. Configuration source diagnostics.
10. `.env.example` and Git exclusion of the real `.env`.
11. Configuration reference and environment setup documentation.

## Corrections

### 1. Configuration loading consistency

`load_settings()` accepted an `env_file` argument but constructed `Settings()`
without it, so the file inspected could differ from the file loaded. It now:

- Loads `Settings(_env_file=selected_file)` — the exact file selected.
- Uses the same file for production-intent detection.
- Uses the same file for unknown-variable inspection.
- Reports diagnostics from the file actually loaded.
- Keeps `env_file=None` as an explicitly disabled dotenv source.

### 2. Test isolation

Configuration tests previously removed `WAXPREP_*` OS variables but could still
read a developer's `.env`. The configuration suite now uses an autouse fixture
that strips `WAXPREP_*` variables and changes the working directory to an empty
temporary directory. Tests that need dotenv values pass an explicit temporary
file; tests that expect defaults pass `_env_file=None`. The shared
`Settings.model_config` is no longer mutated.

### 3. Startup integration

`main.py` now exposes a canonical `run()` entrypoint (also the `waxprep`
console script) that passes the validated `settings.host` and `settings.port`
to Uvicorn with the ASGI app object. `WAXPREP_HOST` and `WAXPREP_PORT` therefore
control the real listening address. Direct `uvicorn` CLI use is documented as a
debugging/reload path that must pass host and port explicitly.

### 4. Dotenv parsing

The hand-written line parser was replaced with `python-dotenv` so the detector
and Pydantic interpret the same syntax: `export`, quotes, comments, whitespace,
duplicate keys, escapes and malformed entries. Unreadable files are treated as
empty.

### 5. Production typo detection

Production intent is detected from the effective environment value. When the
correctly spelled `WAXPREP_ENVIRONMENT` is absent, a misspelled
`WAXPREP_ENVIRONMET=production` is still treated as production intent, so a
deployment cannot silently downgrade to development. Critical misspellings
(`PORRT`, `HOSTT`, `LOG_LEVEl`, `ENVIRONMET`) block startup in production with
value-free errors.

### 6. Documentation

README, `pyproject.toml`, `docs/CONFIGURATION_REFERENCE.md` and
`docs/ENVIRONMENT_SETUP.md` now describe Stage 11, the canonical startup method,
and the isolation strategy accurately.

## New and updated tests

- Custom `env_file` is the file actually loaded (multiple files, cwd isolation).
- Disabled dotenv source stays disabled.
- Production requirements are enforced from the selected file.
- python-dotenv parity: `export`, quotes, inline comments, duplicates, escapes,
  malformed entries, unreadable files.
- Adversarial production typos: misspelled environment alone, misspelled
  environment in `.env`, misspelled host, correct-over-typo precedence,
  OS-over-dotenv precedence, invalid production values, value-free errors.
- A deliberate conflicting local `.env` cannot leak into isolated defaults.
- `run()` passes validated host/port and the app object to Uvicorn.
- Real subprocess startup on a configured port; liveness and readiness succeed.
- Real subprocess refusal for invalid configuration and incomplete production
  configuration.

## Local quality gate

`make check` (ruff lint, ruff format check, mypy strict, import-linter, semgrep,
lockfile check, supply-chain gate, CI workflow audit, full suite, 100% coverage)
passes locally on Python 3.14.10 with `uv`.

## Remote CI acceptance

The previously corrected commit `4763d762bfbf65f9d20730f049230b00c192a341`
was verified against GitHub Actions:

- Quality Gate run `45890903165` — all 16 jobs succeeded.
- `Tests — configuration` collected and passed 61 tests (no deselection).
- `Coverage Gate — Full Suite (100%)` passed.
- `CI Acceptance — Independent Evidence Verification` decision: `ACCEPTED`
  for the assessed commit.
- Dependency Security run `45890903261` succeeded.

Acceptance for this hardening commit is provided by the Quality Gate workflow
run for that commit; the acceptance decision is recorded in the workflow
artifacts and is not asserted ahead of the remote run.
