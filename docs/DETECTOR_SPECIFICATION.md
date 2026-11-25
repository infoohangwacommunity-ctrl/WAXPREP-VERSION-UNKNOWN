# Living Specification — Universal Hardcoding Detection Rules

> This specification defines the enforceable architectural principles for the
> Universal Hardcoding Detection System (Stage 08). Each rule describes
> structural and behavioral anti-patterns, not individual words.

This document is the single source of truth for what the detector checks and why.

---

## Rule WHD-001: Fixed-String Comparisons Against Student Input

**Rule ID:** WHD-001

**Rule:** No unauthorized fixed-vocabulary decisions in student interpretation.

**Intent:** Prevent the tutor from using manually predetermined vocabulary to decide conversational behavior through direct string equality comparisons.

**Prohibited behavior:** Student-input-dependent decisions based on manually fixed words, phrases, or vocabulary mappings implemented as string equality comparisons (`==`, `!=`).

**Scope:** Protected tutor interpretation and response strategy modules (`waxprep.messaging`, `waxprep.context`, `waxprep.services`).

**Allowed exceptions:**
- Technical validation (checking command strings, API field values)
- Transport routing (message type discrimination)
- Security controls (authentication tokens, permissions)
- Approved non-conversational functionality

**Detection method:** AST analysis detecting `Compare` nodes with `Eq`/`NotEq` operators where the left operand resembles student input and the right operand is a string constant. Input detection is token-based, never substring-based: identifiers are split on snake_case/camelCase boundaries and whole tokens (`message`, `text`, `content`, `input`, `query`, `prompt`, `body`, `data`, `payload`, `msg`, `utterance`) are matched. Consequently `context` is not treated as `text` and `metadata` is not treated as `data`. Calls are treated as input only when the function name is an inbound reader (`get_message`, `read_message`, `receive_message`, or a whole `receive`/`read` token). Attribute access such as `self.message` and calls such as `process_message()` are not treated as input.

**Severity:** HIGH

**Enforcement:** CI quality gate — blocking in protected modules.

**Confidence threshold:** 0.85

**Tests:**
- `tests/detector/test_detector.py::TestWHD001FixedStringComparison`
- `tests/detector/test_adversarial.py::TestAdversarialAlternateSyntax::test_ternary_instead_of_if`
- `tests/detector/test_adversarial.py::TestAdversarialHelperIndirection::test_helper_function_with_comparison`

**Status:** Enforced

**Known limitations:**
- Does not detect comparisons via helper functions without explicit AST tracing
- Input identification is still a name heuristic; values reached through containers, parameters with unrelated names, or function returns other than the known readers are not recognised
- Does not detect reverse comparisons (`"string" == input`) — only `input == "string"` direction
- Does not detect comparisons where input is transformed before comparison
- Does not detect comparisons using variables instead of literals (requires data-flow analysis)

---

## Rule WHD-002: Fixed Vocabulary Membership Tests

**Rule ID:** WHD-002

**Rule:** No membership tests against hardcoded vocabularies in student interpretation.

**Intent:** Prevent checking student input against predefined lists, sets, or tuples of terms to drive behavior.

**Prohibited behavior:** Using `in` or `not in` operators to check student input against literal collections of strings in protected modules.

**Scope:** Protected modules (`waxprep.messaging`, `waxprep.context`, `waxprep.services`).

**Allowed exceptions:**
- Technical validation lists (allowed file types, supported commands)
- Configuration validation
- Protocol/format constants

**Detection method:** AST analysis detecting `Compare` nodes with `In`/`NotIn` operators where the left operand resembles input (same token-based heuristic as WHD-001) and the right operand is a literal `List`/`Set`/`Tuple` containing strings, or a name assigned such a collection in the same file.

**Severity:** HIGH

**Enforcement:** CI quality gate — blocking in protected modules.

**Confidence threshold:** 0.80

**Tests:**
- `tests/detector/test_detector.py::TestWHD002MembershipTest`
- `tests/detector/test_adversarial.py::TestMutationDetection::test_mutation_string_to_list_comparison`

**Status:** Enforced

**Known limitations:**
- Does not trace collections imported from other modules
- Does not track reassignment or mutation of a named collection (requires data-flow analysis)
- Does not detect reverse membership (`"hello" in message`)

---

## Rule WHD-003: Fixed Decision Trees (If/Elif Chains)

**Rule ID:** WHD-003

**Rule:** No fixed decision trees based on string comparisons in student interpretation.

**Intent:** Prevent hardcoded branching logic that routes student messages based on predetermined conditions.

**Prohibited behavior:** `if/elif` chains with 3+ branches containing 2+ string comparisons in protected modules.

**Scope:** Protected modules.

**Allowed exceptions:**
- Technical branching (error handling, status code routing)
- Configuration-based decisions
- Protocol/format dispatch

**Detection method:** AST analysis counting string comparisons across `if/elif` chains and flagging chains exceeding thresholds.

**Severity:** MEDIUM

**Enforcement:** CI quality gate — review required; never blocks a merge (`blocks_merge=false`, `requires_review=true`).

**Confidence threshold:** 0.70

**Tests:**
- `tests/detector/test_detector.py::TestWHD003IfElifChain`
- `tests/detector/test_adversarial.py::TestMutationDetection::test_mutation_single_to_chain`

**Status:** Enforced (medium severity)

**Known limitations:**
- Threshold-based detection may miss shorter but significant chains
- A chain longer than three branches can be reported more than once (the outer chain and a trailing sub-chain)
- Does not detect nested if/else as chains (only flat elif structures)
- Does not detect match/case statements; `tests/detector/test_adversarial.py::test_match_statement` is a strict xfail so this gap cannot silently disappear

---

## Rule WHD-004: Regex-Based Pattern Matching

**Rule ID:** WHD-004

**Rule:** No regex patterns designed to detect phrases for conversational routing.

**Intent:** Prevent hidden phrase detection using regular expressions that could activate predetermined behaviors.

**Prohibited behavior:** Using `re.match`, `re.search`, `re.findall`, etc. with patterns containing word boundaries in protected modules.

**Scope:** Protected modules.

**Allowed exceptions:**
- Input validation (email format, phone numbers, IDs)
- Security pattern matching
- Data extraction for technical purposes

**Detection method:** AST analysis detecting calls to `re` module functions (`match`, `search`, `findall`, `fullmatch`, `finditer`) with patterns containing a word-boundary escape. In Python source a raw literal `r"\bword\b"` contains a backslash followed by the letter `b`; the detector checks for that sequence (not the backspace character). Patterns assigned to a variable in the same file are resolved and inspected at the call site. A pattern is suspicious when it contains a word boundary or is longer than 10 characters.

**Severity:** MEDIUM

**Enforcement:** CI quality gate — review required, not automatically blocking.

**Confidence threshold:** 0.65

**Tests:**
- `tests/detector/test_detector.py::TestWHD004RegexMatching`

**Status:** Enforced (medium severity, advisory blocking)

**Known limitations:**
- Long technical validation patterns (>10 characters) are also reported, because intent cannot be inferred statically
- Cannot determine if regex is used for legitimate validation vs. phrase detection
- Pattern intent requires human review
- Patterns built dynamically (concatenation, f-strings) or imported from other modules are not resolved

---

## Rule WHD-005: Word-to-Action Dictionary Lookups

**Rule ID:** WHD-005

**Rule:** No string-keyed dictionary lookups that map terms to actions in student interpretation.

**Intent:** Prevent indirect mappings that connect text inputs to system actions through dictionary subscript operations.

**Prohibited behavior:** Using dictionary subscript (`dict[key]`) with string keys where the dictionary variable name suggests a mapping in protected modules.

**Scope:** Protected modules.

**Allowed exceptions:**
- Lookup tables for technical codes (status codes, error codes)
- Configuration value lookups
- Protocol/format mapping tables

**Detection method:** AST analysis detecting `Subscript` nodes in a load context where the value is a `Name` and the slice is a string constant. Writes such as `mapping["key"] = value` are not lookups and are not reported.

**Severity:** MEDIUM

**Enforcement:** CI quality gate — review required in protected modules; never blocks a merge (`blocks_merge=false`, `requires_review=true`).

**Confidence threshold:** 0.60

**Tests:**
- `tests/detector/test_detector.py::TestWHD005DictionaryLookup`

**Status:** Enforced (medium severity)

**Known limitations:**
- Variable name heuristic is conservative — no metavariable-regex filtering on variable names
- Does not trace imported dictionaries or data-file-loaded mappings
- Does not detect `.get()` calls with variable keys
- Does not detect dictionary lookups outside function context

---

## Rule WHD-006: Deeply Nested Conditional Structures

**Rule ID:** WHD-006

**Rule:** No deeply nested conditional structures suggesting hidden routing in student interpretation.

**Intent:** Identify complex hidden routing logic that may be difficult to review and maintain.

**Prohibited behavior:** Nested `if` statements with 3+ levels of nesting in protected modules.

**Scope:** Protected modules.

**Allowed exceptions:**
- Complex validation logic
- Error handling chains
- Technical branching

**Detection method:** AST analysis calculating nesting depth of `If` nodes. The outermost `if` counts as level 1, so three nested `if` statements are reported as three levels of nesting.

**Severity:** LOW

**Enforcement:** Informational — does not block merge; flags for review.

**Confidence threshold:** 0.50

**Tests:**
- Covered by edge case tests in `tests/detector/test_detector.py`

**Status:** Advisory

**Known limitations:**
- Nesting depth alone is not indicative of prohibited behavior
- Many legitimate patterns require nesting
- Does not distinguish between technical and conversational nesting

---

## Rule WHD-007: Predetermined String Responses

**Rule ID:** WHD-007

**Rule:** No functions returning predetermined string responses in student interpretation.

**Intent:** Prevent hardcoded response generation that bypasses contextual intelligence.

**Prohibited behavior:** Functions whose names suggest response generation (`response`, `reply`, `greeting`, `answer`, `message`, `output`, `say`, `speak`) and that return string literals in protected modules.

**Scope:** Protected modules.

**Allowed exceptions:**
- Technical error messages
- Format strings for logging
- Static UI text
- Health check responses
- Utility functions that transform input (e.g., `normalize_text`)

**Detection method:** AST analysis identifying response-named functions that contain `Return` statements with string constants, lists of strings, or tuples of strings.

**Severity:** MEDIUM

**Enforcement:** CI quality gate — review required in protected modules; never blocks a merge (`blocks_merge=false`, `requires_review=true`).

**Confidence threshold:** 0.65

**Tests:**
- `tests/detector/test_detector.py::TestWHD007LiteralResponse`
- `tests/detector/test_adversarial.py::TestFalsePositivePrevention::test_legitimate_error_messages`

**Status:** Enforced (medium severity)

**Known limitations:**
- Does not use function name heuristic (removed metavariable-regex on function names)
- Does not detect responses built from multiple parts
- May flag legitimate utility functions if they don't match the exclusion pattern

---

## Rule WHD-008: Hardcoded Vocabularies

**Rule ID:** WHD-008

**Rule:** No hardcoded vocabularies used for classification or decision-making in student interpretation.

**Intent:** Prevent predefined term collections that could drive student classification or behavior routing.

**Prohibited behavior:** Variable assignments of lists/sets/tuples containing 2+ string literals in protected modules, where the variable name contains a vocabulary indicator (`words`, `phrases`, `vocabulary`, `terms`, `keywords`, `topics`, `subjects`, `greetings`, `responses`, `replies`, `messages`, `inputs`).

**Scope:** Protected modules.

**Allowed exceptions:**
- Technical term lists (supported platforms, API endpoints)
- Error message collections
- Format strings for technical purposes
- Module exports (`__all__`)

**Detection method:** AST analysis of assignments where the target name contains a vocabulary indicator and the value is a list/set/tuple of strings (nested collections are flattened). Module exports such as `__all__` do not match the indicator set.

**Severity:** MEDIUM

**Enforcement:** CI quality gate — review required in protected modules; never blocks a merge (`blocks_merge=false`, `requires_review=true`).

**Confidence threshold:** 0.55

**Tests:**
- `tests/detector/test_detector.py::TestWHD008HardcodedVocabulary`
- `tests/detector/test_adversarial.py::TestAdversarialVocabularyReplacement::test_synonym_vocabulary`

**Status:** Enforced (medium severity)

**Known limitations:**
- Does not use variable name heuristic (removed metavariable-regex on variable names)
- Does not detect vocabularies loaded from data files
- May flag technical constant lists
- Does not detect set or tuple vocabularies

---

## Rule WHD-009: JSON String-to-String Mappings

**Rule ID:** WHD-009

**Rule:** No JSON files containing string-to-string mappings that may function as behavioral engines.

**Intent:** Detect data files that have become hidden behavioral control systems.

**Prohibited behavior:** JSON files with 3+ string key-value pairs where both key and value are strings, potentially representing phrase-to-action mappings.

**Scope:** Data files inside the configured scan scope (default: `src/`, `docs/`, `README.md`, `tests/README.md`, `pyproject.toml`).

**Allowed exceptions:**
- Configuration files with legitimate string mappings
- Localization/i18n files
- Documentation data

**Detection method:** Recursive JSON analysis counting string-to-string mappings.

**Severity:** MEDIUM

**Enforcement:** CI quality gate — review required, not automatically blocking.

**Confidence threshold:** 0.60

**Tests:**
- `tests/detector/test_detector.py::TestDataFileInspector::test_inspects_json_vocabulary`

**Status:** Advisory

**Known limitations:**
- Cannot determine intent of mappings without context
- Legitimate configuration may trigger findings

---

## Rule WHD-010: Vocabulary Lists in Data Files

**Rule ID:** WHD-010

**Rule:** No data files containing large vocabulary lists without clear non-conversational purpose.

**Intent:** Identify data files that may be importing vocabulary for behavioral use.

**Prohibited behavior:** JSON, YAML, TOML, or CSV files containing 5+ string terms that appear to be vocabulary (alphabetic words > 3 characters).

**Scope:** Data files inside the configured scan scope (default: `src/`, `docs/`, `README.md`, `tests/README.md`, `pyproject.toml`).

**Allowed exceptions:**
- Documentation glossaries
- Technical reference lists
- Localization data
- Educational content (legitimate learning material)

**Detection method:** File-type-specific analysis detecting collections of string terms. JSON uses recursive parsing; TOML uses a real TOML parser and reports one array of five or more natural-language terms; YAML uses deliberately conservative line-based parsing (one contiguous list run at one indentation level). Lists of code identifiers (for example `ignore_names = ["register_defaults", "get_app"]`) are configuration, not vocabulary.

**Severity:** LOW

**Enforcement:** Informational — flags for review.

**Confidence threshold:** 0.40-0.50

**Tests:**
- `tests/detector/test_detector.py::TestDataFileInspector::test_inspects_yaml_vocabulary`

**Status:** Advisory

**Known limitations:**
- Educational content is legitimate and should not be flagged
- Context is required to determine purpose
- Complex nested YAML structures require full YAML parsing

---

## Rule WHD-011: Response Templates in Markdown

**Rule ID:** WHD-011

**Rule:** No Markdown files containing predetermined response templates.

**Intent:** Detect documentation that may be functioning as response generation logic.

**Prohibited behavior:** Markdown files containing patterns like "if student says X, respond with Y" or explicit response templates.

**Scope:** Markdown files inside the configured scan scope (default includes `docs/`, `README.md` and `tests/README.md`).

**Allowed exceptions:**
- Design documentation describing intended behavior
- User-facing documentation examples
- Architecture decision records

**Detection method:** Regex pattern matching in Markdown content for response template patterns.

**Severity:** LOW

**Enforcement:** Informational — flags for review.

**Confidence threshold:** 0.40

**Tests:**
- Covered by data file inspector tests

**Status:** Advisory

**Known limitations:**
- Documentation often describes behavior without implementing it
- High false positive rate without context

---

## Summary

| Rule ID | Severity | Blocks Merge | Requires Review | Scope | Detection Method |
|---------|----------|--------------|-----------------|-------|------------------|
| WHD-001 | HIGH | Yes (protected) | — | Protected modules | AST Compare nodes with token-based input heuristic |
| WHD-002 | HIGH | Yes (protected) | — | Protected modules | AST Compare + In/NotIn (list/set/tuple) |
| WHD-003 | MEDIUM | No | Yes | Protected modules | AST If/elif chains |
| WHD-004 | MEDIUM | No | Yes | Protected modules | AST re calls with `\b` word boundaries |
| WHD-005 | MEDIUM | No | Yes | Protected modules | AST Subscript reads |
| WHD-006 | LOW | No | No | Protected modules | AST nesting depth |
| WHD-007 | MEDIUM | No | Yes | Protected modules | AST response functions + Return |
| WHD-008 | MEDIUM | No | Yes | Protected modules | AST vocabulary assignment |
| WHD-009 | MEDIUM | No | Yes | Data files | JSON/YAML mapping analysis |
| WHD-010 | LOW | No | No | Data files | File-type vocabulary analysis |
| WHD-011 | LOW | No | No | Markdown files | Regex pattern matching |

Only WHD-001 and WHD-002 can block a merge, and only inside protected
modules. Every other rule produces review or informational findings.

---

## Scan scope, completeness and enforcement

### Explicit scope

Scanning is never project-wide by accident. The CLI and quality-gate entry
point share `DEFAULT_SCAN_TARGETS`:

- Python source scanning: `src/`
- Active documentation: `docs/`
- Project documents: `README.md`, `tests/README.md`
- Project configuration: `pyproject.toml`

Callers can pass explicit files or directories as positional targets. Test
fixtures and dependency trees (`tests/`, `.venv/`, `node_modules/`, caches,
build output) are never part of the default scope, so examples and generated
content cannot create misleading findings.

### Completeness is reported

A file that cannot be read, parsed, or decoded is recorded as a **scan
problem** (for example `syntax-error`, `invalid-json`, `invalid-toml`,
`unreadable`). Scan problems are printed, counted in the JSON report, and
fail the gate (exit code 1) because an incomplete scan cannot certify the
codebase. `"no findings"` therefore never means "not inspected".

### One enforcement policy

The CLI and the quality-gate module both call `waxprep.detector.analyze()`.
Blocking status comes from `Finding.blocks_merge`, and report counts use the
same property, so `get_report()["blocking_findings"]`, the printed summary
and the exit code cannot disagree. Severity, review status and merge-blocking
status are separate fields.

---

## Architectural Boundaries Reference

**Protected modules** (hardcoded conversational behavior prohibited):
- `waxprep.messaging` — Message handling & conversation flow
- `waxprep.context` — Understanding the learner
- `waxprep.services` — Light orchestration

**Allowed modules** (fixed values are legitimate):
- `waxprep.core` — Pure logic & protocols
- `waxprep.config` — Settings
- `waxprep.id` — Identity generation
- `waxprep.registries` — Registry implementations
- `waxprep.adapters` — Adapter implementations
- `waxprep.middleware` — Middleware
- `waxprep.main` — ASGI application entry point

---

## Detection Architecture

### Two-Layer Detection System

1. **Python AST Detector** (`src/waxprep/detector/__init__.py`)
   - Primary enforcement mechanism
   - 11 detection rules (WHD-001 through WHD-011)
   - Operates on Python source files
   - Data file inspector for JSON, YAML, TOML, CSV, Markdown

2. **Semgrep Configuration** (`.semgrep/config.yml`)
   - Supplementary structural pattern matching
   - 7 rules (WHD-001 through WHD-005, WHD-007, WHD-008)
   - WHD-006, WHD-009, WHD-010, WHD-011 are NOT in Semgrep (only in AST detector)
   - Excludes detector directory (`src/waxprep/detector/`) from scanning

### Test Organization

- `tests/detector/test_detector.py` — Unit tests for each WHD rule
- `tests/detector/test_adversarial.py` — Adversarial and mutation tests
- `tests/detector/test_cli_and_quality_gate.py` — CLI and integration tests
- `tests/detector/test_coverage_gaps.py` — Coverage gap analysis
- `tests/detector/test_property.py` — Property-based tests

### Known Cross-File Detection Gaps

The following patterns require data-flow analysis beyond current AST capabilities:

- Imported vocabulary from other modules
- Vocabulary stored in configuration files
- Comparisons through helper function chains
- Variable-based comparisons (literal assigned to variable, then used)
- Dynamic string construction (concatenation, formatting)
- Variable indirection (aliases)

These are documented as `xfail` tests in `test_adversarial.py`.

---

## Enforcement Status

| Component | Status |
|-----------|--------|
| CLI (`src/waxprep/detector/cli.py`) | Functional — explicit targets, default project scope, `--format` |
| Quality gate (`src/waxprep/detector/quality_gate.py`) | Functional — calls the same `analyze()` policy as the CLI |
| CI Integration | Functional — runs in Quality Gate workflow over the default scope |
| Blocking Exit Code | Functional — 1 for blocking findings or an incomplete scan |
| Scan completeness | Functional — read/parse failures are reported, never silently ignored |
| Semgrep Config | Valid — 7 rules load and execute |
| Python Detector | Valid syntax — exception handling and TOML parsing verified |
