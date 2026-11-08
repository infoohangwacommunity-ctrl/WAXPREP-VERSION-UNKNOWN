"""
Unit Tests - Stage 05

Unit tests for pure domain logic.

Characteristics:
- Fastest test layer
- Tests domain models, value objects, and pure functions
- No external dependencies (no adapters, no infrastructure)
- Runs on every save in IDE
- Runs on every commit in CI

Fixtures:
- Use function-scoped fixtures by default
- No shared mutable state
- Each test constructs its own test data
"""
