# WaxPrep Foundation - Boundary Rules (Stage 03)

**Version:** 0.1.0  
**Python Requirement:** >=3.14  
**Last updated:** Stage 03 boundary definition (active copy)

---

## Dependency Direction: Outer → Inner

**The Golden Rule:** Dependencies flow from outer layers toward inner layers. Inner layers MUST NOT import from outer layers.

```
┌─────────────────────────────────────────────────────────────────┐
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

**Location:** `src/waxprep/core/` (future)  
**Current scope:** Domain logic, rules, state machines, tutor behavior

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

```python
# src/waxprep/core/tutor.py - VALID

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
# src/waxprep/core/tutor.py - INVALID ❌

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
| ❌ NO imports from `waxprep.adapters` (except `register_defaults`) | Registries don't know about concrete adapters |
| ❌ NO channel/model/SDK specific code | Registries are generic |
| ✅ `register_defaults()` is the ONLY exception | Explicitly documented bridge from registries to adapters |

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
        # ONLY place where registry imports from adapters
        from waxprep.adapters.fake_channel import FakeChannelAdapter
        self.register("fake", FakeChannelAdapter())
```

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

**Location:** `src/waxprep/messaging/` (future)  
**Current scope:** None yet (Stage 03 will add this)

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

**Location:** `src/waxprep/context/` (future)  
**Current scope:** None yet

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

### `src/waxprep/core/` (when added)

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.core` | standard lib, typing | `waxprep.adapters`, FastAPI, external SDKs |
| **Direction:** | Pure inward | Depends on nothing external |

### `src/waxprep/registries/`

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.registries.base` | standard lib, typing | Everything else |
| `waxprep.registries.channel` | `waxprep.registries.base`, typing, `waxprep.adapters` (only in `register_defaults`) | Concrete channel code, FastAPI |
| `waxprep.registries.model` | `waxprep.registries.base`, typing, `waxprep.adapters` (only in `register_defaults`) | Concrete model code, FastAPI |
| `waxprep.registries.tool` | `waxprep.registries.base`, typing, `waxprep.adapters` (only in `register_defaults`) | Concrete tool code, FastAPI |
| **Direction:** | Defines → Implemented by | Does not import adapters except `register_defaults` |

### `src/waxprep/adapters/`

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.adapters.fake_*` | standard lib, typing | `waxprep.core`, other adapters |
| `waxprep.adapters.*` (real) | registry protocols, channel/model SDKs | `waxprep.core`, other adapters, FastAPI |
| **Direction:** | Implements protocols | Does not import core |

### `src/waxprep/messaging/` (when added)

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.messaging` | `waxprep.core`, `waxprep.registries`, standard lib | Concrete adapters, direct SDK imports, FastAPI |
| **Direction:** | Orchestrates via protocols | Does not bypass registries |

### `src/waxprep/context/` (when added)

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.context` | standard lib, typing | Nothing internal (optional dependency) |
| **Direction:** | Available to messaging/core | Not forced on anyone |

### `src/waxprep/main.py` (FastAPI app)

| Package | Can Import From | Cannot Import From |
|---------|-----------------|---------------------|
| `waxprep.main` | FastAPI, uvicorn, `waxprep.config`, `waxprep.registries`, `waxprep.middleware`, `waxprep.adapters` | `waxprep.core` (core is framework-agnostic) |
| **Direction:** | Wires everything together | Kept separate from core logic |

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
- [ ] Do registries import adapters outside `register_defaults()`? → REJECT
- [ ] Does messaging import concrete adapters directly? → REJECT
- [ ] Does messaging bypass registries to get adapters? → REJECT

---

## Stage 03 Evolution

As Stage 03 adds:

1. **Core logic** (`src/waxprep/core/`) — domain rules, tutor behavior
2. **Messaging layer** (`src/waxprep/messaging/`) — message orchestration
3. **Context** (`src/waxprep/context/`) — student state (optional, flexible)

These boundaries ensure:

- Core remains testable without any external dependencies
- New channels can be added by creating adapters, not modifying core
- Messaging can swap channels without code changes
- Context evolves without breaking existing code

---

## Quick Reference: "Can This File Import X?"

| File Location | Can Import `adapters`? | Can Import `core`? | Can Import FastAPI? | Can Import SDKs? |
|---------------|------------------------|--------------------|---------------------|------------------|
| `registries/` | Only in `register_defaults()` | No | No | No |
| `adapters/` | No | No | No | Yes (for that adapter) |
| `core/` (future) | **NO** | — | **NO** | **NO** |
| `messaging/` (future) | No (use registries) | Yes | No | No (use registries/adapters) |
| `context/` (future) | No | Optional | No | No |
| `main.py` | Yes | No | Yes | No (use adapters) |
| `middleware/` | No | No | Yes (Starlette) | No |

---

*Document version: 1.0*  
*Last updated: Stage 03 boundary definition*
