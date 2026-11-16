# Test Plan: Stage 03 - Structural Boundaries

**Version:** 0.3.0  
**Current Test Status:** 42 passing tests  

---

## Executive Summary

Stage 03 adds four new directories (`core/`, `messaging/`, `context/`, `services/`) that enforce architectural boundaries. The test strategy should:

1. **Verify existing tests continue to pass** (regression protection)
2. **Add boundary rule tests** to enforce dependency direction
3. **Test placeholder modules lightly** to validate structure, not features
4. **Skip empty-directory tests** — they add no value

---

## 1. Existing Tests: Will They Pass?

### Assessment: YES — with one caveat

| Test File | Risk Level | Reason |
|-----------|------------|--------|
| `tests/test_config.py` | ✅ None | Config is unchanged |
| `tests/test_registries.py` | ✅ None | Registries unchanged |
| `tests/test_foundation.py` | ✅ None | App/health/middleware unchanged |
| `tests/test_main.py` | ⚠️ Minor | Root endpoint message may need update if it references stages |

### Required Updates

The root endpoint currently returns:
```python
{"message": "WaxPrep Foundation - Stages 01-02 ONLY", "stages": ["01", "02"]}
```

If Stage 03 is complete, this should be updated to reflect the new stage:
```python
{"message": "WaxPrep Foundation - Stages 01-03", "stages": ["01", "02", "03"]}
```

**Action:** Update `src/waxprep/main.py` to reflect Stage 03 completion, then update `tests/test_main.py` accordingly.

---

## 2. New Structure Tests: Empty Directories?

### Decision: NO — Do NOT test for empty directories

**Rationale:**
- Empty directories have no behavior to test
- Directory existence is a filesystem concern, not a code concern
- CI/build systems already verify the project structure compiles
- Adding tests for `os.path.isdir("src/waxprep/core")` adds maintenance burden with zero value

**Exception:** If a directory is *supposed* to be empty but shouldn't be, that's a code review concern, not a test concern.

---

## 3. Boundary Rule Tests: YES — Critical Addition

The architectural boundaries are the primary value of Stage 03. Tests should enforce:

### 3.1 Core Layer Boundary Tests

**File:** `tests/test_architectural_boundaries.py` (new)

```python
"""
Test Architectural Boundaries - Stage 03
Prove dependency direction is enforced: outer → inner only.
"""

import ast
import pytest
from pathlib import Path


class TestCoreLayerBoundaries:
    """Prove core/ imports nothing external."""
    
    CORE_PATH = Path("src/waxprep/core")
    
    @pytest.mark.skipif(
        not CORE_PATH.exists(),
        reason="core/ directory does not exist yet"
    )
    def test_core_does_not_import_adapters(self):
        """Core must not import from waxprep.adapters."""
        for py_file in self.CORE_PATH.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("waxprep.adapters"), \
                            f"Core imports adapters: {py_file}:{node.lineno}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.adapters"):
                        pytest.fail(f"Core imports from adapters: {py_file}:{node.lineno}")
    
    @pytest.mark.skipif(
        not CORE_PATH.exists(),
        reason="core/ directory does not exist yet"
    )
    def test_core_does_not_import_fastapi(self):
        """Core must not import FastAPI or any web framework."""
        for py_file in self.CORE_PATH.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name != "fastapi", \
                            f"Core imports FastAPI: {py_file}:{node.lineno}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module and ("fastapi" in node.module or "starlette" in node.module):
                        pytest.fail(f"Core imports web framework: {py_file}:{node.lineno}")
    
    @pytest.mark.skipif(
        not CORE_PATH.exists(),
        reason="core/ directory does not exist yet"
    )
    def test_core_does_not_import_external_sdks(self):
        """Core must not import external SDKs (openai, whatsapp, etc.)."""
        forbiddden_imports = ["openai", "whatsapp_business_sdk", "telegram", "twilio"]
        for py_file in self.CORE_PATH.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert alias.name not in forbiddden_imports, \
                            f"Core imports external SDK: {alias.name} in {py_file}:{node.lineno}"
```

### 3.2 Context Layer Boundary Tests

```python
class TestContextLayerBoundaries:
    """Prove context/ imports only from core/."""
    
    CONTEXT_PATH = Path("src/waxprep/context")
    
    @pytest.mark.skipif(
        not CONTEXT_PATH.exists(),
        reason="context/ directory does not exist yet"
    )
    def test_context_does_not_import_messaging(self):
        """Context must not import from waxprep.messaging."""
        for py_file in self.CONTEXT_PATH.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.messaging"):
                        pytest.fail(f"Context imports messaging: {py_file}:{node.lineno}")
    
    @pytest.mark.skipif(
        not CONTEXT_PATH.exists(),
        reason="context/ directory does not exist yet"
    )
    def test_context_does_not_import_services(self):
        """Context must not import from waxprep.services."""
        for py_file in self.CONTEXT_PATH.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.services"):
                        pytest.fail(f"Context imports services: {py_file}:{node.lineno}")
    
    @pytest.mark.skipif(
        not CONTEXT_PATH.exists(),
        reason="context/ directory does not exist yet"
    )
    def test_context_does_not_import_adapters(self):
        """Context must not import from waxprep.adapters."""
        for py_file in self.CONTEXT_PATH.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.adapters"):
                        pytest.fail(f"Context imports adapters: {py_file}:{node.lineno}")
```

### 3.3 Messaging Layer Boundary Tests

```python
class TestMessagingLayerBoundaries:
    """Prove messaging/ imports only from core/ and context/."""
    
    MESSAGING_PATH = Path("src/waxprep/messaging")
    
    @pytest.mark.skipif(
        not MESSAGING_PATH.exists(),
        reason="messaging/ directory does not exist yet"
    )
    def test_messaging_does_not_import_services(self):
        """Messaging must not import from waxprep.services."""
        for py_file in self.MESSAGING_PATH.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.services"):
                        pytest.fail(f"Messaging imports services: {py_file}:{node.lineno}")
    
    @pytest.mark.skipif(
        not MESSAGING_PATH.exists(),
        reason="messaging/ directory does not exist yet"
    )
    def test_messaging_does_not_import_adapters_directly(self):
        """Messaging must not import concrete adapters directly (use registries)."""
        for py_file in self.MESSAGING_PATH.rglob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.adapters"):
                        pytest.fail(
                            f"Messaging imports adapters directly: {py_file}:{node.lineno}. "
                            f"Use registries instead."
                        )
```

### 3.4 Services Layer: The Exception

Services/ is allowed to import from anywhere — it's the composition root. No boundary tests needed for services/.

---

## 4. Placeholder Module Tests: Light Touch

### 4.1 Core Protocols Tests

**File:** `tests/test_core_protocols.py` (new)

The protocols defined in `core/protocols.py` should have basic satisfaction tests:

```python
"""
Test Core Protocols - Stage 03
Prove protocols are properly defined and can be satisfied.
"""

import pytest
from waxprep.core.protocols import Message, MessageHandler, ContextProvider


class TestMessageProtocol:
    """Prove Message protocol is correctly defined."""
    
    def test_message_protocol_has_required_methods(self):
        """Message protocol must define get_content, get_metadata, get_id."""
        assert hasattr(Message, 'get_content')
        assert hasattr(Message, 'get_metadata')
        assert hasattr(Message, 'get_id')
    
    def test_message_protocol_is_runtime_checkable(self):
        """Message should be usable with isinstance checks."""
        # Create a simple class that satisfies the protocol
        class TestMessage:
            def get_content(self) -> str:
                return "test"
            def get_metadata(self) -> dict:
                return {}
            def get_id(self) -> str:
                return "test-id"
        
        msg = TestMessage()
        assert isinstance(msg, Message)


class TestMessageHandlerProtocol:
    """Prove MessageHandler protocol is correctly defined."""
    
    def test_handler_protocol_has_required_methods(self):
        """Handler must define can_handle and handle."""
        assert hasattr(MessageHandler, 'can_handle')
        assert hasattr(MessageHandler, 'handle')


class TestContextProviderProtocol:
    """Prove ContextProvider protocol is correctly defined."""
    
    def test_provider_protocol_has_required_method(self):
        """Provider must define get_context."""
        assert hasattr(ContextProvider, 'get_context')
```

### 4.2 Core Pure Functions Tests

**File:** `tests/test_core_pure.py` (new)

```python
"""
Test Core Pure Functions - Stage 03
Prove pure functions work correctly with no side effects.
"""

import pytest
from waxprep.core.pure import normalize_text, extract_keywords, build_response, compose_handlers


class TestNormalizeText:
    """Prove normalize_text is pure and correct."""
    
    def test_normalizes_whitespace(self):
        assert normalize_text("  hello   world  ") == "hello world"
    
    def test_handles_empty_string(self):
        assert normalize_text("") == ""
    
    def test_handles_none(self):
        assert normalize_text(None) == ""
    
    def test_is_pure_function(self):
        """Same input always produces same output."""
        text = "  hello   world  "
        assert normalize_text(text) == normalize_text(text)


class TestExtractKeywords:
    """Prove extract_keywords is pure and correct."""
    
    def test_extracts_words(self):
        keywords = extract_keywords("hello world python programming")
        assert "hello" in keywords
        assert "world" in keywords
        assert "python" in keywords
    
    def test_filters_by_min_length(self):
        keywords = extract_keywords("hi hello", min_length=3)
        assert "hi" not in keywords
        assert "hello" in keywords
    
    def test_returns_sorted_unique(self):
        keywords = extract_keywords("banana apple banana")
        assert keywords == ["apple", "banana"]


class TestBuildResponse:
    """Prove build_response creates proper response structure."""
    
    def test_basic_response(self):
        response = build_response("hello")
        assert response["content"] == "hello"
        assert "metadata" not in response
    
    def test_response_with_metadata(self):
        response = build_response("hello", {"key": "value"})
        assert response["content"] == "hello"
        assert response["metadata"] == {"key": "value"}


class TestComposeHandlers:
    """Prove handler composition works."""
    
    def test_composes_two_handlers(self):
        add_one = lambda x: x + 1
        double = lambda x: x * 2
        
        pipeline = compose_handlers([add_one, double])
        assert pipeline(3) == 8  # (3 + 1) * 2
```

### 4.3 Context Placeholder Tests (When Implemented)

When `context/` has actual code, add minimal tests:

```python
# tests/test_context.py (future)
from waxprep.context.profile import LearnerProfile

def test_learner_profile_initial_state():
    profile = LearnerProfile(learner_id="test-123")
    assert profile.learner_id == "test-123"
    assert profile.interaction_count == 0
```

---

## 5. Test Count Projection

| Test File | Stage 02 | Stage 03 Additions | Stage 03 Total |
|-----------|----------|-------------------|----------------|
| `test_config.py` | 5 | 0 | 5 |
| `test_registries.py` | 11 | 0 | 11 |
| `test_foundation.py` | 11 | 0 | 11 |
| `test_main.py` | 2 | 0 | 2 |
| `test_architectural_boundaries.py` | 0 | 6-9 | 6-9 |
| `test_core_protocols.py` | 0 | 5 | 5 |
| `test_core_pure.py` | 0 | 9 | 9 |
| **Total** | **29** | **20-23** | **49-52** |

*Note: The brief mentions 42 passing tests. The discrepancy may be due to additional tests in the `everything-claude-code/` tree or newer additions. Run `pytest --collect-only` to verify the exact count.*

---

## 6. Execution Order

Tests should run in this order to catch boundary violations early:

1. **Architectural boundary tests** — Fail fast if structure is wrong
2. **Core pure function tests** — Validate core logic
3. **Core protocol tests** — Validate protocol definitions
4. **Existing registry/config/foundation tests** — Regression check
5. **Main/app tests** — Integration check

---

## 7. CI Integration

Add to CI pipeline:

```yaml
# Example GitHub Actions step
- name: Run Stage 03 boundary tests
  run: |
    uv run pytest tests/test_architectural_boundaries.py -v
    uv run pytest tests/test_core_protocols.py -v
    uv run pytest tests/test_core_pure.py -v
```

The boundary tests should be **blocking** — a failure means the architecture is compromised.

---

## 8. What NOT to Test

| Thing | Reason |
|-------|--------|
| Empty directory existence | No behavior to verify |
| `__init__.py` files that only re-export | Import behavior is tested implicitly |
| Placeholder classes with no logic | No behavior yet |
| Import success (module can be imported) | Covered by boundary tests |
| Services layer boundaries | Services is the composition root; it imports everything by design |

---

## 9. Summary

### Must Have (blocking)

1. ✅ Update root endpoint message for Stage 03
2. ✅ Add `test_architectural_boundaries.py` with core/ context/ messaging/ boundary checks
3. ✅ Add `test_core_pure.py` for pure function validation
4. ✅ Add `test_core_protocols.py` for protocol validation

### Nice to Have (optional)

1. 📝 Add context/ tests when actual code is implemented
2. 📝 Add messaging/ handler tests when handlers are implemented
3. 📝 Add import lint script (`scripts/check_imports.py`) for CI

### Skip

1. ❌ Tests for empty directories
2. ❌ Tests for services/ boundaries (it's the composition root)

---

**Approval Criteria:** All existing 42+ tests pass, new boundary tests pass, no core/ context/ messaging/ file imports from an outer layer.
