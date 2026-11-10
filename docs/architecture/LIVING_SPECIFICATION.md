# WaxPrep Living Specification

## 📜 OVERVIEW

This document defines the **executable architectural rules** for WaxPrep. It serves as the foundation for the architectural enforcement system that prevents hardcoded educational decisions while preserving legitimate deterministic infrastructure.

### Core Principle

**WaxPrep must NEVER make educational decisions through hardcoded logic.**

- ✅ **ALLOWED**: Infrastructure that supports AI decision-making (configuration, permissions, validation)
- ❌ **PROHIBITED**: Any code that makes educational decisions without AI model involvement

### The Distinction

| Category | Definition | Examples | Allowed? |
|----------|------------|----------|----------|
| **Deterministic Infrastructure** | Technical rules that enable the system to function | Connection timeouts, retry limits, auth rules, data validation | ✅ YES |
| **Deterministic Intelligence** | Predefined educational decisions that should be made by AI | Subject classification, student level detection, teaching method selection | ❌ NO |

---

## 🏛️ ARCHITECTURAL BOUNDARIES

### Layer Responsibilities

#### 1. Domain Layer (`src/waxprep/domain/`)
**Purpose**: Pure business logic and value objects

**ALLOWED**:
- Result types (Success, Failure, etc.)
- Value objects (StudentId, SessionId, etc. - but NOT Student, Session as domain models)
- Domain exceptions
- Pure business rules (not educational)

**PROHIBITED**:
- ❌ Any educational knowledge (subjects, levels, teaching methods)
- ❌ Dependencies on external services
- ❌ Infrastructure concerns
- ❌ Hardcoded educational decisions

**Rule**: `WAXPREP-ARCH-001`
> Domain layer must contain ONLY pure business logic. No external dependencies, no educational knowledge.

---

#### 2. Application Layer (`src/waxprep/application/`)
**Purpose**: Use case orchestration and port definitions

**ALLOWED**:
- Port interfaces (ChannelPort, ModelPort, ToolPort)
- Use case orchestration
- Business logic coordination
- Dependencies on domain layer

**PROHIBITED**:
- ❌ Direct implementation of ports (use adapters)
- ❌ Educational decision-making
- ❌ Hardcoded educational knowledge
- ❌ Direct dependencies on concrete infrastructure

**Rule**: `WAXPREP-ARCH-002`
> Application layer defines WHAT needs to be done, not HOW. All educational decisions must go through AI models via ports.

---

#### 3. Adapters Layer (`src/waxprep/adapters/`)
**Purpose**: Implement port interfaces

**ALLOWED**:
- Implementation of port interfaces
- Communication with external services
- Data transformation
- Fake/testing implementations

**PROHIBITED**:
- ❌ Educational decision-making
- ❌ Hardcoded educational knowledge
- ❌ Business logic (belongs in application)

**Rule**: `WAXPREP-ARCH-003`
> Adapters implement HOW to communicate with external systems. They must NOT make educational decisions.

---

#### 4. Infrastructure Layer (`src/waxprep/infrastructure/`)
**Purpose**: Runtime concerns and technical implementation

**ALLOWED**:
- Configuration management
- Logging
- Lifecycle management
- Dependency injection
- Technical utilities
- Generic student/account management (IDs, permissions, NOT educational data)

**PROHIBITED**:
- ❌ Educational decision-making
- ❌ Hardcoded educational knowledge
- ❌ Business logic (belongs in domain/application)

**Rule**: `WAXPREP-ARCH-004`
> Infrastructure provides technical support. It must NOT contain educational intelligence.

---

#### 5. Composition Root (`src/waxprep/main.py`)
**Purpose**: Wire all layers together

**ALLOWED**:
- Import from ALL layers
- Initialize configuration
- Register adapters with ports
- Set up application
- Define routes

**PROHIBITED**:
- ❌ Business logic (belongs in domain/application)
- ❌ Educational decision-making

**Rule**: `WAXPREP-ARCH-005`
> Only main.py may import across all layers. No other module may do this.

---

## 🚫 PROHIBITED PATTERNS

### Pattern 1: Hardcoded Educational Classifications

**Violation**: Any fixed list or dictionary of educational subjects, topics, or categories.

```python
# ❌ PROHIBITED
SUBJECTS = ["Anatomy", "Biology", "Chemistry", "Physics"]

TOPICS = {
    "biology": ["cells", "genetics", "evolution"],
    "chemistry": ["atoms", "molecules", "reactions"]
}

if subject in ["Anatomy", "Biology", "Chemistry"]:
    # educational decision
    pass
```

**Rule**: `WAXPREP-HARD-001`
> No hardcoded educational classifications. All educational categorization must be done by AI models.

---

### Pattern 2: Hardcoded Student Categories

**Violation**: Any fixed student levels, categories, or classifications.

```python
# ❌ PROHIBITED
STUDENT_LEVELS = ["Beginner", "Intermediate", "Advanced"]

if student.level == "Beginner":
    # educational decision based on hardcoded level
    pass

STUDENT_TYPES = {"SS1": "Senior Secondary 1", "SS2": "Senior Secondary 2"}
```

**Rule**: `WAXPREP-HARD-002`
> No hardcoded student categories or levels. Student progression must be context-based, not classification-based.

---

### Pattern 3: Hardcoded Teaching Methods

**Violation**: Any predefined teaching approaches or methodologies.

```python
# ❌ PROHIBITED
TEACHING_METHODS = {
    "explanation": "Provide detailed explanation",
    "example": "Give practical examples",
    "quiz": "Ask questions"
}

def get_teaching_method(topic):
    # Hardcoded decision
    if topic == "Anatomy":
        return "explanation"
    return "example"
```

**Rule**: `WAXPREP-HARD-003`
> No hardcoded teaching methods. All pedagogical decisions must be made by AI models based on context.

---

### Pattern 4: Hardcoded Responses

**Violation**: Any fixed responses that don't adapt to context.

```python
# ❌ PROHIBITED (if not configurable)
def welcome_student():
    return "Welcome to WaxPrep. How can I help you today?"

# ❌ PROHIBITED (hardcoded educational content)
def explain_anatomy():
    return "Anatomy is the study of the structure of living things..."
```

**Exception**: Generic system messages (error messages, status messages) are allowed if they don't contain educational content.

**Rule**: `WAXPREP-HARD-004`
> No hardcoded educational responses. All educational content must be generated by AI models.

---

### Pattern 5: Conditional Branching on Educational Strings

**Violation**: Making decisions based on fixed educational keywords.

```python
# ❌ PROHIBITED
if "anatomy" in message.lower():
    return handle_anatomy_question()
elif "biology" in message.lower():
    return handle_biology_question()
```

**Rule**: `WAXPREP-HARD-005`
> No conditional branching based on fixed educational strings. Use AI model for intent detection.

---

### Pattern 6: Hidden Educational Dictionaries

**Violation**: Dictionaries that map to educational knowledge, even if not obvious.

```python
# ❌ PROHIBITED
SUBJECT_CODES = {"BIO101": "Biology 101", "CHEM202": "Chemistry 202"}

# ❌ PROHIBITED (even in config)
CONFIG = {
    "supported_subjects": ["Anatomy", "Biology", "Chemistry"]
}
```

**Exception**: Non-educational dictionaries (config, permissions, etc.) are allowed.

**Rule**: `WAXPREP-HARD-006`
> No dictionaries containing educational knowledge. All educational data must be dynamic.

---

## ✅ ALLOWED PATTERNS

### Pattern 1: Legitimate Configuration

```python
# ✅ ALLOWED - Technical configuration
CONFIG = {
    "max_message_length": 4096,
    "timeout_seconds": 30,
    "retry_attempts": 3
}

# ✅ ALLOWED - Security/permissions
PERMISSIONS = {
    "admin": ["read", "write", "delete"],
    "user": ["read", "write"]
}
```

---

### Pattern 2: Generic Student Management

```python
# ✅ ALLOWED - Student identifiers (not educational data)
class StudentId:
    value: str

# ✅ ALLOWED - Account management
def get_student_record(student_id: StudentId):
    # Returns student's conversation history, preferences, etc.
    # Does NOT return educational classification
    pass
```

---

### Pattern 3: Validation Rules

```python
# ✅ ALLOWED - Data validation
if len(message) > MAX_MESSAGE_LENGTH:
    raise ValueError("Message too long")

# ✅ ALLOWED - Type checking
if not isinstance(student_id, StudentId):
    raise TypeError("Invalid student ID")
```

---

### Pattern 4: AI Model Integration

```python
# ✅ ALLOWED - Delegate to AI model
def process_message(message: str, context: dict) -> str:
    # Let AI decide how to respond
    response = model.generate(
        prompt=build_prompt(message, context),
        context=context
    )
    return response

# ✅ ALLOWED - Context-based decisions
def get_response(message: str, student_context: dict) -> str:
    # AI model makes educational decisions based on context
    return model.generate_response(message, student_context)
```

---

## 🎯 SEVERITY LEVELS

| Level | Description | Action | Examples |
|-------|-------------|--------|----------|
| **BLOCKING** | Confirmed architectural violation | Merge blocked, must fix | Hardcoded subjects, educational conditionals |
| **WARNING** | Suspicious pattern, needs review | Merge allowed, but flag for review | Large dictionaries, unusual conditionals |
| **INFORMATIONAL** | Suggestion or best practice | Merge allowed, inform developer | Style improvements, documentation |

---

## 📋 ENFORCEMENT MECHANISMS

### 1. AST-Based Structural Analysis
Detects patterns in code structure without understanding semantics.

**Detects**:
- Conditional branching on string literals
- Large dictionaries with educational-looking keys
- Hardcoded response functions

### 2. Semantic Analysis (Semgrep)
Pattern-based detection with semantic awareness.

**Rules File**: `.semgrep/waxprep_rules.yml`

### 3. Import Linter
Enforces architectural layer boundaries.

**File**: `scripts/lint_imports.py`

### 4. Architectural Fitness Tests
Automated tests that verify architectural rules.

**Files**: `tests/architecture/*`

### 5. AI-Assisted Review
AI agent that reviews changes for architectural violations.

**File**: `scripts/ai_architectural_reviewer.py`

### 6. Property-Based Testing
Tests that verify behavior across many inputs.

**Files**: `tests/property_based/*`

### 7. Mutation Testing
Tests that verify detectors catch deliberate violations.

**Files**: `tests/detector_verification/*`

---

## 🔄 UPDATING THIS SPECIFICATION

1. **Propose Change**: Create a PR with the proposed rule change
2. **Review**: All architectural changes must be reviewed by at least 2 maintainers
3. **Test**: Update detector verification tests to cover new rules
4. **Document**: Update this document and machine-readable rules
5. **Merge**: Only after all tests pass

---

## 📄 MACHINE-READABLE RULES

See: `.waxprep/architectural_rules.yaml`

---

## ✅ APPROVAL

**Status**: APPROVED for implementation
**Approved By**: WaxPrep Architecture Team
**Date**: 2026-11-10
**Version**: 1.0.0

---

## 📚 REFERENCES

- [Hexagonal Architecture ADR](../docs/adr/001-hexagonal-architecture.md)
- [Error Handling ADR](../docs/adr/002-error-handling-convention.md)
- [Definition of Done](../docs/DEFINITION_OF_DONE.md)
