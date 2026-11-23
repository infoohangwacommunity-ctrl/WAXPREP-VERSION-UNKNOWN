# Stage 03 Architecture Guide

> **Philosophy reminder:** We are creating *land*, not a *finished house*. The architecture should leave room for discovery while preventing accidental tight coupling.

## Current State (Stage 03 Completed)

Stage 03 has established the foundation. The current implementation is minimal by design:

```
src/waxprep/
├── main.py              # ASGI app, health endpoints, lifespan, middleware
├── config.py            # Settings (NO hardcoded values)
├── core/                # Pure logic & protocols (NO infrastructure imports)
│   ├── __init__.py      # Boundary rules, purpose statement
│   ├── protocols.py     # Domain protocols (Message, MessageHandler, ContextProvider)
│   └── pure.py          # Pure functions (normalize_text, extract_keywords, etc.)
├── messaging/           # Message handling & conversation flow (PLACEHOLDER)
│   └── __init__.py      # Boundary rules, placeholder for future code
├── context/             # Understanding the learner (PLACEHOLDER)
│   └── __init__.py      # Boundary rules, open land - internal shape TBD
├── services/            # Light orchestration (PLACEHOLDER)
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
└── adapters/            # Fake adapter implementations (source of truth)
    ├── __init__.py
    ├── fake_channel.py  # FakeChannelAdapter
    ├── fake_model.py    # FakeModelAdapter
    └── fake_tool.py    # FakeTool
```

### What Exists vs. What's Placeholder

| Package | Status | Contents |
|---------|--------|----------|
| `core/` | ✅ Implemented | Protocols, pure functions |
| `messaging/` | 🔲 Placeholder | `__init__.py` only |
| `context/` | 🔲 Placeholder | `__init__.py` only |
| `services/` | 🔲 Placeholder | `__init__.py` only |
| `registries/` | ✅ Implemented | Base registry, channel/model/tool registries |
| `adapters/` | ✅ Implemented | Fake adapters for testing |
| `middleware/` | ✅ Implemented | Request ID middleware |

## 1. Package Relationship Map

```
┌─────────────────────────────────────────────────────────────────┐
│  Outer Layer (infrastructure, wiring, composition)              │
│  services/                                                      │
│    └─ light orchestration only; no business logic               │
├─────────────────────────────────────────────────────────────────┤
│  Messaging Layer (conversation flow, routing)                  │
│  messaging/                                                     │
│    ├─ Message types (what flows through the system)            │
│    ├─ Router (decides where a message goes — swappable)        │
│    └─ Handlers (channel-specific entry/exit points)            │
│    └─ Depends on: core/ (protocols), registries/ (channel/model lookups)   │
├─────────────────────────────────────────────────────────────────┤
│  Context Layer (understanding the learner)                     │
│  context/                                                       │
│    ├─ LearnerProfile (what we know — open schema)              │
│    ├─ ContextStore (how we persist/retrieve — swappable)       │
│    └─ Observation (raw signals from messages)                  │
│    └─ Depends on: core/ only                                   │
├─────────────────────────────────────────────────────────────────┤
│  Core Layer (pure logic & protocols — zero infrastructure)     │
│  core/                                                          │
│    ├─ Protocols/Interfaces (swappable contracts)               │
│    ├─ Value objects (immutable data with behaviour)            │
│    └─ Domain rules that apply regardless of channel/model/tool │
│    └─ Depends on: nothing                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Dependency Rule (Outer → Inner)

| From | May depend on | Must NOT depend on |
|------|---------------|-------------------|
| `services/` | `messaging/`, `context/`, `core/`, `registries/`, `adapters/` | anything outside this list |
| `messaging/` | `core/`, `registries/` | `services/`, infrastructure, adapters directly, context/ |
| `context/` | `core/` | `messaging/`, `services/`, infrastructure |
| `core/` | nothing | anything |

**Why this direction?** Inner layers define *what* is possible; outer layers decide *when* and *how* to use it. This means:
- You can swap the context store without touching messaging logic
- You can add a new channel handler without touching learner profile logic
- You can test core protocols with zero mocking

---

## 2. Boundary Protocols

### 2.1 Core → Everything: The Protocol Layer

All Protocols live in `core/`. These define *capability contracts*, not implementations.

**Current protocols in `core/protocols.py`:**
- `Message` - message type that flows through the system
- `MessageHandler` - handles messages and produces responses
- `ContextProvider` - provides learner context

**Why Protocols instead of abstract base classes?** Protocols let any existing class satisfy the contract without inheritance. A real WhatsApp adapter, a test double, and a future AI-generated adapter can all be used interchangeably without modification.

### 2.2 Messaging Boundary

Messaging depends on core protocols and registries only. It does not currently import context; any future need to read learner context would go through the registries (which expose adapter lookups), not through a direct messaging→context import.

**Key constraint:** Messaging never *writes* to context. Messaging also never reads context directly today — that boundary remains closed until explicitly reopened with a corresponding architecture test and import-linter contract.

### 2.3 Context → Core: Pure dependency

Context depends only on core protocols. It has no knowledge of channels, models, or services.

### 2.4 Services → Everything: Composition Root

`services/` is where you wire real implementations together. It is the **only** place that knows about concrete adapters.

**This is the only layer that imports from multiple layers simultaneously.** Every other file imports only from inner layers.

---

## 3. Ensuring Dependency Direction

### Mechanism 1: Test Enforcement

The `tests/test_boundaries.py` file enforces the dependency rules by scanning imports with AST. This catches accidental coupling early.

### Mechanism 2: Code review checklist

When reviewing Stage 03 code, ask:
- Does this file import from an outer layer? (for inner layer files)
- Does this file know about a concrete adapter? (for non-services files)
- Could this be tested without any infrastructure? (for core files)

---

## 4. What Stage 03 Proves

Stage 03 is about proving the *architecture* works, not delivering features. The tests demonstrate:

1. **Protocols are satisfied by multiple implementations** — a test double and a fake implementation both satisfy the protocols
2. **Dependency direction is enforced** — `core/` imports nothing; `context/` imports only `core/`
3. **Components can be swapped** — replacing adapters doesn't break the structure
4. **Conversation flow is open** — no hardcoded paths; the architecture enables flexibility

---

## 5. Placeholder Packages: What to Build Later

### `messaging/` — Message handling & conversation flow

To be implemented in later stages:
- Message type discriminators (text, image, etc.)
- Swappable message router
- Channel-specific handlers (WhatsApp, Telegram, etc.)

**Responsibility:** Receive messages, decide what to do with them, produce responses. Depends on core protocols and registries only. **Never** knows about concrete channel/model/tool implementations.

### `context/` — Understanding the learner

To be implemented in later stages:
- `LearnerProfile` (open schema — what we know about a learner)
- `ContextStore` protocol (swappable storage)
- Observation extraction and aggregation

**Responsibility:** Capture and retrieve what we know about learners. No channel knowledge. No model knowledge. No orchestration.

**Key design choice:** The learner profile uses an open schema, not fixed fields. We don't know yet what dimensions matter. The AI will discover them through interaction.

### `services/` — Light orchestration

To be implemented in later stages:
- Composition root that wires implementations
- Observation extractor (messages → context updates)

**Responsibility:** The only place that knows about concrete adapters. Wires protocols to implementations. Thin — if you can't explain what a service does in one sentence, it's doing too much.

---

## 6. What NOT to Build in Stage 03

These belong to later stages, when the AI has learned enough to make informed decisions:

- ❌ Real channel adapters (WhatsApp, Telegram, etc.)
- ❌ Real model integrations
- ❌ Real storage backends
- ❌ Conversation trees or fixed flows
- ❌ Student categorization or fixed learner types
- ❌ Prescriptive "intelligent response" logic in core

---

## 7. Anti-Patterns to Watch For

| Anti-pattern | Why it violates the philosophy | What to do instead |
|--------------|-------------------------------|---------------------|
| Hardcoded learner categories | "No permanent categories" | Use open observations that the AI interprets |
| Fixed message routing | Channels must stay swappable | Router is a separate swappable component |
| Context storing channel-specific data | Unrelated components become coupled | Context is channel-agnostic |
| Services importing from messaging internals | Dependency direction violated | Services depend on messaging protocols, not internals |
| Core importing from registries | Infrastructure leakage into pure logic | Core defines protocols; registries are outer-layer wiring |
| Prescriptive "intelligent response" in core | AI must learn the student over time | Response generation is model-dependent, not hardcoded |

---

## 8. Quick Reference: Current File Responsibility Matrix

| File | May import from | Must NOT import from | Purpose |
|------|-----------------|---------------------|---------|
| `core/protocols.py` | nothing | anything | Capability contracts |
| `core/pure.py` | nothing | anything | Pure functions (no I/O) |
| `context/__init__.py` | `core/` | `messaging/`, `services/`, registries | Boundary rules, placeholder |
| `messaging/__init__.py` | `core/` | `services/`, registries | Boundary rules, placeholder |
| `services/__init__.py` | — | — | Boundary rules, composition placeholder |
| `registries/*.py` | `core/` (protocols) | `messaging/`, `context/`, `services/` | Registry implementations |
| `adapters/*.py` | registry protocols | `core/`, other adapters | Fake adapter implementations |
| `main.py` | FastAPI, config, registries, middleware, adapters | `core/` (framework-agnostic) | ASGI app entry point |

---

## Next Steps

This document defines the *land*. The placeholders (`messaging/`, `context/`, `services/`) are ready for future implementation when the needs are better understood.

## Related: Stage 08 — Universal Hardcoding Detection

Stage 08 adds an independent detection system that protects the architectural boundaries defined here. It ensures that `messaging/`, `context/`, and `services/` modules do not contain hardcoded conversational behavior that would undermine the flexibility this architecture is designed to provide.

See `docs/DETECTOR_SPECIFICATION.md` for details.
