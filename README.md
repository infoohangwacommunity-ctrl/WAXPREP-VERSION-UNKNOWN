# WaxPrep Foundation

**IMPORTANT: This repository contains the WaxPrep engineering foundation (Stages 01 through 19).**

Stage 07 adds the consolidated CI quality gate (`.github/workflows/quality-gate.yml`) with blocking checks (ruff, ruff format, mypy, import-linter, semgrep, tests, 100% coverage gate, smoke test) and advisory checks (pyright, vulture). Stage 09 adds dependency and supply-chain security to the same gate: pip-audit without blanket ignores, a scoped expiring exception register, lockfile hashes, dependency source restrictions, license policy, OSV malicious-package intelligence, a CycloneDX SBOM and Dependabot proposals. Stage 10 turns that collection into an acceptance system: every job records machine-readable evidence, the workflow audits its own definition, and acceptance is decided only from evidence bound to the exact commit being assessed.

Stage 12–15 add the operational layer, implemented in dependency order (12 → 13 → 15 → 14) so error categories are stable before telemetry is built:

- **Stage 12 — Secrets:** `SecretStr` configuration, provider-neutral secret boundary, a metadata-only inventory, and defence-in-depth redaction covering key names, bearer tokens, URL credentials, PEM blocks and provider token shapes.
- **Stage 13 — Logging:** one logging contract (`configure_logging`) with a fixed UTC/JSON schema, documented severity policy, request/trace correlation and redaction applied *before* output.
- **Stage 15 — Errors:** a typed taxonomy with stable codes and bounded categories, category→HTTP mapping that preserves the existing public contract, single-owner reporting, and a bounded, jittered, cancellation-aware retry policy.
- **Stage 14 — Observability:** vendor-neutral OpenTelemetry behind an **optional extra**, a real OTLP metrics pipeline (meter provider + periodic reader) and one request span per HTTP request, low-cardinality labels using route *templates*, and a fail-open exporter policy so a collector outage never breaks a request.
- **Stage 16 — Application lifecycle:** one explicit state machine per application instance, dependency-ordered initialization, `AsyncExitStack` reverse-order rollback, failure-isolated cleanup that preserves the original exception, cancellation-aware shutdown, owned background-task supervision, lifecycle-aware readiness and centrally validated timeouts.
- **Stage 17 — Internal communication contracts:** strict immutable Pydantic DTOs, discriminated operation results, a versioned message envelope, bounded JSON validation/serialization, semantic contract identity and compatibility policy, deterministic JSON Schema publication with CI drift and baseline-compatibility enforcement, and contract failures integrated with the Stage 15 taxonomy.
- **Stage 18 — Dependency injection and composition:** one authoritative composition root, a typed dependency graph with missing/cycle/lifetime validation, typed application bundles, constructor/factory injection, explicit test overrides, registry implementation selection moved to composition, and integration with the Stage 16 lifecycle. No third-party container or global service locator.
- **Stage 19 — Background execution:** an open-world typed job registry, an application-facing submission boundary, Taskiq integration behind an optional extra (in-memory broker by default), reuse of Stage 17 envelopes and Stage 15 errors, a worker-specific composition bundle, and an independent worker entrypoint that uses the Stage 16 lifecycle without FastAPI. No product jobs, custom queue, scheduler, retry engine or broker.

**Stage 10 completion does not mean the WaxPrep AI tutoring product is complete.** This is still a foundation project. Real WhatsApp/Telegram handlers, database infrastructure, tutor logic, and the intelligence layer are not implemented.

## Stage 01: Programming Language
- Python 3.14 (`requires-python = ">=3.14,<3.15"`; 3.15+ is not supported until dependencies resolve and CI tests it)
- uv for dependency management
- Pydantic v2 for data validation
- Static type checking (mypy/pyright)

## Stage 02: Runtime and Execution Environment
- ASGI application (FastAPI + Uvicorn)
- Registry pattern with fake adapters (proves architecture)
- Explicit registry registration (no import-time side effects)
- Graceful shutdown (ASGI server-managed via lifespan; no custom signal handler)
- Application state owned per FastAPI instance (`app.state.app_state`); `create_app()` builds isolated instances (Stage 16)
- Health endpoints (liveness ≠ readiness, readiness checks registry state)
- Structured logging with correlation IDs (middleware-bound, context properly restored)
- Request ID validation (incoming IDs validated before trust)
- Global exception handling (no stack traces leaked; HTTP exceptions sanitized)

## Stage 03: Project Architecture and Structural Boundaries

- Package structure with explicit domain boundaries
- `core/` - Pure logic & protocols (no infrastructure imports)
- `messaging/` - Message handling & conversation flow (placeholder - no implementation)
- `context/` - Understanding the learner (placeholder - no implementation)
- `services/` - Light orchestration (placeholder - no implementation)
- Boundary rules documented and enforced via import-linter
- Dependency direction: Outer → Inner. Never the reverse.
- "Land not house" philosophy - architecture enables future builds without dictating them

### Package Structure (Stage 03)

```
src/waxprep/
├── main.py              # ASGI app, health endpoints, lifespan, middleware
├── config.py            # Settings (configurable defaults with development defaults; override via WAXPREP_ env vars)
├── id.py                # UUIDv7 identity generation (Stage 04 identity foundation)
├── core/                # Pure logic & protocols (NO infrastructure imports)
│   ├── __init__.py      # Boundary rules and purpose statement (no code)
│   ├── protocols.py     # Message / MessageHandler / ContextProvider protocols
│   └── pure.py          # Pure functions (normalize_text, extract_keywords, etc.)
├── messaging/           # Message handling & conversation flow (placeholder)
│   └── __init__.py      # Boundary rules, placeholder for future code
├── context/             # Understanding the learner (placeholder)
│   └── __init__.py      # Boundary rules, open land - internal shape TBD
├── services/            # Light orchestration (placeholder)
│   └── __init__.py      # Boundary rules, composition layer
├── middleware/          # Request ID and base middleware patterns
│   ├── __init__.py
│   ├── request_id.py    # Correlation ID middleware
│   └── base.py          # Middleware skeletons for future use
├── registries/          # Channel, Model, Tool registries
│   ├── __init__.py
│   ├── base.py          # BaseRegistry[T] - generic registry
│   ├── channel.py       # ChannelRegistry + ChannelAdapter protocol
│   ├── model.py         # ModelRegistry + ModelAdapter protocol
│   └── tool.py          # ToolRegistry + Tool protocol
├── contracts/           # Stage 17 typed communication contracts, schemas and validation
├── composition/         # Stage 18 composition root, dependency graph, bundles and lifetimes
├── background/          # Stage 19 job registry, runtime boundary and Taskiq adapter
├── worker.py            # Stage 19 independent worker entrypoint (no FastAPI)
├── detector/            # Stage 08 hardcoding detector (development-time only)
├── supplychain/         # Stage 09 dependency & supply-chain gate (development-time only)
├── ci/                  # Stage 10 CI evidence, acceptance and workflow audit (development-time only)
└── adapters/            # Fake adapter implementations (source of truth)
    ├── __init__.py
    ├── fake_channel.py  # FakeChannelAdapter
    ├── fake_model.py    # FakeModelAdapter
    └── fake_tool.py     # FakeTool
```

tests/
├── unit/               # Pure logic, single function/class
│   ├── __init__.py
│   ├── test_core_pure.py              # Pure function logic
│   ├── test_id.py                     # UUIDv7 correctness, monotonicity, mass uniqueness, format validation
│   └── test_middleware_skeletons.py   # Middleware skeleton validation
├── integration/       # Component interactions
│   ├── __init__.py
│   ├── test_exception_handler_pattern.py  # Exception handler pattern documentation
│   ├── test_exception_handlers.py     # Exception handler integration
│   ├── test_final_coverage.py         # Final coverage verification
│   ├── test_foundation.py             # Foundation stability + middleware + correlation IDs
│   ├── test_main.py                   # Health endpoints
│   └── test_registries.py            # Registry behavior
├── contract/          # Protocol compliance
│   ├── __init__.py
│   └── test_core_protocols.py         # Protocol compliance
├── lifecycle/         # Startup/shutdown, failures
│   ├── __init__.py
│   └── test_lifecycle.py              # Startup/shutdown, failure paths
├── architecture/      # Boundary enforcement
│   ├── __init__.py
│   └── test_boundaries.py             # Architectural boundary enforcement
├── configuration/     # Config loading
│   ├── __init__.py
│   └── test_config.py                 # Proves configurable defaults, not hardcoded values
├── detector/          # Stage 08 detector tests (not in the CI category matrix)
│   ├── test_detector.py               # Unit tests for each WHD rule
│   ├── test_adversarial.py            # Adversarial and mutation tests
│   ├── test_cli_and_quality_gate.py   # CLI and integration tests
│   ├── test_coverage_gaps.py          # Coverage gap analysis
│   └── test_property.py               # Property-based tests
├── supplychain/       # Stage 09 dependency and supply-chain tests
│   ├── conftest.py                    # Synthetic lockfile/policy fixtures
│   ├── test_policy.py                 # Exception, license and source policies
│   ├── test_lockfile.py               # uv.lock and requirement parsing
│   ├── test_scanners.py               # pip-audit, OSV and license adapters
│   ├── test_checks.py                 # Aggregate trust assessment
│   └── test_outputs.py                # SBOM, reports and CLI
├── regression/        # Behavior preservation + Stage 10 adversarial CI tests
│   ├── __init__.py
│   ├── test_ci_acceptance.py         # Acceptance rejects skipped/cancelled/missing/stale evidence
│   ├── test_ci_evidence.py           # Evidence records and required-report validation
│   ├── test_ci_cli.py                # record / accept / audit CLI and reporting
│   └── test_ci_workflows.py          # Workflow pinning, triggers, jobs, matrix, evidence audit
└── conftest.py                        # Shared fixtures




### Boundary Rules

**Dependency Direction: Outer → Inner (ONE WAY)**

```
Outer layers (infrastructure, orchestration) may import Inner layers.
Inner layers (core, protocols) MUST NOT import Outer layers.

messaging/ ──→ core/, registries/
context/   ──→ core/
services/  ──→ core/, messaging/, context/, registries/
main.py    ──→ config, registries, middleware, adapters
adapters/  ──→ registry protocols (NOT core/, NOT registries/)
registries/-→ base, typing (defines protocols; imports concrete fakes for defaults)
core/      ──→ Nothing from waxprep (pure logic only)

NEVER reverse this: core/ must not import from messaging/, services/, adapters/, or anywhere that contains infrastructure details.
```

Note: The registry layer contains protocols and imports concrete fake adapters for default registration. This is a deliberate design choice using structural typing (runtime_checkable Protocol). Adapters must NOT import from registries/ - they implement the protocols defined there.

### Package Naming Rules
- ❌ NO packages named after student types (e.g., "beginners", "advanced")
- ❌ NO packages named after academic levels (e.g., "high_school", "college")
- ❌ NO packages named after subjects (e.g., "math", "science")
- ❌ NO packages named after ability categories
- ✅ Packages named after ARCHITECTURAL ROLES (core, messaging, context, services)

### What Each Package May Import

| Package | May Import From | May NOT Import From |
|---------|-----------------|---------------------|
| `core/` | standard library only | adapters, channels, FastAPI, SDKs, any waxprep.* |
| `messaging/` | core/, registries/ | concrete adapters, direct SDKs, context/, services/ |
| `context/` | core/ | messaging/, services/, concrete adapters |
| `services/` | core/, messaging/, context/, registries/ | adapters directly (use registries) |
| `main.py` | FastAPI, config, registries, middleware, adapters | core/ (framework-agnostic) |
| `adapters/` | registry protocols (structural typing), SDKs | core/, registries/, other adapters, messaging/, context/, services/ |
| `registries/` | registries/base, typing | messaging/, context/, services/ |

Adapters depend on registry protocols via structural typing (duck typing). They do not import from the registries/ package.

### What is NOT included (later stages):
- ❌ NO WhatsApp handlers
- ❌ NO Telegram handlers  
- ❌ NO database schema
- ❌ NO docker-compose files
- ❌ NO PostgreSQL/Redis configuration
- ❌ NO tutor logic
- ❌ NO intelligence layer
- ❌ NO message router
- ❌ NO student context manager
- ❌ NO model orchestrator
- ❌ NO tool executor
- ❌ NO Prometheus/OpenTelemetry
- ❌ NO production deployment

## Stage 04: Identity Foundation (Wax ID)

- `src/waxprep/id.py` — UUIDv7 identity generation (`generate_id()`, `is_valid_id()`)
- Centralized, reusable identity capability for system entities and objects
- Uses standard UUID string format, no semantic prefixes
- Time-sortable (UUIDv7, RFC 9562), suitable for distributed systems
- Designed so future components can safely consume it
- `tests/unit/test_id.py` — UUIDv7 correctness, monotonicity, mass uniqueness, format validation

## Stage 05: Testing

Seven test categories with dedicated directories under `tests/`:

- **unit/** — pure logic, single function/class
- **integration/** — component interactions  
- **contract/** — protocol compliance
- **lifecycle/** — startup/shutdown, failures
- **architecture/** — boundary enforcement
- **configuration/** — config loading
- **regression/** — behavior preservation (directory present; no tests currently pinned)

```bash
uv run pytest tests/unit/ -v          # run unit tests
uv run pytest tests/integration/ -v   # run integration tests
# etc.
```

**Markers alternative:** Use `@pytest.mark.unit` etc. on test functions instead of directory nesting. Run with `pytest -m unit`.

## Stage 06: Static Analysis

Static-analysis tooling added and configured:

- **Ruff** — linting + format checking (blocking)
- **Mypy** — strict type checking (blocking)
- **Pyright** — strict type checking (advisory)
- **Import Linter** — architecture import contracts (blocking, 4 contracts in `.importlinter`)
- **Semgrep** — security pattern scanning (blocking, `--config .semgrep --error` for `src/`, excluding `src/waxprep/detector/`)
- **Vulture** — dead code detection (advisory)

Configuration lives in `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`, `[tool.pyright]`, `[tool.vulture]`) and `.importlinter`.

## Stage 07: Quality Gate

Consolidated CI quality gate in `.github/workflows/quality-gate.yml`:

**Trigger:** push to `main`, pull requests targeting `main`, and manual dispatch (Stage 10).

**Blocking jobs** (all must pass):
- `ci-audit` — workflow integrity: action pinning, permissions, triggers, jobs, matrix and evidence recording (Stage 10)
- `quality-setup` — uv sync + shared package cache
- `quality-gate` — ruff lint, ruff format, mypy (strict), import-linter, semgrep, dependency and supply-chain gate (Stage 09), hardcoding detector (Stage 08)
- `tests` — matrix of unit, integration, contract, lifecycle, architecture, configuration, regression
- `coverage-gate` — full suite with `--cov-fail-under=100` and the coverage XML artifact
- `smoke-test` — app boot + liveness/readiness health checks
- `supply-chain-evidence` — CycloneDX SBOM (required evidence) and trust report

**Advisory jobs** (recorded, never block acceptance):
- `pyright` — strict type check (`continue-on-error`, outcome recorded)
- `vulture` — dead code report (`continue-on-error`, outcome recorded)

**Acceptance job** (`ci-acceptance`) downloads every evidence artifact, binds it to `github.sha`, validates the coverage XML and SBOM contents, writes a JSON decision and the job summary, and fails unless every required job succeeded for that exact commit. A skipped, cancelled, failed, missing or stale result is a rejection, never a pass. See Stage 10 below.

**Vulnerability exceptions:** pip-audit runs without `--ignore-vuln`. `GHSA-53pm-wgxf-c6qf` (wcmatch 8.5.2) is recorded in `security/dependency-policy/vulnerability-exceptions.toml`, scoped to that package and version and expiring 2026-12-22. Expired exceptions and every uncovered advisory fail the gate.

**Local equivalent:** `make check` (Makefile) or `just check` (Justfile) run the same blocking checks locally.

## Stage 08: Universal Hardcoding Detection System

Independent, deterministic source-code detection system that identifies prohibited hardcoded conversational behavior in WaxPrep.

**Purpose:** The detector investigates HOW source code makes decisions about student messages, not just what words appear in the code. It prevents developers and AI coding agents from quietly introducing fixed input-dependent behavior into parts of WaxPrep where decisions are expected to be contextual, flexible, or delegated to an approved intelligence layer.

**Status:** Baseline implementation exists with documented detection limitations. Not all patterns are detected — see Known limitations below.

**Key characteristics:**
- Development-time tool only — not part of the production tutor response pipeline
- Operates deterministically without AI or network access
- Uses Python AST analysis (primary) and Semgrep structural rules (supplementary)
- Integrates with the existing Quality Gate
- Does not rely on a manually maintained forbidden-word list

**Detection rules (Living Specification):** See `docs/DETECTOR_SPECIFICATION.md`

| Rule ID | Description | Severity | Blocks Merge |
|---------|-------------|----------|--------------|
| WHD-001 | Fixed-string comparisons against student input | HIGH | Yes (protected) |
| WHD-002 | Fixed vocabulary membership tests | HIGH | Yes (protected) |
| WHD-003 | Fixed decision trees (if/elif chains, match/case) | MEDIUM | No — review |
| WHD-004 | Regex-based phrase detection | MEDIUM | No — review |
| WHD-005 | Word-to-action dictionary lookups | MEDIUM | No — review |
| WHD-006 | Deeply nested conditional structures | LOW | No |
| WHD-007 | Predetermined string responses | MEDIUM | No — review |
| WHD-008 | Hardcoded vocabularies | MEDIUM | No — review |
| WHD-009 | String-to-string mappings in data files | MEDIUM | No — review |
| WHD-010 | Vocabulary lists in data files | LOW | No |
| WHD-011 | Response templates in Markdown | LOW | No |

**Protected modules** (hardcoded conversational behavior prohibited):
- `waxprep.messaging` — Message handling & conversation flow
- `waxprep.context` — Understanding the learner
- `waxprep.services` — Light orchestration

**Enforcement policy:** a finding can exist, require human review, and/or block a merge — these are separate states. Only findings with `blocks_merge=true` fail the gate. WHD-001 and WHD-002 block inside protected modules; the remaining rules are review or informational findings and never block. The report counts blocking findings from that same property, so the report and the exit code cannot disagree.

**Usage:**
```bash
# Run the detector (explicit scope; default scope is src, docs, README.md,
# tests/README.md and pyproject.toml)
python -m waxprep.detector.cli [path ...] --format [text|json|summary]

# Run as quality gate check
python -m waxprep.detector.quality_gate [path] --format summary
```

**Test suite:** `tests/detector/` contains:
- `test_detector.py` — Unit tests for each WHD rule
- `test_adversarial.py` — Adversarial and mutation tests (with xfail for known limitations)
- `test_cli_and_quality_gate.py` — CLI and integration tests
- `test_coverage_gaps.py` — Coverage gap analysis
- `test_property.py` — Property-based tests

**Known limitations:**
- Cross-file data-flow analysis not implemented (imports, helper chains)
- Variable-based comparisons require constant propagation
- Dynamic string construction not detected
- Match/case routing is detected only when case patterns are string literals; guards are covered by WHD-001, not the branch count
- Some adversarial tests marked xfail for documented gaps
- Files that cannot be read or parsed are reported as scan problems and fail the gate; use `--allow-incomplete-scan` on the quality-gate entry point only when that is intentional
- Coverage gate excludes `waxprep/detector/quality_gate.py` (see pyproject.toml)

**CI integration:** The Quality Gate runs the detector over its explicit default scope:
```bash
uv run python -m waxprep.detector.cli --format summary
```
This inspects Python in `src/`, the active docs, `README.md`, `tests/README.md` and `pyproject.toml`. It does not scan the whole repository (which would include dependency trees and test fixtures).

## Stage 10: Continuous Integration

Stage 10 does not add another quality inspector. It makes the established systems independently executable, independently evidenced and independently verifiable, so a change is accepted because the systems actually ran and succeeded for exactly that commit.

**Architecture:** triggers → one job per responsibility (workflow audit, environment, static analysis + Stage 08/09 gates, test matrix, coverage, smoke test, supply-chain evidence, advisory pyright/vulture) → per-job evidence artifacts → a single `ci-acceptance` job that decides and reports.

**Evidence:** every job writes `ci-evidence/<job>.json` (job, classification, status, commit, run id, timestamp) and uploads it, including on failure (`if: always()`). Required reports are coverage XML and the CycloneDX SBOM; both are validated by content, not by existence.

**Acceptance rules:** a full 40-character commit SHA is required; `git rev-parse HEAD` must equal `github.sha`; every required job needs exactly one record, classified blocking, naming that commit, with status `success`; coverage `line-rate` must meet 1.0; every SBOM component needs a `purl`. Anything else is rejected with a stated reason. Advisory failures are warnings. There is no override flag.

**Workflow audit:** `uv run python -m waxprep.ci.cli audit` reads the workflow structure, not just its text. It fails if any action reference is a mutable tag, if least-privilege `permissions` are missing, if a required trigger or job is absent, if the tests matrix drifts from the declared categories, if a job stops recording evidence or records it under the wrong class, if a job stops uploading `ci-evidence-<job>` or uploads it from the wrong directory, if `ci-acceptance` stops downloading the evidence or a required report, if a required report is not validated from its producing job's output, if `ci-acceptance` does not run with `if: always()` or no longer depends on a required job, or if a job loses its timeout. All actions are pinned to full commit SHAs.

**Commands:**
```bash
uv run python -m waxprep.ci.cli audit              # workflow integrity
uv run python -m waxprep.ci.cli accept --help      # evidence-driven decision (CI use)
uv run pytest tests/regression -q                  # adversarial CI tests
```

**Adversarial testing:** `tests/regression/test_ci_*.py` prove that failed, cancelled, skipped, missing, duplicate, misclassified and stale-commit evidence all prevent acceptance, that malformed records (bad job id/file pair, run id, timestamp or exit code) cannot be read as success, and that advisory failures only warn. Advisory outcomes are reported as `passed`, `failed`, `not-executed`, `infrastructure-failure`, `cancelled`, `missing` or `stale-evidence`, so a tool that never ran is never reported as having passed. The workflow audit is tested by mutating the real pipeline definition: each rule has a case that removes or weakens exactly the property it enforces.

**Documentation:** [docs/STAGE_10_CI_SPECIFICATION.md](docs/STAGE_10_CI_SPECIFICATION.md), [docs/CI_OPERATIONS.md](docs/CI_OPERATIONS.md), [docs/CI_ACCEPTANCE_POLICY.md](docs/CI_ACCEPTANCE_POLICY.md), [docs/CI_SECURITY.md](docs/CI_SECURITY.md), [docs/STAGE_10_CORRECTION_REPORT.md](docs/STAGE_10_CORRECTION_REPORT.md).

**Known limitations:** `Dependency Review` is a separate workflow and cannot be consumed via `needs`, so it must be a required check in branch protection and is **not** part of the acceptance decision; 100% coverage refers to the measured scope (`waxprep` minus the documented `detector/quality_gate.py` exclusion); `tests/detector/` and `tests/supplychain/` run inside the coverage job rather than as matrix categories; evidence must be regenerated for every new commit; the workflow audit proves structure, not GitHub expression semantics, so execution evidence remains the only proof that the pipeline behaved as documented.

## Stage 09: Dependency and Supply-Chain Security

Development and release tooling that protects the external software WaxPrep depends on. It is separate from Stage 08, is never imported by the request path, and adds no runtime service or database.

**Blocking controls:**
- pip-audit runs without `--ignore-vuln`; exceptions are scoped per advisory, package and version in `security/dependency-policy/vulnerability-exceptions.toml` and expire automatically.
- `uv.lock` is mandatory; `uv lock --check` and `uv sync --frozen` remain in CI.
- Every runtime registry package must carry an artifact hash from `uv.lock`.
- Runtime dependencies must resolve from an approved registry; Git, URL, path and editable sources are rejected by policy.
- Every direct runtime dependency needs a version constraint, a resolved lock entry, a documented purpose and owner, and a reviewed major version.
- Licenses are classified from SPDX policy: approved passes, review requires a human decision, prohibited blocks, unknown requires review.
- OSV malicious-package (`MAL-`) advisories block; an OSV outage is a review finding, never a silent pass.

**Outputs:**
```bash
# Blocking gate (also inside make check / just check and CI)
uv run python -m waxprep.supplychain.cli check --format summary

# Dependency Trust Intelligence report
uv run python -m waxprep.supplychain.cli trust --output artifacts/dependency-trust.md

# CycloneDX 1.5 SBOM for the resolved runtime set
uv run python -m waxprep.supplychain.cli sbom --output artifacts/waxprep-sbom.cdx.json
```

**Policies:** `security/dependency-policy/` contains the vulnerability exception register, license policy, source policy and direct-dependency inventory. Policies are TOML so the gate adds no dependency of its own.

**GitHub workflows:**
- `quality-gate.yml` — blocking supply-chain gate on push and pull request.
- `dependency-review.yml` — pull-request review of newly introduced vulnerabilities and licenses.
- `dependency-security.yml` — weekly scheduled monitoring, trust report and SBOM artifacts keyed by commit SHA.
- `dependabot.yml` — weekly grouped patch/minor proposals and individual major proposals; nothing is auto-approved.

**Testing:** `tests/supplychain/` covers scoped exceptions and expiry, lockfile/source/hash failures, license decisions, malicious matches, OSV failure, SBOM shape, report rendering and CLI exit codes with synthetic fixtures and mocked scanners. No malicious package is installed.

**Known limitations:** license facts come from installed metadata rather than the source distribution and are not legal advice; provenance attestations are reported as `not-verified`, not checked; OSV coverage depends on published OpenSSF reports; pip-audit audits the installed environment, which includes development tools, while the inventory/SBOM/license checks cover the runtime closure; `uv`'s preview malware check is not enabled. See [docs/security/STAGE_09_DEPENDENCY_SECURITY.md](docs/security/STAGE_09_DEPENDENCY_SECURITY.md) and [docs/security/DEPENDENCY_EXCEPTION_POLICY.md](docs/security/DEPENDENCY_EXCEPTION_POLICY.md).

## Supporting Documentation

All project documentation is organized in the `docs/` folder:

### Active Documentation
- `docs/CONTRIBUTING.md` — How developers should contribute
- `docs/ENGINEERING-STANDARDS.md` — Engineering rules and conventions
- `docs/PR_REVIEW_CHECKLIST.md` — What reviewers should check before approving changes
- `docs/ARCHITECTURE_BOUNDARIES.md` — Package dependency rules and what each layer may import
- `docs/DETECTOR_SPECIFICATION.md` — Universal Hardcoding Detection rules (Stage 08)
- `docs/security/STAGE_09_DEPENDENCY_SECURITY.md` — Dependency and supply-chain controls (Stage 09)
- `docs/STAGE_10_CI_SPECIFICATION.md` — CI architecture, execution model and acceptance rules (Stage 10)
- `docs/CI_OPERATIONS.md` — Running, reading, investigating and re-running the pipeline (Stage 10)
- `docs/CI_ACCEPTANCE_POLICY.md` — Blocking versus advisory, evidence requirements and the decision table (Stage 10)
- `docs/CI_SECURITY.md` — Workflow permissions, action pinning, cache integrity and tool evaluation (Stage 10)
- `docs/STAGE_10_IMPLEMENTATION_REPORT.md` — Stage 10 implementation results and limitations
- `docs/STAGE_10_CORRECTION_REPORT.md` — Post-implementation verification pass: issues found, corrections and evidence
- `docs/CONFIGURATION_REFERENCE.md` — Configuration settings, validation, precedence and production policy (Stage 11)
- `docs/ENVIRONMENT_SETUP.md` — Operating WaxPrep in development, test, staging and production (Stage 11)
- `docs/STAGE_11_CORRECTION_REPORT.md` — Stage 11 corrective verification pass (historical record)
- `docs/STAGE_11_HARDENING_REPORT.md` — Independent review follow-up: loading consistency, isolation, startup and typo hardening
- `docs/security/DEPENDENCY_EXCEPTION_POLICY.md` — Vulnerability exception register and expiry rules
- `docs/SECURITY_AND_SECRETS.md` — Secret classification, precedence, inventory, rotation/revocation and incident response (Stage 12)
- `docs/OBSERVABILITY_AND_LOGGING.md` — Log schema, severity policy, correlation, telemetry, metric catalogue and cardinality (Stages 13–14)
- `docs/ERROR_HANDLING.md` — Error taxonomy, boundaries, public HTTP contract and retry policy (Stage 15)
- `docs/OPERATIONS_RUNBOOK.md` — On-call triage, category table, scenarios, deploy and rollback
- `docs/APPLICATION_LIFECYCLE.md` — Lifecycle states, resource ownership, initialization order, cleanup and re-entry (Stage 16)
- `docs/LIFECYCLE_OPERATIONS.md` — Startup failure, cancellation, shutdown and lifecycle diagnosis (Stage 16)
- `docs/LIFECYCLE_TESTING.md` — Lifecycle invariants, failure injection and adversarial testing (Stage 16)
- `docs/STAGE_16_IMPLEMENTATION_REPORT.md` — Stage 16 decisions, evidence and limitations
- `docs/INTERNAL_COMMUNICATION_CONTRACTS.md` — Contract layers, envelope, validation and schema policy (Stage 17)
- `docs/CONTRACT_EVOLUTION.md` — Contract identity, compatibility classes and migration (Stage 17)
- `docs/CONTRACT_TESTING.md` — Contract verification strategy and invariants (Stage 17)
- `docs/STAGE_17_IMPLEMENTATION_REPORT.md` — Stage 17 decisions, evidence and limitations
- `docs/DEPENDENCY_INJECTION_AND_COMPOSITION.md` — Composition root, typed graph, lifetimes and lifecycle integration (Stage 18)
- `docs/COMPOSITION_TESTING.md` — Composition invariants, overrides, failure injection and static enforcement (Stage 18)
- `docs/STAGE_18_IMPLEMENTATION_REPORT.md` — Stage 18 decisions, evidence and limitations

### Archive (Historical/Superseded)
- `docs/archive/` — Contains superseded documents:
  - `STAGE_01_02_SPEC.md` — Original Stage 01-02 specification (superseded by README)
  - `STAGE_03_ARCHITECTURE.md` — Original Stage 03 architecture (merged into README)
  - `STAGE_07_STATIC_ANALYSIS.md` — Static analysis audit (superseded by CI workflow)
  - `STAGE06_STATIC_ANALYSIS_RESEARCH.md` — Stage 06 research (superseded by Stage 07)
  - `STAGE03_BOUNDARIES.md` — Stage 03 boundary notes (superseded by ARCHITECTURE_BOUNDARIES.md)
  - `IMPLEMENTATION_PLAN.md` — Original implementation plan (completed)
  - `INDEPENDENT_AUDIT_STAGE_01_07.md` — Independent audit report
  - `FUNDATION_CORRECTION_REPORT.md` — Foundation correction report
  - `TEST_PLAN_STAGE_03.md` — Stage 03 test plan

## Configuration Policy

WaxPrep uses configurable defaults via environment variables (WAXPREP_ prefix).

### What Is Configured via Environment (WAXPREP_ prefix)
- Environment name (`WAXPREP_ENVIRONMENT`, default: `development`)
- Host binding (`WAXPREP_HOST`, default: `0.0.0.0`)
- Port (`WAXPREP_PORT`, default: `8000`)
- Log level (`WAXPREP_LOG_LEVEL`, default: `info`)

### What Are Acceptable Defaults
Development defaults are provided for convenience. Production deployments must override via environment:

- Default environment: `development`
- Default host: `0.0.0.0`
- Default port: `8000`
- Default log level: `info`

### What Is Not Hardcoding
- Configurable defaults with environment override are not hardcoded values
- Test constants are not operational hardcoding
- Architectural invariants (e.g., HTTP methods, status codes) are not configuration

### What Would Be Hardcoding (Forbidden)
- Operational values that should vary across environments without configuration
- Model names, API keys, credentials
- Channel identifiers that should be configurable
- Student levels, greetings, keyword routes that are domain-specific

Configuration lives in environment variables via Pydantic Settings.

## Registry Pattern

Each adapter type (channels, models, tools) has a registry that:
- Accepts adapters via `register(name, adapter)`
- Validates adapters conform to the protocol
- Retrieves by name with `get(name)` (raises KeyError if missing)
- Lists all registered with `list_all()`
- Checks registration with `is_registered(name)`

**Important: Registries are NOT populated at import time.** 
Use `register_defaults()` explicitly in the application lifespan to populate with fake adapters for testing.

In Stages 01-02, each registry contains ONE fake adapter to prove the pattern works.

## Land Not House Philosophy

Stage 03 is about preparing the land, not building a house.

**We are building:**
- ✅ Clear package boundaries
- ✅ Dependency direction rules
- ✅ Protocol definitions
- ✅ Placeholders for future layers

**We are NOT building:**
- ❌ Complete domain entity hierarchy
- ❌ Full application service layer
- ❌ Real infrastructure implementations
- ❌ Production-ready adapter implementations

**Why "Land Not House":**
A house dictates exactly what goes where. A house is hard to remodel.
Land with clear boundaries, utilities, and foundations:
- Can accommodate any house design
- Easy to change the house without changing the land
- Multiple houses can share the same land

For WaxPrep:
- The domain boundaries we establish now will outlast any specific implementation
- When we add identity generation (Stage 04 Wax ID), it fits into the existing structure
- When we add AI models, they fit into the existing adapter structure
- The architecture enables change without requiring architectural changes

## Running Tests

Prerequisite (sync dev dependencies once):

```bash
uv sync --extra dev
```

Full suite:

```bash
uv run pytest tests/ -v
```

With coverage:

```bash
uv run pytest tests/ -v --cov=waxprep --cov-report=term-missing
```

Local quality gate (matches CI blocking checks, including the Stage 10 workflow audit):

```bash
make check
# or
just check
```

Acceptance evidence can only be produced by a workflow run. The local equivalent
of the acceptance decision is the adversarial regression suite:

```bash
uv run pytest tests/regression -q
uv run python -m waxprep.ci.cli audit
```


## Running the Application

The canonical startup method is the application entrypoint. It reads the validated
configuration, so `WAXPREP_HOST` and `WAXPREP_PORT` always control the address the
server actually binds:

```bash
uv run python -m waxprep.main
# or, after `uv sync`, the console script:
uv run waxprep
```

For development with auto-reload, Uvicorn's CLI can be used, but it does not read
`WAXPREP_HOST`/`WAXPREP_PORT` implicitly — pass the same values explicitly:

```bash
uv run uvicorn waxprep.main:get_app --host "${WAXPREP_HOST:-0.0.0.0}" --port "${WAXPREP_PORT:-8000}" --reload
```

Direct `uvicorn` invocation is an advanced/debug path; use the entrypoint above for
deployments on Railway or Render so configuration stays authoritative.

## Configuration (WAXPREP_ prefix) — Stage 11

All configuration uses the `WAXPREP_` prefix to avoid conflicts with sandbox environment variables.
Configuration is centrally managed by `src/waxprep/config.py` and validated at startup.
Invalid configuration prevents application startup with a clear error.

| Variable | Default | Description | Validation |
|----------|---------|-------------|------------|
| `WAXPREP_ENVIRONMENT` | development | Environment name (`development`, `test`, `staging`, `production`) | Must be one of the four recognised values |
| `WAXPREP_HOST` | 0.0.0.0 | Bind host | Must be non-empty |
| `WAXPREP_PORT` | 8000 | Bind port | Integer 1–65535 |
| `WAXPREP_LOG_LEVEL` | info | Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) | Normalised to uppercase; must be a recognised level |

Configuration sources (precedence): OS environment variables > `.env` file > validated defaults.
OS environment variables always override `.env` file values.

A `.env.example` file is provided with safe development defaults.
The real `.env` file is excluded from Git via `.gitignore`.
For production, supply all values via the hosting environment.

Unknown `WAXPREP_` variables (typos, unsupported settings) produce warnings to stderr
without preventing startup. Known misspellings are detected and mapped to their correct names.

Note: `WAXPREP_SHUTDOWN_GRACE_PERIOD` has been removed. Graceful request draining is managed by the ASGI server (uvicorn) lifecycle; WaxPrep adds explicit resource shutdown, rollback and bounded cleanup timeouts (Stage 16).

For the full configuration reference including validation rules, precedence, production policy,
unknown-variable detection, and error handling, see `docs/CONFIGURATION_REFERENCE.md`.

## Health Endpoints

### Liveness (`GET /health/liveness`)
Returns whether the process is alive. Always returns 200 if the app is running.

```json
{"status": "alive"}
```

### Readiness (`GET /health/readiness`)
Returns whether the application is ready to serve requests. Checks:
- Configuration has a non-empty environment value
- Registries are initialized
- Default adapters are registered in each registry

Reports only what the application can independently verify. Does not include middleware status since that is not independently checked.

```json
{
  "status": "ready",
  "checks": {
    "configuration": "ok",
    "channel_registry": "ok",
    "model_registry": "ok",
    "tool_registry": "ok"
  }
}
```

If not ready, returns 503 with reason.

## Correlation ID Middleware

Every request receives a correlation ID:
- Generated as UUID if `X-Request-ID` header not provided
- Propagated from `X-Request-ID` header if provided
- Bound to structlog context for request lifetime
- Added to response headers as `X-Request-ID`

This enables request tracing in logs without requiring distributed tracing infrastructure.

## Exception Handling

The application includes global exception handlers:
- **HTTP exceptions**: Return clean JSON with status code and path
- **Validation errors**: Return structured error list (sanitized)
- **Unhandled exceptions**: Return generic 500 error, log full details server-side

No stack traces are leaked to clients.
