# Stage 03 Package Boundaries

## Overview

Stage 03 introduces four new packages:
- `core/` - Pure logic & protocols (no infrastructure)
- `messaging/` - Message handling & conversation flow (placeholder)
- `context/` - Understanding the learner (thin/empty)
- `services/` - Light orchestration (existing, now active)

## Package Descriptions

### core/ - Pure Logic & Protocols

**Purpose**: Abstract interfaces and pure functions that define WHAT components do, not HOW.

**Contains**:
- Protocols (abstract interfaces via `typing.Protocol`)
- Pure functions (no I/O, no infrastructure)
- Type aliases and common patterns

**Dependencies**:
- Standard library only
- NO imports from messaging/, context/, services/, adapters/, registries/

**Used by**:
- messaging/ (protocols for handlers)
- context/ (protocols for providers)
- services/ (protocols for orchestration)
- adapters/ (may implement protocols)

**Does NOT contain**:
- Student types or profiles
- Subject categories or taxonomies
- Ability levels or performance classifications
- Any rigid domain models
- Infrastructure or I/O code

---

### messaging/ - Message Handling (Placeholder)

**Purpose**: Message routing and conversation flow infrastructure.

**Current State**: Placeholder structure. No working implementations.

**Contains**:
- `router.py` - Skeleton showing intended routing structure
- `conversation.py` - Skeleton showing intended conversation state structure

**Dependencies**:
- core/ (for protocols)
- May use registries/ for handler discovery (future)

**Used by**:
- services/ (for message orchestration)

**Does NOT contain**:
- Working message handlers (yet)
- Full conversation engine (yet)
- Channel-specific implementations (yet)

---

### context/ - Learner Understanding (Thin)

**Purpose**: Provide context for message processing.

**Current State**: Minimal/placeholder. Intentionally thin.

**Contains**:
- `session.py` - Skeleton showing intended session structure
- `providers.py` - Skeleton showing intended context provider structure

**Dependencies**:
- core/ (for ContextProvider protocol)

**Used by**:
- services/ (for context in orchestration)
- messaging/ (for session context)

**Does NOT contain**:
- Student types or profiles
- Subject categories
- Ability levels
- Any fixed schema for "learner data"

**Design Principle**: Context is what implementations make of it. A session is just a session. What it contains is up to implementations.

---

### services/ - Light Orchestration

**Purpose**: Coordinate between components. Wire things together.

**Current State**: Active placeholder. Some skeleton patterns.

**Contains**:
- `message_service.py` - Skeleton showing message orchestration
- `patterns.py` - Skeleton showing orchestration patterns

**Dependencies**:
- core/ (for protocols)
- messaging/ (for message handling)

**Used by**:
- main.py (for application services)

**Does NOT contain**:
- Business logic (that's in handlers/implementations)
- Domain models (that's not services' job)
- Direct I/O (services coordinate, they don't do I/O themselves)

---

## Import Rules

### Allowed Import Directions

```
core/ ← NO imports from other waxprep packages
  ↑
  ├── messaging/ imports from core/
  ├── context/   imports from core/
  └── services/  imports from core/, messaging/

adapters/ may implement protocols from core/
registries/ may reference protocol types (for type hints)
main.py may import from services/
```

### Forbidden Import Directions

```
messaging/ → core/        ✓ ALLOWED
context/   → core/        ✓ ALLOWED
services/  → core/        ✓ ALLOWED
services/  → messaging/   ✓ ALLOWED

messaging/ → services/    ✗ FORBIDDEN (circular)
context/   → services/    ✗ FORBIDDEN (circular)
core/     → any waxprep/  ✗ FORBIDDEN (core is pure)

adapters/ → core/         ✓ ALLOWED (implements protocols)
adapters/ → services/     ✗ FORBIDDEN (adapters don't orchestrate)
```

### Rationale

- `core/` must be dependency-free to be reusable and testable
- `messaging/`, `context/`, `services/` can depend on `core/`
- `services/` orchestrates, so it's the top of the dependency chain
- Circular dependencies make testing and reasoning harder

---

## Boundary Documentation in Code

Each package's `__init__.py` documents:
1. What the package contains
2. What it does NOT contain
3. Import rules relevant to that package

Each skeleton module documents:
1. That it's a skeleton/placeholder
2. The intended design (NOT decisions)
3. What will be implemented later

---

## What This Structure Enables

1. **Flexibility**: No rigid domain models means implementations can define their own structures
2. **Testability**: Pure `core/` can be tested in isolation
3. **Evolution**: Placeholder structure shows intent without committing to implementation
4. **Clarity**: Boundary docs make it clear what belongs where

## What This Structure Avoids

1. **Student types** - Not defined; implementations decide if/when needed
2. **Subject categories** - Not defined; not everyone needs subject categorization
3. **Ability levels** - Not defined; not a framework concern
4. **Rigid schemas** - Protocols are minimal; implementations extend as needed

---

## Stage Progression

| Stage | Focus |
|-------|-------|
| 01-02 | Foundation (registries, middleware, config) |
| 03 | Package structure (this architecture) |
| 04+ | Implementations within this structure |

Stage 03 establishes the boundaries. Later stages fill in implementations
within these boundaries without changing the package structure.
