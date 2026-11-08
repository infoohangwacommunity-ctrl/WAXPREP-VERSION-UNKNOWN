"""
Contract Tests - Stage 05

Contract tests verify that all adapter implementations satisfy their port protocols.

Pattern:
1. Define a contract suite for each port
2. Run the same suite against every implementation of that port
3. Parameterize tests over all implementations

This ensures:
- Every required method exists and is callable
- Async methods are coroutines where required
- Adapters return expected types
- Adapters raise/return expected errors on invalid input
- Capability declarations match actual behavior
"""
