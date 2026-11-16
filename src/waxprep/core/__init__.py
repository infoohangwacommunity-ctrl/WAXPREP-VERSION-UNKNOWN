"""
WaxPrep Core - Pure Logic & Protocols

This package contains the APPLICATION'S CORE:
- Domain protocols and interfaces
- Pure business logic (no infrastructure)
- Rules that don't depend on channels, models, or databases

BOUNDARY RULES (STRICT):
- NO FastAPI imports
- NO WhatsApp/Telegram/channel specifics
- NO database/ORM code
- NO adapter implementations
- NO HTTP handling
- NO imports from any waxprep.* package (messaging, context, services, config)

Dependencies may ONLY point inward (pure domain types).
Outer layers (messaging, adapters, services, main) depend on core.
Core NEVER knows about outer layers.

This is the innermost layer. All other packages depend on it.
"""
