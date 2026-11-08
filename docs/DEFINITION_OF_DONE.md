# Definition of Done - Stage 04

This document defines what it means for a component to be "done" in the WaxPrep project.
A component is not "done" because it has been written. It is done when **all** of the following
criteria are met and evidence is provided.

---

## Component Acceptance Criteria

### 1. Port Implementation
- [ ] It implements an **existing port** defined in `application/ports/`
- [ ] The port interface is clearly documented with docstrings
- [ ] The implementation satisfies all methods in the port protocol

### 2. Package Location
- [ ] It lives in the correct package:
  - Domain models: `domain/`
  - Port interfaces: `application/ports/`
  - Port implementations (adapters): `adapters/`
  - Infrastructure: `infrastructure/`
- [ ] It does NOT live in a shared `utils/` or `common/` package without a named owner

### 3. Registration
- [ ] It is registered through the registry pattern
- [ ] Registration happens at startup, not at import time (no side effects)
- [ ] It declares its capabilities through the port's `get_capabilities()` method

### 4. Testing
- [ ] It has a **unit test** that tests the component in isolation
- [ ] It has a **contract test** that runs against the port interface
- [ ] All tests pass in random order (pytest-randomly)
- [ ] All tests pass under parallel execution (pytest-xdist)

### 5. Code Quality
- [ ] It passes `python scripts/lint_imports.py` (import-linter contracts)
- [ ] It passes `ruff check` with the full rule set (E, F, W, I, N, UP, S, B, A, C4, SIM, TCH, RUF)
- [ ] It passes `ruff format --check`
- [ ] It passes `pyright` in strict mode

### 6. Documentation
- [ ] It has a docstring on every public function, class, and module
- [ ] The docstring states the **contract** (what it guarantees), not a line-by-line description
- [ ] If the decision was non-obvious, there is an ADR documenting it

### 7. Configuration
- [ ] It adds **no hardcoded values** to `src/`
- [ ] All configuration is loaded from environment variables via `Settings`
- [ ] Secrets, behavior, and student data stay in their correct categories

### 8. Error Handling
- [ ] It follows the error handling convention:
  - Expected failures (network issues, rate limits, validation) use `Result` types
  - Programming errors (bugs, invariants) raise typed exceptions
- [ ] No bare `except:` clauses
- [ ] No `except Exception: pass` without handling or logging
- [ ] Domain errors are a typed hierarchy, not string literals

### 9. Independent Verification
- [ ] The implementing agent or engineer does NOT approve their own claim
- [ ] Independent verification by a human or a separate agent is required
- [ ] All acceptance criteria above must be demonstrated with evidence

---

## Evidence Required

To claim a component is "done", you must provide evidence for each criterion:

1. **Port Implementation**: Link to the port interface and implementation
2. **Package Location**: Show the file path
3. **Registration**: Show the registry registration code
4. **Testing**: Link to test files and CI results
5. **Code Quality**: Show CI logs for lint-imports, ruff, pyright
6. **Documentation**: Link to docstrings and ADRs
7. **Configuration**: Show that no hardcoded values exist
8. **Error Handling**: Show error handling code
9. **Independent Verification**: Name of the verifier and verification method

---

## Checklist Template

When submitting a component for review, include this checklist:

```markdown
## Definition of Done Checklist

- [ ] Implements existing port from `application/ports/`
- [ ] Located in correct package (domain/adapters/infrastructure)
- [ ] Registered through registry pattern
- [ ] Unit tests pass
- [ ] Contract tests pass
- [ ] Random order tests pass
- [ ] Parallel tests pass
- [ ] lint-imports passes
- [ ] ruff check passes
- [ ] ruff format --check passes
- [ ] pyright strict passes
- [ ] Docstrings present
- [ ] No hardcoded values
- [ ] Error handling follows convention
- [ ] Independent verification obtained
```

---

## Notes

- This Definition of Done applies to **all** components added after Stage 03
- Existing components (from Stages 01-02) should be updated to meet these criteria
- The Definition of Done may evolve, but changes require an ADR
- If a criterion doesn't apply to a specific component, document why
