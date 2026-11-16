"""
WaxPrep Services - Light Orchestration

Services coordinate between layers without containing business logic:
- Application service coordination
- Use case orchestration
- Integration points

Stage 03: Placeholder for orchestration patterns.

BOUNDARY RULES:
- Depends on core/ protocols
- Depends on messaging/ for message flow
- May depend on registries for lookups
- May depend on context/ for learner state
- Does NOT contain domain logic (that's core/)
- Does NOT contain channel implementations (that's adapters/)

Relationship to main.py:
- main.py lifespan() currently handles registry initialization directly
- When services/ grows, lifespan() should delegate to a bootstrap service
- Services coordinate between messaging/, context/, and registries/

DEPENDENCY DIRECTION: services/ → inner layers (core/, messaging/, context/)
Never the reverse.
"""
