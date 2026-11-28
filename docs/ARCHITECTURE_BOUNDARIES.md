# WaxPrep Foundation - Boundary Rules (Stages 03, 16-19)

**Version:** 1.2
**Python Requirement:** >=3.14,<3.15
**Last updated:** 2026-11-28 — Stage 18 composition and registry-selection correction

---

## Dependency Direction: Outer → Inner

**The Golden Rule:** Dependencies flow from outer layers toward inner layers. Inner layers MUST NOT import from outer layers.

```
┌─────────────────────────────────────────────────────────────────┐
│  OUTER: Composition Root (Stage 18)                             │
│  └── Selects implementations, assembles the typed graph         │
│      (Only production place that imports concrete adapters)      │
├─────────────────────────────────────────────────────────────────┤
│  OUTER: Messaging/Conversation                                  │
│  └── Talks to Core + Registries ONLY                           │
│      (Never imports concrete WhatsApp/Telegram/model code)     │
├─────────────────────────────────────────────────────────────────┤
│  OUTER: Adapters                                                │
│  └── Implement protocols                                       │
│      (Know about specific channels/models/SDKs)                │
├─────────────────────────────────────────────────────────────────┤
│  INNER: Registries                                              │
│  └── Own registration/lookup                                   │
│      (Talk ONLY through protocols)                             │
├─────────────────────────────────────────────────────────────────┤
│  INNER: Core/Pure Logic                                        │
│  └── Domain logic, rules, state machines                       │
│      (NO imports of adapters, channels, FastAPI, SDKs)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## Boundary Rule 1: Core/Pure Logic

**Location:** `src/waxprep/core/`  
**Current scope:** Generic pure utilities (`normalize_text`, `extract_keywords`, `build_response`, `compose_handlers`) and capability protocols. No tutor behaviour, student model or conversational rules exist yet.

### Rules

| Rule | Description |
|------|-------------|
| ❌ NO imports from `waxprep.adapters` | Core cannot depend on adapter implementations |
| ❌ NO imports from `waxprep.adapters` (concrete) | Core cannot import adapter-specific code |
| ❌ NO FastAPI imports | Core is framework-agnostic |
| ❌ NO external SDK imports | Core does not know about WhatsApp, Telegram, AI providers |
| ❌ NO HTTP/client code | Core is pure logic |

### Allowed Imports

- Standard library only
- Types from `typing` module
- Pure data classes/dicts for input/output

### Example: Valid Core Code

> Illustrative only — this file does not exist in the current repository.

```python
# src/waxprep/core/rules.py - VALID

from dataclasses import dataclass
from typing import Optional

@dataclass
class TutorDecision:
    """Pure data - no external dependencies."""
    action: str
    message: str
    next_state: Optional[str] = None

class TutorRuleEngine:
    """Core logic. Never imports adapters, channels, or FastAPI."""
    
    def evaluate(self, state: dict, input: str) -> TutorDecision:
        # Pure logic here
        return TutorDecision(action="respond", message="Hello", next_state="waiting")
```

### Example: Invalid Core Code

```python
# src/waxprep/core/rules.py - INVALID ❌

# VIOLATION: imports adapter
from waxprep.adapters.whatsapp import WhatsAppAdapter

# VIOLATION: imports FastAPI
from fastapi import HTTPException

# VIOLATION: imports external SDK
import whatsapp_business_sdk

class BadTutor:
    def __init__(self):
        self.adapter = WhatsAppAdapter()  # Can't do this in core
```

---

## Boundary Rule 2: Registries

**Location:** `src/waxprep/registries/`  
**Current scope:** Registration and lookup of adapters

### Rules

| Rule | Description |
|------|-------------|
| ✅ May define protocols | Registries define what adapters must implement |
| ✅ May import protocols | Uses Protocol types for type hints |
| ✅ Production path: `register(name, instance)` | Composition selects and supplies the implementation |
| ⚠️ Legacy only: `register_defaults()` | Historical convenience for foundation tests/embedding; not a production selection mechanism |
| ❌ NO implementation selection in new code | The composition root decides which concrete adapter is used |
| ❌ NO channel/model/SDK specific code | Registries are generic |

### Dependency Pattern

```
Registries define: Protocol (abstract)
Adapters implement: Protocol (concrete)
Registries register: Protocol (via register())
```

### Example: Valid Registry Code

```python
# src/waxprep/registries/channel.py - VALID

from typing import Protocol, runtime_checkable
from waxprep.registries.base import BaseRegistry

@runtime_checkable
class ChannelAdapter(Protocol):
    """Protocol that adapters must implement."""
    name: str
    async def handle_message(self, message: dict) -> dict: ...

class ChannelRegistry(BaseRegistry[ChannelAdapter]):
    """Registry owns registration, not implementation."""
    
    def register(self, name: str, adapter: ChannelAdapter) -> None:
        # Validates protocol compliance, not implementation
        if not hasattr(adapter, 'name'):
            raise ValueError("Must have 'name' attribute")
        self._items[name] = adapter
    
    def register_defaults(self) -> None:
        # LEGACY convenience only. Production composition selects the adapter.
        # Kept for foundation tests/old embedding; not the production path.
        from waxprep.adapters.fake_channel import FakeChannelAdapter
        self.register("fake", FakeChannelAdapter())
```

### Production selection (Stage 18)

`waxprep.composition.CompositionRoot` selects the concrete adapters. The
`registries` lifecycle component receives them and calls `register(name,
instance)`. Registries keep registration/lookup/validation; they no longer own
implementation selection in production.

---

## Boundary Rule 2.5: Composition Root

**Location:** `src/waxprep/composition/`
**Current scope:** Explicit typed assembly, dependency graph, lifetimes, typed
bundles and Stage 16 integration.

### Rules

| Rule | Description |
|------|-------------|
| ✅ Selects concrete implementations | Only production boundary that imports adapters |
| ✅ Builds the typed dependency graph | Providers, dependencies, lifetimes, cycles |
| ✅ Returns typed bundles | No global container or string-keyed lookup |
| ✅ Runs inside the Stage 16 lifecycle | Lifecycle remains the only initialization/cleanup owner |
| ❌ NO business logic | Assembly only; no message processing or tutor behaviour |
| ❌ NO global service locator | Components receive values; they never resolve from composition |
| ❌ Inner packages must not import composition | Enforced by import-linter/architecture tests |

`main.py` (the ASGI entrypoint) may import composition. No other inner package
may. Future workers may call the composition root from their own outer
entrypoint; they must not import it from business/domain code.

---

## Boundary Rule 3: Adapters

**Location:** `src/waxprep/adapters/`  
**Current scope:** Fake adapters for testing

### Rules

| Rule | Description |
|------|-------------|
| ✅ Implement protocols from registries | Adapters satisfy registry contracts |
| ✅ May import channel/model SDKs | Adapters know about specific platforms |
| ✅ May import external libraries | Adapters bridge to external systems |
| ❌ NO importing from core | Adapters don't depend on domain logic |
| ❌ NO importing other adapters | No coupling between adapter types |

### Future Real Adapters

Real adapters (WhatsApp, Telegram, AI providers) will live here and:

1. Implement the registry's Protocol
2. Import the specific SDK/library for that channel
3. Translate between external format and internal format

### Example: Valid Adapter Code

```python
# src/waxprep/adapters/whatsapp.py - FUTURE (valid pattern)

from waxprep.registries.channel import ChannelAdapter

class WhatsAppAdapter:
    """Real WhatsApp adapter. Implements protocol."""
    
    name = "whatsapp"
    
    def __init__(self):
        # May import WhatsApp SDK here
        import whatsapp_business_sdk
        self.client = whatsapp_business_sdk.Client(...)
    
    async def handle_message(self, message: dict) -> dict:
        # Translate WhatsApp format to internal format
        # Call core logic if needed (but core doesn't import this)
        return {"status": "handled", "channel": self.name}
```

### Example: Invalid Adapter Code

```python
# src/waxprep/adapters/whatsapp.py - INVALID ❌

# VIOLATION: adapter imports core (wrong direction)
from waxprep.core.tutor import TutorRuleEngine

# VIOLATION: adapter imports another adapter
from waxprep.adapters.telegram import TelegramAdapter

class BadWhatsAppAdapter:
    def __init__(self):
        self.tutor = TutorRuleEngine()  # Wrong: adapter shouldn't own core
```

---

## Boundary Rule 4: Messaging/Conversation Layer

**Location:** `src/waxprep/messaging/`  
**Current scope:** Placeholder — message handling & conversation flow (no implementation yet)

### Rules

| Rule | Description |
|------|-------------|
| ✅ Talks to core | Uses core logic for decisions |
| ✅ Talks to registries | Looks up adapters via registries |
| ❌ NO direct imports from concrete adapters | Must go through registries |
| ❌ NO direct WhatsApp/Telegram/model code | Abstracts away channel details |

### Why This Rule Exists

The messaging layer is the **orchestrator**. It receives messages from channels, decides what to do using core logic, and sends responses through the appropriate channel adapter.

If messaging imported concrete WhatsApp code directly, we'd be unable to:
- Swap WhatsApp for Telegram without rewriting messaging
- Test messaging without real WhatsApp connections
- Add new channels without modifying existing code

### Example: Valid Messaging Code

```python
# src/waxprep/messaging/handler.py - FUTURE (valid pattern)

from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.core.tutor import TutorRuleEngine  # Core logic

class MessageHandler:
    """Orchestrates message handling."""
    
    def __init__(self, channel_registry: ChannelRegistry, model_registry: ModelRegistry):
        self.channels = channel_registry
        self.models = model_registry
        self.tutor = TutorRuleEngine()
    
    async def handle(self, channel_name: str, message: dict) -> dict:
        # Get adapter via registry (not direct import)
        adapter = self.channels.get(channel_name)
        
        # Use core logic for decision
        decision = self.tutor.evaluate(message, channel_name)
        
        # Process through adapter
        return await adapter.handle_message(message)
```

### Example: Invalid Messaging Code

```python
# src/waxprep/messaging/handler.py - INVALID ❌

# VIOLATION: imports concrete adapter directly
from waxprep.adapters.whatsapp import WhatsAppAdapter

# VIOLATION: imports model SDK directly
import openai

class BadMessageHandler:
    async def handle(self, message: dict) -> dict:
        # Wrong: bypasses registry
        adapter = WhatsAppAdapter()
        
        # Wrong: talks to SDK directly, not through model registry
        response = openai.chat.complete(...)
```

---

## Boundary Rule 5: Context (Stage 03+)

**Location:** `src/waxprep/context/`  
**Current scope:** Placeholder — understanding the learner (no implementation yet)

### Rules

| Rule | Description |
|------|-------------|
| ✅ Reachable by services/main | Context can be accessed by outer orchestration layers |
| ❌ NO forced categories on students | Context is flexible, not prescriptive |

### Design Principle

Context should be a **capability** that orchestration layers (services, main) can use, not a **constraint** that forces a particular categorization model.

```python
# src/waxprep/context/manager.py - FUTURE (valid pattern)

class StudentContext:
    """Flexible context - no forced categories."""
    
    def __init__(self, student_id: str):
        self.student_id = student_id
        self.properties: dict = {}  # Arbitrary key-value pairs
    
    def get(self, key: str, default=None):
        return self.properties.get(key, default)
    
    def set(self, key: str, value):
        self.properties[key] = value

# Usage: messaging/core decides what to track
# No forced schema like "level", "category", "track"
```

---

## Package Import Rules Summary

### `src/waxprep/core/`

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.core` | standard lib, typing | `waxprep.adapters`, FastAPI, external SDKs |
| **Direction:** | Pure inward | Depends on nothing external |

### `src/waxprep/registries/`

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.registries.base` | standard lib, typing | Everything else |
| `waxprep.registries.channel` | `waxprep.registries.base`, typing, `waxprep.adapters` (legacy `register_defaults` only) | Concrete channel code, FastAPI, composition |
| `waxprep.registries.model` | `waxprep.registries.base`, typing, `waxprep.adapters` (legacy `register_defaults` only) | Concrete model code, FastAPI, composition |
| `waxprep.registries.tool` | `waxprep.registries.base`, typing, `waxprep.adapters` (legacy `register_defaults` only) | Concrete tool code, FastAPI, composition |
| **Direction:** | Defines → Implemented by | Production selection is composition; legacy defaults are not the production path |

### `src/waxprep/adapters/`

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.adapters.fake_*` | standard lib, typing | `waxprep.core`, other adapters |
| `waxprep.adapters.*` (real) | registry protocols, channel/model SDKs | `waxprep.core`, other adapters, FastAPI |
| **Direction:** | Implements protocols | Does not import core |

### `src/waxprep/messaging/`

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.messaging` | `waxprep.core`, `waxprep.registries`, standard lib | Concrete adapters, direct SDK imports, FastAPI |
| **Direction:** | Orchestrates via protocols | Does not bypass registries |

### `src/waxprep/context/`

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.context` | standard lib, typing | Nothing internal (optional dependency) |
| **Direction:** | Available to messaging/core | Not forced on anyone |

### `src/waxprep/composition/`

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.composition` | config, registries, adapters, lifecycle, observability, contracts, standard lib | `waxprep.main` (cycle) |
| **Direction:** | Outermost assembly | Inner packages never import it |

### `src/waxprep/main.py` (FastAPI app)

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.main` | FastAPI, uvicorn, `waxprep.config`, `waxprep.composition`, `waxprep.lifecycle`, `waxprep.middleware` | `waxprep.core` (framework-agnostic), concrete adapters (composition selects) |
| **Direction:** | Thin ASGI entrypoint | Assembly delegated to composition |

---

## Enforcement: How to Verify

### Static Analysis (mypy/pyright)

Run type checkers to catch boundary violations:

```bash
uv run mypy src/waxprep --strict
```

If core imports adapters, mypy will show the import and you can catch it in review.

### Architectural Test Pattern

Add a test that explicitly verifies boundaries:

```python
# tests/test_boundaries.py

import ast
import sys
from pathlib import Path

class TestBoundaryRules:
    """Verify no boundary violations in source code."""
    
    def test_core_does_not_import_adapters(self):
        """Core module must not import from adapters package."""
        core_path = Path("src/waxprep/core")
        if core_path.exists():
            for py_file in core_path.rglob("*.py"):
                tree = ast.parse(py_file.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            assert not alias.name.startswith("waxprep.adapters"), \
                                f"Core imports adapters: {alias.name}"
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and node.module.startswith("waxprep.adapters"):
                            pytest.fail(f"Core imports from adapters: {node.module}")
    
    def test_registries_only_import_adapters_in_register_defaults(self):
        """Registries should only import adapters in register_defaults method."""
        # Implementation would scan for import statements outside register_defaults
        pass
```

### Code Review Checklist

When reviewing PRs, ask:

- [ ] Does core import anything from `adapters/`? → REJECT
- [ ] Does core import FastAPI? → REJECT
- [ ] Does core import external SDKs? → REJECT
- [ ] Do registries import adapters outside legacy `register_defaults()`? → REJECT
- [ ] Does production code call `register_defaults()` or select adapters outside composition? → REJECT
- [ ] Does an inner package import `waxprep.composition`? → REJECT
- [ ] Did a component bypass the composition root with a global service locator? → REJECT
- [ ] Does messaging import concrete adapters directly? → REJECT
- [ ] Does messaging bypass registries to get adapters? → REJECT

---

## Current State of the Boundary Packages

The packages exist; most of them are intentionally empty land.

1. **Core** (`src/waxprep/core/`) — generic pure utilities (`normalize_text`, `extract_keywords`, `build_response`, `compose_handlers`) and capability protocols. It contains no tutor behavior, no student model and no conversational rules.
2. **Messaging layer** (`src/waxprep/messaging/`) — package boundary and statement of intent. No message orchestration is implemented.
3. **Context** (`src/waxprep/context/`) — package boundary only. No student state is implemented.
4. **Services** (`src/waxprep/services/`) — package boundary only. No product services.
5. **Composition** (`src/waxprep/composition/`) — Stage 18 composition root, typed graph, lifetimes and bundles. This is implemented; it is not a product service.
6. **Background** (`src/waxprep/background/`, `src/waxprep/worker.py`) — Stage 19 submission boundary, job registry, Taskiq adapter and independent worker entrypoint. No product jobs are registered.

`extract_keywords()` is a generic lexical utility. It is not, and must not
become, the tutor's student-understanding mechanism.

These boundaries ensure:

- Core remains testable without any external dependencies
- New channels can be added by creating adapters, not modifying core
- Messaging can swap channels without code changes
- Context evolves without breaking existing code

---

## Quick Reference: "Can This File Import X?"

| File Location | Can Import `adapters`? | Can Import `core`? | Can Import FastAPI? | Can Import SDKs? |
|---------------|------------------------|--------------------|---------------------|------------------|
| `registries/` | Legacy `register_defaults()` only | No | No | No |
| `adapters/` | No | No | No | Yes (for that adapter) |
| `core/` | **NO** | — | **NO** | **NO** |
| `messaging/` | No (use registries) | Yes | No | No (use registries/adapters) |
| `context/` | No | Optional | No | No |
| `composition/` | Yes (selection boundary) | No | No | Yes (selects adapters) |
| `background/` | No | No | No | Taskiq (framework adapter only) |
| `worker.py` | No | No | No (composition/background) | No |
| `main.py` | No (composition selects) | No | Yes | No |
| `middleware/` | No | No | Yes (Starlette) | No |

---

*Document version: 1.3*
*Last updated: 2026-11-28 — Stage 19 background execution boundary*
