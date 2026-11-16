"""
WaxPrep Messaging - Message Handling & Conversation Flow

This package handles natural message processing:
- Incoming message normalization
- Conversation flow management
- Handler dispatching

Stage 03: Placeholder structure. Will evolve as messaging requirements arrive.

BOUNDARY RULES:
- Depends on core/ protocols (never the reverse)
- May depend on registries for channel/model lookups
- Does NOT contain channel-specific implementations (those stay in adapters/)
- Does NOT contain AI model calls (those go through model registry)
"""
