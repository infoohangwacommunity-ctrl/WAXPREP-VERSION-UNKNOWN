# Stage 03 Architecture Guide

> **Philosophy reminder:** We are creating *land*, not a *finished house*. The architecture should leave room for discovery while preventing accidental tight coupling.

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
│    └─ Depends on: core/ (protocols), context/ (read context)   │
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
| `services/` | `messaging/`, `context/`, `core/` | anything outside this list |
| `messaging/` | `context/`, `core/` | `services/`, infrastructure |
| `context/` | `core/` | `messaging/`, `services/`, infrastructure |
| `core/` | nothing | anything |

**Why this direction?** Inner layers define *what* is possible; outer layers decide *when* and *how* to use it. This means:
- You can swap the context store without touching messaging logic
- You can add a new channel handler without touching learner profile logic
- You can test core protocols with zero mocking

---

## 2. Boundary Protocols

### 2.1 Core → Everything: The Protocol Layer

Place all Protocols in `core/protocols/`. These define *capability contracts*, not implementations.

```python
# core/protocols/channels.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class ChannelSender(Protocol):
    """Anything that can send a message out through a channel."""
    async def send(self, recipient: str, content: dict) -> dict: ...

@runtime_checkable
class ChannelReceiver(Protocol):
    """Anything that can receive a message from a channel."""
    async def receive(self) -> dict | None: ...
```

```python
# core/protocols/models.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class ModelGenerator(Protocol):
    """Anything that can generate a response from a prompt."""
    async def generate(self, prompt: str, context: dict | None = None) -> str: ...
```

```python
# core/protocols/context.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class LearnerContextReader(Protocol):
    """Read what we know about a learner."""
    async def get(self, learner_id: str) -> dict | None: ...

@runtime_checkable
class LearnerContextWriter(Protocol):
    """Record something we learned about a learner."""
    async def update(self, learner_id: str, observation: dict) -> None: ...
```

**Why Protocols instead of abstract base classes?** Protocols let any existing class satisfy the contract without inheritance. A real WhatsApp adapter, a test double, and a future AI-generated adapter can all be used interchangeably without modification.

### 2.2 Messaging → Context: The "Read Context" Boundary

Messaging handlers may need to know something about the learner before responding. This is the only dependency from messaging into context, and it should be narrow:

```python
# messaging/with_context.py (example pattern, not prescriptive)
from waxprep.core.protocols.context import LearnerContextReader

class MessageHandler:
    def __init__(self, context_reader: LearnerContextReader):
        self._context = context_reader

    async def handle(self, message: dict) -> dict:
        learner_context = await self._context.get(message.get("from"))
        # ... use context to shape response ...
```

**Key constraint:** Messaging never *writes* to context. Writing happens through a separate pathway (observation extraction), keeping the direction clear.

### 2.3 Context → Core: Pure dependency

Context depends only on core protocols. It has no knowledge of channels, models, or services.

### 2.4 Services → Everything: Composition Root

`services/` is where you wire real implementations together. It is the **only** place that knows about concrete adapters.

```python
# services/composition.py (conceptual — implementation is your choice)
from waxprep.registries.channel import get_channel_registry
from waxprep.registries.model import get_model_registry
from waxprep.context.store import MemoryContextStore
from waxprep.messaging.router import Router

def compose_message_router() -> Router:
    channels = get_channel_registry()
    models = get_model_registry()
    context_store = MemoryContextStore()  # swappable
    return Router(channels, models, context_store)
```

**This is the only file that imports from multiple layers simultaneously.** Every other file imports only from inner layers.

---

## 3. Ensuring Dependency Direction

### Mechanism 1: Layered `pyproject.toml` optional dependencies (future)

If the project grows, consider making each layer a separate installable package. For now, directory structure is sufficient.

### Mechanism 2: Import linting in CI

Add a simple check that enforces the dependency rules:

```python
# scripts/check_imports.py (optional guard)
ALLOWED_IMPORTS = {
    "waxprep.core": [],                                    # nothing
    "waxprep.context": ["waxprep.core"],                   # only core
    "waxprep.messaging": ["waxprep.core", "waxprep.context"],  # core + context
    "waxprep.services": ["waxprep.core", "waxprep.context", "waxprep.messaging", "waxprep.registries", "waxprep.adapters"],
}
```

Run this in CI to catch accidental coupling early.

### Mechanism 3: Code review checklist

When reviewing Stage 03 code, ask:
- Does this file import from an outer layer? (for inner layer files)
- Does this file know about a concrete adapter? (for non-services files)
- Could this be tested without any infrastructure? (for core files)

### Mechanism 4: Package-level `__init__.py` as gate

Each package's `__init__.py` should re-export only what the next outer layer needs. This makes illegal imports visibly break:

```python
# context/__init__.py
from waxprep.context.profile import LearnerProfile
from waxprep.context.store import ContextStore  # protocol, not implementation

__all__ = ["LearnerProfile", "ContextStore"]
```

---

## 4. Placeholder Code: What to Include (and What to Avoid)

### What to include: Protocols and value objects

These define the *shape* of the system without dictating *how* it works.

```python
# core/messages.py — message types that flow through the system
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class InboundMessage:
    """A message received from any channel."""
    channel: str
    sender: str
    content: dict[str, Any]
    timestamp: float

@dataclass(frozen=True)
class OutboundMessage:
    """A message to send through any channel."""
    recipient: str
    content: dict[str, Any]
```

**Why this helps:** Anyone implementing a new channel knows what shape messages take. The dataclass is frozen because messages should be immutable once created.

### What to include: Abstract store protocol (not implementation)

```python
# context/store.py — what a context store must provide
from typing import Protocol

class ContextStore(Protocol):
    """Swappable storage for learner context."""
    async def get(self, learner_id: str) -> dict | None: ...
    async def observe(self, learner_id: str, observation: dict) -> None: ...
```

**Do NOT include:** A concrete implementation like `SQLiteContextStore` or `RedisContextStore`. Let implementers choose the storage medium. The protocol is the land; the implementation is the house.

### What to include: Open-ended learner profile

```python
# context/profile.py — what we know about a learner (open schema)
from dataclasses import dataclass, field
from typing import Any

@dataclass
class LearnerProfile:
    """What we know about a learner. Open schema — add observations over time."""
    learner_id: str
    known_topics: set[str] = field(default_factory=set)
    observed_preferences: dict[str, Any] = field(default_factory=dict)
    interaction_count: int = 0

    def record_observation(self, key: str, value: Any) -> None:
        self.observed_preferences[key] = value
        self.interaction_count += 1
```

**Design choice:** `observed_preferences` is an open `dict`, not a fixed set of fields. We don't know yet what dimensions matter. The AI will discover them.

### What NOT to include: Prescriptive conversation flows

Avoid:
- Fixed dialogue trees
- Hardcoded "welcome → assess → teach → quiz" sequences
- Predefined categories of learner ("beginner", "intermediate", "advanced")
- Keyword-based routing

These are the opposite of "creating land." They bake in assumptions the AI hasn't earned yet.

### What NOT to include: Orchestration logic in core

`core/` should contain **no** "when to call X then Y" logic. That belongs in `services/` or `messaging/`. Core contains:
- Pure functions (no I/O)
- Protocols (capability contracts)
- Value objects (data with behaviour)

---

## 5. What Each Package Should Look Like

### `core/` — Pure logic & protocols

```
core/
├── __init__.py
├── protocols/
│   ├── __init__.py
│   ├── channels.py      # ChannelSender, ChannelReceiver
│   ├── models.py        # ModelGenerator
│   └── context.py       # LearnerContextReader, LearnerContextWriter
├── messages.py          # InboundMessage, OutboundMessage (value objects)
└── errors.py            # Domain errors (NotFoundError, etc.)
```

**Responsibility:** Define what the system *can do*, not what it *does*.

### `messaging/` — Message handling & conversation flow

```
messaging/
├── __init__.py
├── types.py             # Message type discriminators (text, image, etc.)
├── router.py            # Swappable message router (decides where messages go)
├── handlers/
│   ├── __init__.py
│   └── base.py          # Base handler protocol
└── flow/
    ├── __init__.py
    └── context_aware.py # Example: handler that reads learner context
```

**Responsibility:** Receive messages, decide what to do with them, produce responses. May read learner context. **Never** knows about concrete channel/model/tool implementations.

### `context/` — Understanding the learner

```
context/
├── __init__.py
├── profile.py           # LearnerProfile (open schema)
├── store.py             # ContextStore protocol (swappable storage)
├── observation.py       # Raw observation types from messages
└── aggregate.py         # Pure functions that combine observations
```

**Responsibility:** Capture and retrieve what we know about learners. No channel knowledge. No model knowledge. No orchestration.

**Key design choice:** `aggregate.py` contains pure functions that transform observations into profile updates. These are testable with zero infrastructure.

### `services/` — Light orchestration

```
services/
├── __init__.py
├── composition.py       # Wires real implementations together
├── message_router.py    # Concrete router using registries
└── observation_extractor.py  # Extracts observations from messages → context
```

**Responsibility:** The only place that knows about concrete adapters. Wires protocols to implementations. Thin — if you can't explain what a service does in one sentence, it's doing too much.

---

## 6. Swappable Component Points

These are the points where implementations can be swapped without touching other code:

| Component | Protocol | Example implementations |
|-----------|----------|------------------------|
| Channel sender | `ChannelSender` (core/protocols) | WhatsApp, Telegram, test double |
| Channel receiver | `ChannelReceiver` (core/protocols) | WebSocket poll, webhook, test double |
| Model generator | `ModelGenerator` (core/protocols) | OpenAI, Anthropic, local, test double |
| Context store | `ContextStore` (context/store.py) | In-memory, SQLite, Redis, vector DB |
| Message router | (defined in messaging/, swappable) | Simple router, AI-directed router, rule-based |

**All of these are proven swappable by the existing registry pattern.** The same principle extends to Stage 03.

---

## 7. What Stage 03 Should Prove

Stage 03 is about proving the *architecture* works, not delivering features. The tests should demonstrate:

1. **Protocols are satisfied by multiple implementations** — a test double and a fake implementation both satisfy `ModelGenerator`
2. **Dependency direction is enforced** — `core/` imports nothing; `context/` imports only `core/`
3. **Components can be swapped** — replacing the context store doesn't break message handling
4. **Conversation flow is open** — no hardcoded paths; the router decides based on message content and context

---

## 8. Anti-Patterns to Watch For

| Anti-pattern | Why it violates the philosophy | What to do instead |
|--------------|-------------------------------|---------------------|
| Hardcoded learner categories | "No permanent categories" | Use open observations that the AI interprets |
| Fixed message routing | Channels must stay swappable | Router is a separate swappable component |
| Context storing channel-specific data | Unrelated components become coupled | Context is channel-agnostic |
| Services importing from messaging internals | Dependency direction violated | Services depend on messaging protocols, not internals |
| Core importing from registries | Infrastructure leakage into pure logic | Core defines protocols; registries are outer-layer wiring |
| Prescriptive "intelligent response" in core | AI must learn the student over time | Response generation is model-dependent, not hardcoded |

---

## 9. Quick Reference: File Responsibility Matrix

| File | May import from | Must NOT import from | Purpose |
|------|-----------------|---------------------|---------|
| `core/protocols/*.py` | nothing | anything | Capability contracts |
| `core/messages.py` | nothing | anything | Message value objects |
| `context/profile.py` | `core/` | `messaging/`, `services/`, registries | Learner data model |
| `context/store.py` | `core/` | `messaging/`, `services/`, registries | Context storage protocol |
| `context/observation.py` | `core/` | `messaging/`, `services/`, registries | Observation value objects |
| `context/aggregate.py` | `core/`, `context/` | `messaging/`, `services/`, registries | Pure observation → profile transforms |
| `messaging/types.py` | `core/` | `services/`, registries | Message type discriminators |
| `messaging/router.py` | `core/`, `context/` | `services/`, registries | Message routing logic |
| `messaging/handlers/base.py` | `core/`, `context/` | `services/`, registries | Handler capability contract |
| `services/composition.py` | everything | nothing | Wires implementations |
| `services/observation_extractor.py` | `core/`, `context/`, `messaging/` | registries | Extracts observations from messages |

---

## 10. Next Steps

This document defines the *land*. Stage 03 implementation should:

1. Create the directory structure (`core/`, `messaging/`, `context/`, `services/`)
2. Implement the protocol layer in `core/`
3. Implement the context store protocol (no concrete store)
4. Implement a minimal message router that depends only on protocols
5. Add a composition root in `services/` that wires a concrete (fake) implementation
6. Add tests that prove swapability and dependency direction

**Do not implement:**
- Real channel adapters
- Real model integrations
- Real storage backends
- Conversation trees or fixed flows
- Student categorization

These belong to later stages, when the AI has learned enough to make informed decisions.
