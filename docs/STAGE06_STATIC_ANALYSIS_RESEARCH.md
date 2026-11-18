# Stage 06: Static Analysis — Research Document

**Status:** Research / Planning  
**Date:** 2026-11-18  
**Branch:** main  
**Scope:** Evaluate and recommend static analysis tooling expansion for the WaxPrep codebase.

---

## 1. Current State: What We Already Have

### 1.1 Ruff (Linting)

**Configuration** (`pyproject.toml`):

| Setting | Value |
|---|---|
| `line-length` | 100 |
| `target-version` | py314 |
| `lint.select` | `["E", "F", "I", "N", "W", "UP"]` |

**Rule categories in use:**

| Code | Category | Examples covered |
|---|---|---|
| `E` | pycodestyle errors | Whitespace, missing newlines, syntax issues |
| `F` | Pyflakes | Unused imports, undefined names, duplicate keys |
| `I` | isort | Import ordering and grouping |
| `N` | pep8-naming | Function/class/variable naming conventions |
| `W` | pycodestyle warnings | Line length (soft), bare except, etc. |
| `UP` | pyupgrade | Modernize syntax for target Python version |

**What this covers well:**

- Import hygiene (unused, ordered, grouped)
- Basic style enforcement (naming, whitespace)
- Syntax modernization (pyupgrade targeting 3.14)
- Quick surface-level correctness (undefined names, duplicate definitions)

**What this does NOT cover:**

- Deeper type errors beyond what pyflakes catches
- Security patterns (injection, hardcoded secrets, unsafe deserialization)
- Architecture boundaries (forbidden cross-package imports)
- Dead code detection (unused functions/classes that pass F401 because they're exported or referenced dynamically)
- Custom project-specific patterns

### 1.2 mypy (Type Checking)

**Configuration** (`pyproject.toml`):

```toml
[tool.mypy]
python_version = "3.14"
strict = true
```

**Strict mode enables:** `disallow_any_generics`, `disallow_subclassing_any`, `disallow_untyped_calls`, `disallow_untyped_defs`, `disallow_incomplete_defs`, `check_untyped_defs`, `disallow_untyped_decorators`, `warn_redundant_casts`, `warn_unused_ignores`, `warn_return_any`, `warn_unreachable`, `strict_equality`, `strict_concatenate`.

**Role in the stack:** Primary type checker. Catches type mismatches, missing annotations, unsafe `Any` usage, unreachable code (via `warn_unreachable`).

### 1.3 pyright (Secondary Type Checking)

**Configuration** (`pyproject.toml`):

```toml
[tool.pyright]
pythonVersion = "3.14"
typeCheckingMode = "strict"
```

**Role in the stack:** Complementary type checker. Different inference engine from mypy; catches different classes of issues. Running both provides defense-in-depth against type errors that one engine might miss.

### 1.4 Boundary Tests (Architecture Validation)

**From CI** (`.github/workflows/test.yml`): The `architecture-tests` job runs `pytest tests/architecture/`. This is a manual/semi-manual boundary enforcement mechanism — likely testing that certain modules do not import from forbidden layers, or that dependency rules are respected.

**What this covers:** Architectural layer boundaries, forbidden import paths, layer dependency rules.

**What this does NOT cover:** It is a test-based approach, meaning:
- It is Python-executed, not a static analysis tool
- It requires writing explicit test cases for each boundary rule
- It may not catch all violations if test coverage of import paths is incomplete
- It runs at test time, not lint time (slower feedback loop)

---

## 2. Gaps: What Is Missing

### 2.1 Dead Code Detection

**Problem:** No tool currently identifies unused functions, classes, methods, or variables.

**Impact:**
- Each sprint may accumulate dead code that is no longer called but remains in the codebase
- Dead code increases cognitive load, confuses readers, and may be accidentally resurrected
- Test coverage metrics can mask dead code if the dead code is still "covered" by tests that reference it through dynamic mechanisms

**Why Ruff's `F` rules are insufficient:**
- `F841` (unused local variable) catches some cases but only within a single function scope
- `F401` (unused import) catches imports but not unused definitions
- Functions/classes that are defined and exported (e.g., in `__init__.py`) but never actually used elsewhere pass all existing rules

### 2.2 Machine-Enforced Import Rules (Architecture Boundaries)

**Problem:** Import boundaries are enforced only through architecture tests, not through a dedicated import-linter tool.

**Impact:**
- Architecture tests are valuable but require manual test authoring for each rule
- A dedicated import linter can express rules declaratively and check all imports statically in one pass
- Without this, the architecture test suite may have blind spots

**Specific architectural concerns for this codebase:**
- The project uses FastAPI, Pydantic, and structlog — there may be layering rules (e.g., domain layer should not import from infrastructure layer)
- Import-linter would allow expressing these as explicit, machine-checked contracts

### 2.3 Security Pattern Matching

**Problem:** No static security analysis tool is installed.

**Impact:** The project handles HTTP (FastAPI), data validation (Pydantic), structured logging (structlog), and configuration (python-dotenv). Security-relevant patterns that could be caught statically include:
- Use of `eval()`, `exec()`, or `compile()` with user-controllable input
- Unsafe deserialization (e.g., `pickle.loads` on untrusted data)
- Hardcoded secrets or credentials in source
- SQL injection patterns (if any raw SQL is constructed)
- Insecure temporary file usage
- Use of weak cryptographic primitives

**Note:** This project may have low surface area for some of these (e.g., if no raw SQL, no pickle), but a lightweight security scanner provides insurance against accidental introduction.

### 2.4 Custom Pattern Matching

**Problem:** No tool for project-specific, custom lint rules.

**Examples of rules that could be expressed:**
- "Do not use `print()` in production code" (require `structlog` instead)
- "All FastAPI route handlers must have a response model specified"
- "Configuration values must come from `pydantic-settings`, not from `os.environ` directly"
- "Avoid certain deprecated patterns as the project evolves"

---

## 3. Tool Recommendations with Justification

### 3.1 Ruff — Expand Rule Coverage

**Recommendation:** **Primary linting engine. Expand select rules.**

**Justification:**
- Ruff is already the project's linting backbone, fast, and well-integrated
- It has grown significantly in rule coverage; expanding the `select` list provides more coverage at zero additional tool installation cost

**Proposed rule additions (evaluate each during implementation):**

| Code | Category | Value | Noise risk |
|---|---|---|---|
| `C4` | flake8-comprehensions | Faster, clearer comprehensions/list/dict/set operations | Low |
| `C90` | flake8-tidy-imports (ban-relative-imports) | Enforce absolute imports over relative where appropriate | Low–Medium (may conflict with existing relative import style) |
| `EXE` | exec-use | Catches `exec()`, `eval()`, `compile()` usage | Low (should always be caught) |
| `ISC` | implicit-str-concat | Catches string concatenation in lists that should use `.join()` or triple-quoted strings | Low |
| `NPY` | PEP 484 numpy-style type hints | If NumPy-style annotations are not used, this enforces standard form | Depends on project conventions |
| `PIE` | unnecessary-code | Catches unnecessary `if True`, `if False`, `elif` after `return`, etc. | Low |
| `PL` | Pylint rules | Broad category; selectively enable subsets (e.g., `PLR` logical redundancy, `PLE` exceptions) | Medium — Pylint has many rules; cherry-pick |
| `PT` | pytest style | If pytest is used (it is), enforces pytest best practices | Low for a pytest-heavy project |
| `RET` | return-value linting | Catches functions that return values inconsistently | Low |
| `SIM` | simplify code | Catches unnecessarily complex expressions that can be simplified | Low |
| `TCH` | type-checking imports | Catches imports only used for type checking that should use `TYPE_CHECKING` block | Low–Medium |
| `TID` | tidy imports (ban-relative-imports) | Same as `C90`; choose one | Low |
| `TID` | `TID251` (logging-fstring-score) | Warns about f-strings in logging calls (should use lazy %-formatting or structlog's native handling) | Medium — relevant if structlog's recommended patterns are preferred |
| `RUF` | Ruff-specific rules | Catches deprecated Ruff configuration, unnecessary `# noqa` comments, etc. | Low |

**Advice on expansion:** Add in small batches, run on the full codebase, triage noise, then commit. Do not add all at once.

### 3.2 mypy + pyright — Keep Complementary

**Recommendation:** **Continue running both. Do not drop either.**

**Justification:**
- mypy and pyright have different type inference engines and different false-negative profiles
- What one misses, the other often catches
- Both are already configured in strict mode; the marginal cost of running both is low compared to the benefit of redundant type safety
- Dropping one would reduce the probability of catching certain classes of type errors

**Potential future consideration:** If CI time becomes a concern, evaluate which catches more unique issues on this codebase and consider making the other advisory-only (e.g., run in CI as a non-blocking check, or run one on every commit and the other nightly).

### 3.3 Vulture — Dead Code Detection

**Recommendation:** **Add Vulture for dead code detection.**

**What it does:**
- Scans the codebase for unused functions, classes, methods, and variables
- Reports items that appear to have no references
- Produces a confidence-based report; items with low confidence can be reviewed manually

**Strengths:**
- Purpose-built for dead code detection
- Fast enough for CI integration
- Works on the AST, not runtime, so it catches dead code before it is deleted in a refactor

**Weaknesses (and mitigations):**
- **False positives from dynamic registry patterns** (see Section 5): Vulture cannot see imports that happen through `__init__.py` re-exports, decorator-based registration, or string-based dynamic lookup. Mitigation: use `--min-confidence` threshold and `# noqa: V101`-style suppression comments for known false positives.
- Cannot detect code that is dead in the current branch but will be used in another branch or by external consumers (library code). Mitigation: for library-facing APIs, mark as retained intentionally.

**CI integration pattern:**
- Run as a separate CI step, not as a blocker on every commit initially
- Triage the initial report, suppress intentional false positives, then consider making it blocking once the noise baseline is established
- Re-run on a schedule (similar to flake-detection) to catch dead code that accumulates

### 3.4 Import-Linters — Architecture Boundary Enforcement

**Recommendation:** **Evaluate import-linter (or similar) for declarative import rule enforcement.**

**Options:**

| Tool | Notes |
|---|---|
| `import-linter` | Most mature option; declarative contract files; checks all imports in one pass; can enforce layer/dependency rules |
| `importlib-metadata`-based custom check | Would require building from scratch; not recommended |
| Architecture tests (current approach) | Already in place; may be sufficient if coverage is complete |

**What import-linter provides:**
- Declarative contracts: "Layer A must not import from Layer B" expressed in a contract file
- Checks all imports statically in a single pass
- Can be integrated into CI as a lint step (faster feedback than architecture tests)
- Can complement or replace the current architecture test suite

**Justification for adding (rather than relying solely on current architecture tests):**
- Current architecture tests are Python-executed; they only check paths that are explicitly exercised by test code
- import-linter checks every import statically; no risk of missing a path because no test hits it
- Declarative contracts are easier to audit and reason about than test code that asserts import rules

**Caveat:** Before adding, audit the existing `tests/architecture/` suite to determine whether it already covers all intended rules. If it does, import-linter may be a refactor (same rules, different mechanism) rather than new coverage.

### 3.5 Semgrep — Custom Pattern Matching

**Recommendation:** **Add Semgrep for custom security and style patterns.**

**What it does:**
- Pattern-based static analysis using YAML rule files
- Can express custom patterns that Ruff, mypy, and pyright cannot (e.g., "any function call matching `eval(...)` where the argument is derived from a request parameter")
- Has a large rule registry (semgrep-rules) with community and maintained rules for security, style, and bug detection
- Fast; can run in CI as a lint step

**Use cases for this project:**

1. **Security patterns (high value):**
   - Detect `eval()`, `exec()`, `compile()` usage
   - Detect `pickle.loads()` or other unsafe deserialization
   - Detect hardcoded secrets (API keys, passwords) in source using regex patterns
   - Detect use of `subprocess` with `shell=True` and user-controllable input

2. **Project-specific conventions (medium value):**
   - "All FastAPI route handlers must specify `response_model`"
   - "No `print()` calls in non-test modules"
   - "Configuration access must go through the pydantic-settings wrapper, not `os.environ` directly"

3. **Existing rule sets to consider:**
   - `semgrep-rules/pythonlangsecurity` (security-focused rules for Python)
   - `semgrep-rules/pseudenger` (general Python bug patterns)
   - Custom project rules in `.semgrep/rules/`

**Noise management:** Start with a small set of high-signal rules. Add more gradually. Use Semgrep's severity levels (`info`, `warning`, `error`) to classify; only `error`-severity rules should block CI initially.

### 3.6 Bandit — Optional Light Security Scanning

**Recommendation:** **Optional. Consider if Semgrep's security coverage is insufficient.**

**What it does:**
- Security-focused static analyzer for Python
- Checks for common security issues: hardcoded passwords, use of `eval`, insecure cryptography, XSS patterns, etc.

**Relationship to Semgrep:**
- Semgrep is more flexible for custom patterns
- Bandit has a focused set of built-in security checks
- Running both is redundant for their overlapping coverage

**Recommendation:** If Semgrep is added with a meaningful security rule set, Bandit is likely redundant. Add Bandit only if:
- The team prefers Bandit's specific check set over Semgrep's, OR
- Semgrep is used for custom patterns and a lightweight, focused security scanner is still desired

**Classification if added:** Advisory initially; blocking only after baseline is established.

---

## 4. Blocking vs Advisory Classification

### 4.1 Decision Framework

| Classification | Meaning | When to use |
|---|---|---|
| **Blocking** | CI fails if the tool reports any finding | Tool has low noise, high signal, and findings represent genuine problems that should not be merged |
| **Advisory** | Findings are reported but do not fail CI | Tool has meaningful noise, findings require human judgment, or the tool is newly adopted and the baseline is being established |
| **Scheduled / Nightly** | Runs periodically (not on every PR) to detect accumulation | Tools that are noisy or whose findings are interesting but not gating (e.g., dead code detection that may have false positives) |

### 4.2 Classification Table

| Tool | Role | Initial classification | Target classification (post-baseline) |
|---|---|---|---|
| Ruff (existing `E,F,I,N,W,UP`) | Linting | **Blocking** | **Blocking** |
| Ruff (expanded rules) | Linting (expanded) | **Advisory** (per new rule batch) | **Blocking** (after per-rule triage) |
| mypy (strict) | Type checking | **Blocking** | **Blocking** |
| pyright (strict) | Type checking | **Blocking** | **Blocking** |
| Vulture | Dead code detection | **Advisory** (or scheduled) | **Advisory** (or blocking if confidence threshold tuned) |
| import-linter | Architecture boundaries | **Advisory** (initial audit) | **Blocking** (after contracts audited) |
| Semgrep (security) | Security patterns | **Advisory** | **Blocking** (high-severity rules only) |
| Semgrep (custom style) | Project conventions | **Advisory** | **Advisory** (or blocking for highest-signal rules) |
| Bandit (if added) | Security scanning | **Advisory** | **Advisory** or redundant with Semgrep |

### 4.3 Rationale for Advisory-First Approach

New static analysis tools almost always produce some false positives or findings that require human judgment on the first pass. An advisory classification allows:
1. The tool to run in CI and produce reports
2. The team to triage findings without blocking development
3. Suppression comments and configuration tuning to reduce noise
4. A deliberate transition to blocking once the noise baseline is acceptable

This is consistent with the project's existing flake-detection approach (scheduled, not blocking on every commit).

---

## 5. Handling False Positives from Dynamic Registry Patterns

### 5.1 The Problem

Python projects frequently use dynamic patterns that static analyzers cannot see:

| Pattern | Example | Why it fools static analyzers |
|---|---|---|
| `__init__.py` re-exports | `from .module import func; __all__ = ["func"]` | The function is referenced only through the string in `__all__`, not by a direct name reference in the AST |
| Decorator-based registration | `@registry.register`; the decorator adds the function to a dict by string key | No direct name reference exists in the codebase; the function is "called" only through dynamic lookup |
| String-based import or lookup | `importlib.import_module(module_name); getattr(module, func_name)` | The target is determined at runtime from a string; static analysis sees no reference |
| Plugin/entry-point systems | Functions registered via setuptools entry points or similar | References exist in configuration, not in code |
| FastAPI/Pydantic model usage | A Pydantic model is referenced only in a route handler's type annotation, or a dependency is injected by name | The model/dependency may appear unused if the analyzer does not understand the framework's dependency injection |
| Module-level `__all__` with dynamic construction | `__all__ = [name for name in dir() if not name.startswith("_")]` | Static analyzers cannot evaluate the list comprehension at analysis time |

### 5.2 Mitigation Strategies

**Strategy 1: Confidence thresholds (Vulture-specific)**

Vulture supports `--min-confidence` (default 80). Raising the threshold reduces false positives but may miss real dead code. Lowering it increases sensitivity but also noise. Start at the default, then adjust based on the triage results.

**Strategy 2: Suppression comments**

Each tool has its own suppression mechanism:
- Vulture: `# noqa: V101` (or equivalent; check current Vulture suppression syntax)
- Ruff: `# noqa: <rule-code>`
- Semgrep: `# semgrep-ignore` (inline) or exclude paths in configuration
- import-linter: Allowlists or exception rules in contract files

Suppression comments should be used sparingly and with an explanatory note when the reason is not obvious:

```python
# Vulture thinks this is dead, but it is registered via the decorator
# and called dynamically by the framework. Confirmed alive as of 2026-11-18.
# noqa: V101
def registered_handler(event):
    ...
```

**Strategy 3: Tool configuration (exclude paths, ignore files)**

- Exclude test directories, migration files, and generated code from dead code analysis
- Exclude `__init__.py` files from Vulture if they primarily contain re-exports (or configure Vulture to handle them correctly)
- Use tool-specific exclude configuration to reduce noise from paths that are known to use dynamic patterns

**Strategy 4: Central registry of known false positives**

Maintain a short document (or section in this document) listing:
- The file and symbol
- Why it is a false positive (which dynamic pattern is responsible)
- Who confirmed it and when

This serves as documentation for future developers who encounter the same finding and prevents re-triage of known false positives.

**Strategy 5: Framework-aware analysis where possible**

Some tools have plugins or configuration for specific frameworks. If Vulture or Semgrep has FastAPI or Pydantic-aware rules, prefer those over generic rules for framework-related code. This is an area to research during implementation.

### 5.3 Specific Considerations for This Codebase

Based on the project's dependencies (FastAPI, Pydantic, structlog, python-dotenv):

- **FastAPI route handlers** are registered by decorating functions. Vulture may report them as dead if no other code calls them directly. They are not dead — the framework calls them at runtime. These are expected false positives.
- **Pydantic models** referenced only in type annotations may appear unused to Vulture. They define data structures consumed by the framework and API consumers; they are not dead.
- **structlog configuration** and logger definitions may appear dead if they are only used through the logging framework's own machinery.
- **Dependency injection functions** (FastAPI `Depends()`) may appear unused if called only through the framework's injection machinery.

Expected action: When Vulture is first run, triage the report with the understanding that FastAPI/Pydantic-related items are likely false positives and should be suppressed with documentation.

---

## 6. Low-Noise Principle

### 6.1 Principle Statement

**Static analysis tooling should produce signals that are worth acting on.** Each new rule or tool should be evaluated against the question: "Does this finding represent a problem that we would want to fix, or is it noise that will be ignored?"

A tool or rule that produces a high ratio of noise to signal will be ignored, and the entire static analysis effort loses credibility.

### 6.2 Operational Guidelines

1. **Add rules in small batches.** Never add more than a handful of new rules in a single change. Run on the full codebase, count findings, triage, and then decide whether to make the rule blocking.

2. **Triage before blocking.** A new rule or tool should run as advisory for at least one full development cycle (or until the finding count is reasonable and the team has reviewed the output) before being promoted to blocking.

3. **Measure noise ratio.** Track:
   - Total findings per run
   - Findings that are acted upon (fixed, suppressed with justification, or confirmed as false positives)
   - Findings that are ignored (no action taken after review)
   
   If the "ignored" rate is high for a rule, either tune the rule, suppress it, or remove it.

4. **Suppress deliberately, not casually.** Every suppression comment should have a reason. Suppressions without reasons become "suppress everything" habits and degrade the tool's usefulness.

5. **Prefer precision over recall in blocking rules.** A blocking rule that fires on every PR for a low-signal issue creates friction and invites people to bypass it. A blocking rule that fires rarely but always on a genuine problem earns trust.

6. **Schedule noisy tools, don't block on them.** Tools like Vulture (dead code) and large-scale Semgrep rule sets may be better suited to scheduled runs (e.g., weekly or on merge to main) rather than as PR blockers.

7. **Review the toolset periodically.** Every tool in the stack should justify its continued presence. If a tool has produced no actionable findings in six months, question whether it should remain.

### 6.3 Target Noise Profile

| Tool | Acceptable finding rate (post-baseline) |
|---|---|
| Ruff (existing rules) | Near-zero — these are established and low-noise |
| Ruff (new rules) | 0–5 findings per rule after triage; fewer is better |
| mypy + pyright | Zero blocking findings on healthy code; findings should be addressed, not suppressed |
| Vulture | Depends on codebase size; target a manageable number of genuine dead code items per run |
| import-linter | Zero violations expected on healthy code (architecture rules should not be violated) |
| Semgrep (security) | Low; high-severity security findings should be rare and always actionable |
| Semgrep (custom style) | Low to moderate, depending on rule strictness |
| Bandit (if used) | Low; most findings should be actionable or easily suppressible |

---

## 7. Summary of Recommendations

| Area | Current state | Recommendation |
|---|---|---|
| **Linting** | Ruff with `E,F,I,N,W,UP` | Expand Ruff rules incrementally; start advisory, promote to blocking per rule |
| **Type checking** | mypy (strict) + pyright (strict) | Keep both; they are complementary and already blocking |
| **Dead code** | No detection | Add Vulture; start advisory/scheduled; suppress known dynamic-pattern false positives |
| **Architecture boundaries** | Architecture tests (pytest-based) | Evaluate import-linter; prefer declarative, static checking over test-based checking |
| **Security patterns** | No security scanner | Add Semgrep with a focused security rule set; advisory initially; blocking for high-severity rules after baseline |
| **Custom patterns** | No custom pattern tool | Use Semgrep for project-specific conventions (print bans, response model requirements, config access rules) |
| **Bandit** | Not installed | Optional; add only if Semgrep's security coverage is insufficient |

---

## 8. Open Questions for Implementation

1. **Ruff expansion:** Which specific additional Ruff rule codes should be enabled first? (Proposed list in Section 3.1; prioritize based on value and noise risk.)

2. **Vulture confidence threshold:** What minimum confidence level produces an acceptable signal-to-noise ratio on this codebase?

3. **import-linter vs. architecture tests:** Does the existing `tests/architecture/` suite cover all intended import rules? If so, is import-linter a replacement or a complement?

4. **Semgrep rule set:** Which specific Semgrep rules (built-in and custom) provide the highest signal for this project's risk profile?

5. **CI compute budget:** Does adding these tools fit within the existing CI timeout budget (5–10 minutes per job)? If not, which tools run on which schedule?

6. **Bandit or no Bandit:** After selecting Semgrep rules, is there meaningful security coverage gap that Bandit would fill?

---

*This document is a research artifact. It does not modify any configuration files or install any tools. Implementation of these recommendations is a separate follow-up effort.*
