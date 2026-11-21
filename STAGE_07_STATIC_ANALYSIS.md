# Stage 07 — Static Analysis Audit Report

**Project:** WaxPrep (`waxprep`, Python >= 3.14, hatchling/uv)
**Auditor:** Static Analysis Engineer
**Status:** Audit only — no configuration changes implemented
**Source files reviewed:** `pyproject.toml`, `.importlinter`, `vulture.cfg.py`, `justfile`, `CONTRIBUTING.md`, `docs/ENGINEERING-STANDARDS.md`, `.github/workflows/test.yml`, `src/waxprep/` package tree

---

## 1. Current Tool Configuration and Blocking vs Advisory Status

| Tool | Purpose | Config source | Blocking? | CI job (test.yml) | Local command (`justfile`) |
|------|---------|---------------|-----------|-------------------|----------------------------|
| **ruff** (lint) | Linting: E, F, I, N, W, UP + curated S* and RUF* rules | `[tool.ruff.lint]` in pyproject.toml | Yes | `ruff-lint` (3 min) | `just lint` → `uv run ruff check src/ tests/` |
| **ruff** (format) | Formatting check | `[tool.ruff.format]` (defaults) | Yes | `ruff-format` (3 min) | `just format` → `uv run ruff format --check src/ tests/` |
| **mypy** | Static type checking, strict | `[tool.mypy]` (`strict = true`, py314) | Yes | `mypy` (5 min) | `just type` (first of two) → `uv run mypy src/` |
| **pyright** | Static type checking, strict | `[tool.pyright]` (`typeCheckingMode = "strict"`, py314) | Yes | `pyright` (5 min) | `just type` (second of two) → `uv run pyright src/` |
| **import-linter** | Import-structure / layering enforcement | `.importlinter` (4 contracts) | Yes | `import-linter` (3 min) | `just import-linter` → `uv run importlinter src/waxprep/` |
| **semgrep** | Security scan | `--config auto` (remote registry), `--error` flag | Yes | `semgrep` (5 min) → `--config auto --error src/` | `just semgrep` → `uv run semgrep --config auto src/` |
| **vulture** | Dead code detection | `pyproject.toml` `[tool.vulture]` + `vulture.cfg.py` | Advisory (`continue-on-error: true`) | `vulture` (3 min) | `just vulture` → `uv run vulture src/waxprep/ --min-confidence 80` |

**Summary of blocking/advisory split:** 6 blocking tools (ruff lint, ruff format, mypy, pyright, import-linter, semgrep) and 1 advisory tool (vulture). The split is correctly implemented in CI (vulture uses `continue-on-error: true`; all others fail the job on non-zero exit). CONTRIBUTING.md §"Static Analysis" and docs/ENGINEERING-STANDARDS.md §"Static Analysis" both document this split accurately.

### Configuration details observed

**pyproject.toml — `[tool.vulture]`**
- `min_confidence = 80`
- `exclude = ["*/tests/*", "*/__pycache__/*", "*/**/__pycache__/*"]`
- `ignore_names` lists 14 symbols (registry registration, fake adapters, factory functions, Pydantic `model_config`, FastAPI exception handlers, route handlers, `get_app`, middleware skeletons, protocols).
- `ignore_decorators = []`

**pyproject.toml — `[tool.ruff]`**
- `line-length = 100`, `target-version = "py314"`, `preview = true`
- select: E, F, I, N, W, UP; S102, S105, S106, S301–S304, S323, S324; RUF005–009, RUF012–019, RUF024, RUF029
- `exclude = ["tests/"]` (tests excluded from config, but linted via CLI in justfile/CI)
- No `ignore` list, no per-file rules, no `unfixable`, no `isort` settings.

**pyproject.toml — `[tool.mypy]`**
- `python_version = "3.14"`, `strict = true`
- No `exclude`, no `ignore_missing_imports`, no `warn_return_any`, no per-module overrides, no `plugins`.

**pyproject.toml — `[tool.pyright]`**
- `pythonVersion = "3.14"`, `typeCheckingMode = "strict"`
- Minimal; no `exclude`, no `reportMissingTypeStubs` tuning, no execution environments.

**.importlinter — 4 contracts**
1. Contract 1 (`forbidden`): source `waxprep.core` must not import `waxprep.registries`, `waxprep.adapters`, `waxprep.middleware`, `waxprep.main`, `waxprep.config`.
2. Contract 2 (`allowed`): sources `waxprep.main`, `waxprep.middleware`, `waxprep.registries`, `waxprep.adapters` may import only `waxprep.core`.
3. Contract 3 (`forbidden`): source `waxprep.adapters` must not import `waxprep.middleware`, `waxprep.main`.
4. Contract 4 (`allowed`): source `waxprep.adapters` may import `waxprep.core`.

**justfile — `check` recipe**
- `check: lint format type import-linter semgrep` — vulture is intentionally NOT in `check` (advisory only).

**CI — `import-linter` job**
- Runs `uv run import-linter lint --no-logo | tee /tmp/imlit.out`, then greps output for "broken" and exits 1 if found. This is a non-standard exit-code check (import-linter exits non-zero on violations natively; the grep adds fragility).

**CI — `semgrep` job**
- `uv run semgrep --config auto --error src/` — includes `--error`, so non-zero exit on findings. Blocking.

**CI — vulture job**
- `uv run vulture src/waxprep/ --min-confidence 80` with `continue-on-error: true`. Advisory.

---

## 2. Gaps in the Quality Gate


### 2.1 Missing tools / categories
No tool covers the following categories, which are standard in a Python quality gate:

| Missing category | Example tools | Risk if absent |
|------------------|---------------|----------------|
| Dependency vulnerability scanning | `pip-audit`, `safety`, `osv-scanner` | Known-vulnerable dependencies enter the tree undetected (semgrep `--config auto` catches code patterns, not dependency advisories). |
| Secret detection | `detect-secrets`, `truffleHog`, `gitleaks` | Hardcoded credentials/API keys; ruff S105/S106 only catch literal strings in code, not env files, configs, or git history. |
| Complexity / maintainability | `radon`, `mccabe` (ruff has no complexity rules selected) | No guardrail on cyclomatic complexity or maintainability index. |
| Documentation checks | `pydocstyle` / ruff `D` | No docstring convention enforcement despite CONTRIBUTING requiring docstrings on public functions. |

### 2.2 Misconfigured / inconsistent thresholds

**a) Vulture whitelist is effectively unused.**
- `pyproject.toml` `[tool.vulture]` and `vulture.cfg.py` both define a curated `ignore_names` list (14 symbols) documenting deliberate false positives: dynamic `register_defaults()`, fake adapters, FastAPI handlers, Pydantic `model_config`, protocols, middleware skeletons.
- The `just vulture` recipe runs `uv run vulture src/waxprep/ --min-confidence 80` **without** `--config vulture.cfg.py`. Vulture auto-reads `pyproject.toml` `[tool.vulture]`, so the pyproject ignores apply locally — but `vulture.cfg.py` is only read if passed via `--config`. The justfile comment says "(advisory — does not affect exit code)" yet the command does not point at `vulture.cfg.py`, and the CI job likewise omits `--config`. The carefully maintained whitelist therefore drifts from the command actually executed; running the documented local command will flag `register_defaults`, `FakeChannelAdapter`, `get_app`, route handlers, etc. as dead code.
- `min_confidence = 80` is set in three places (pyproject.toml, `vulture.cfg.py`, and the justfile/CI CLI) with no single source of truth.

**b) Semgrep `--error` flag mismatch between CI and local.**
- CI: `uv run semgrep --config auto --error src/` (blocking, exits non-zero on findings).
- `just semgrep`: `uv run semgrep --config auto src/` (**no** `--error`), so locally `just check` can report semgrep findings yet still return success. The quality gate is weaker locally than in CI.

**c) Ruff test-exclusion inconsistency.**
- `pyproject.toml` `[tool.ruff.lint] exclude = ["tests/"]` excludes tests from linting by config, yet both `just lint` and the CI `ruff-lint` job explicitly pass `tests/` on the CLI, overriding the exclusion. Contributors reading `pyproject.toml` believe tests are excluded; the CLI commands contradict that.

**d) Import-linter invocation mismatch.**
- `just import-linter`: `uv run importlinter src/waxprep/` (passes a path argument).
- CI `import-linter`: `uv run import-linter lint --no-logo` plus a fragile `grep broken` post-check. Two different commands for the same gate; the grep adds a failure mode unrelated to import-linter's own exit code.

### 2.3 No failure-mode documentation for flaky/remote tooling
- Semgrep `--config auto` pulls rules from Semgrep's public registry at runtime: results can change between runs as rules are updated, making the gate non-deterministic and requiring network access in CI.
- No pinning of ruff `preview` ruleset version; `preview = true` enables rules (e.g. RUF029 unused-async) that may change behavior between ruff releases.

---

## 3. Redundancy: mypy + pyright both strict

**Observation:** Both type checkers are configured strict and both run in `just type`, in CI as separate blocking jobs, and are documented as blocking in CONTRIBUTING.md and docs/ENGINEERING-STANDARDS.md. The pyproject.toml itself contains an explicit comment (lines 95–99) acknowledging this is redundant and recommending consolidation.

**Impact:**
- Double CI time (~10 min across two jobs) and double local type-check time for a codebase of ~20 source files.
- Divergent error messages: mypy and pyright report overlapping errors differently, creating noise when one flags an issue the other does not.
- Contributor friction: CONTRIBUTING pre-push checklist and ENGINEERING-STANDARDS list both checkers, so contributors must satisfy two strict type systems.

**Recommendation (per existing pyproject.toml comment):** Keep mypy as the single primary strict type checker (mature, broad ecosystem, CI-friendly, config already in pyproject.toml), and either drop pyright or relax it to `typeCheckingMode = "basic"` for cross-validation only. Remove pyright from the `just type` recipe and from CI, keeping one blocking type-check job.

---

## 4. Import-Linter Contract Completeness

The actual source tree contains these top-level packages/modules under `src/waxprep/`:
`core/`, `adapters/`, `registries/`, `middleware/`, `messaging/`, `context/`, `services/`, plus `config.py`, `id.py`, `main.py`.

**Gaps and contradictions:**

1. **`messaging`, `context`, `services`, `id`, `config` are absent from all contracts.**
   - Contract 1 forbids `core` from importing only `registries`, `adapters`, `middleware`, `main`, `config`. `core` could import `messaging`, `context`, `services`, or `id` without triggering Contract 1 — a direct violation of the documented Outer→Inner rule (core must import nothing from `waxprep.*`).
   - Contract 2 lists only `main`, `middleware`, `registries`, `adapters` as allowed-to-import-core. `messaging`, `context`, `services` all import from `core` per CONTRIBUTING §Architecture Boundaries, but Contract 2 does not cover them, so those legal dependencies are not formally asserted (and could be accidentally broken without detection).
   - Contract 4 states adapters *may* import `waxprep.core`, but CONTRIBUTING §File Organization table and §Architecture Boundaries state adapters may **not** import from `core/` ("adapters/ ──→ registry protocols (NOT core/)"). This is a direct contradiction between `.importlinter` Contract 4 and the project documentation.

2. **No contract enforces "adapters may not import concrete adapters/services/messaging/context".** Contract 3 only blocks adapters → `middleware`, `main`. Per the documented architecture, adapters should depend on registry protocols/SDKs only, not on concrete modules in other outer layers. This is unenforced.

3. **Contract 2 is redundant with Contract 1.** Contract 1 already enforces "core must not import outer layers"; Contract 2 merely documents the inverse direction as `allowed` with source_modules = outer layers and allowed_modules = core. An `allowed` contract only *permits* listed imports; it does not *forbid* imports to non-listed modules, so Contract 2 adds no enforcement beyond documentation. It could be replaced by extending Contract 1's `forbidden_modules` to cover all outer packages.

4. **No contract enforces registries directionality.** Documented rule: `messaging`, `context` must use registries and not import concrete adapters. No import-linter contract enforces this.

**Recommended contract set (non-exhaustive):**
- Extend Contract 1 `forbidden_modules` to include `waxprep.messaging`, `waxprep.context`, `waxprep.services`, `waxprep.id` (core imports nothing from waxprep).
- Extend Contract 2 `source_modules` to include `waxprep.messaging`, `waxprep.context`, `waxprep.services` (all outer layers may import core).
- Resolve the Contract 4 contradiction: either adapters may import core protocols (update docs) or adapters must not import core (remove Contract 4 / make it `forbidden`).
- Add a contract forbidding `waxprep.adapters` from importing `waxprep.messaging`, `waxprep.context`, `waxprep.services`, `waxprep.registries` concrete modules (adapters depend on registry protocols/SDKs only).

---

## 5. Semgrep Configuration (`--config auto`, `--error` flag)

| Item | Observation | Assessment |
|------|-------------|------------|
| Ruleset | `--config auto` (Semgrep public registry) | Non-deterministic: rule content can change between CI runs. Requires network. Hard to audit exactly what is being enforced. |
| Target | `src/` | Only source scanned; tests and config files not scanned. Acceptable for a security scan of shipped code. |
| Exit behavior | CI uses `--error`; `justfile` omits it | Local/CI inconsistency: `just check` may pass while CI fails. |
| Ignore file | No `.semgrepignore` | No way to exclude generated files, fixtures, or vendored code except inline `# semgrep: ignore`. |
| CI timeout | 5 minutes | Reasonable for `--config auto` but network-dependent downloads add variability. |

**Recommendation:** Pin a specific ruleset (e.g. a pinned semgrep registry config or a vendored local `semgrep.yml`) for deterministic, offline-capable scans. Add `--error` to the `just semgrep` recipe so local and CI behavior match. Add `.semgrepignore` for exclusions.

---

## 6. Recommendations for Consolidation and Reliability

### High priority

1. **Consolidate type checkers.** Keep mypy strict as the single blocking type-check tool. Remove pyright from `just type`, CI, CONTRIBUTING.md, ENGINEERING-STANDARDS.md, and pyproject.toml (or relax pyright to `basic` and make it advisory). This aligns with the existing recommendation already documented in pyproject.toml lines 95–99.

2. **Make vulture's whitelist authoritative.** Ensure the justfile vulture recipe and CI job both read the curated config (`uv run vulture src/waxprep/ --config vulture.cfg.py` or rely solely on `[tool.vulture]` in pyproject.toml and remove `vulture.cfg.py`). Pick one config source; remove `min_confidence` duplication by keeping it in pyproject.toml only and omitting the CLI `--min-confidence 80` flag.

3. **Align `just check` with CI.** Add `--error` to `just semgrep`. Make ruff lint/format commands in the justfile match the config (decide whether tests are linted; if yes, remove `exclude = ["tests/"]` from pyproject.toml; if no, stop passing `tests/` on the CLI).

4. **Pin semgrep rules.** Replace `--config auto` with a pinned/local ruleset to avoid silent gate changes when the Semgrep registry updates. Add `.semgrepignore`.

5. **Standardize import-linter invocation.** Use the same command in justfile and CI (`uv run import-linter lint` or `uv run importlinter` without path args), and rely on import-linter's native exit code instead of the `grep broken` post-check in CI.

### Medium priority

6. **Expand import-linter contracts.** Cover `messaging`, `context`, `services`, `id` in the core-isolation contract; resolve the adapters↔core contradiction; add adapter-to-outer-layer restrictions per documented architecture.

7. **Add missing quality-gate categories.** Consider `pip-audit` (dependency vulnerabilities) and secret detection as blocking CI jobs; consider ruff `D` (pydocstyle) given docstring requirements in CONTRIBUTING.

8. **Ruff configuration hardening.** Add `ignore` or `unfixable` rules as needed; consider pinning ruff version in `uv.lock`/`dev` dependencies since `preview = true` makes behavior release-sensitive. Decide whether `tests/` should be excluded and make config + CLI agree.

9. **Tighten mypy config.** Add `exclude`, `warn_return_any`, and consider `disallow_any_generics` under strict; pyright can be dropped entirely once consolidated.

### Low priority

10. **Documentation sync.** After changes, update CONTRIBUTING.md §Static Analysis table, docs/ENGINEERING-STANDARDS.md §Static Analysis table, and the pyproject.toml tool comments to reflect the final tool set and blocking/advisory status.

---

### Discrepancy quick-reference (to fix when implementing)

| Area | pyproject.toml / config | justfile | CI (test.yml) | Docs |
|------|------------------------|----------|---------------|------|
| semgrep exit | n/a | missing `--error` | `--error` present | `--error` not mentioned |
| vulture config | `[tool.vulture]` + `vulture.cfg.py` | no `--config` | no `--config` | runs without `--config` |
| ruff tests | `exclude = ["tests/"]` | lints `tests/` | lints `tests/` | lints `src/ tests/` |
| type checkers | mypy + pyright both strict | both | both | both listed |
| import-linter | 4 contracts | `importlinter src/waxprep/` | `import-linter lint --no-logo` + grep | `importlinter src/waxprep/` |

