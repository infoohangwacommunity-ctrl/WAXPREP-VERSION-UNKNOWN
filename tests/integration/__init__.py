"""
Integration Tests - Stage 05

Integration tests for application lifecycle and component interactions.

Characteristics:
- Slower than unit tests
- Tests application startup, shutdown, health
- Tests interactions between components
- Runs in CI but not on every save

Fixtures:
- Use function-scoped fixtures by default
- Expensive, read-only resources use broader scopes
"""
