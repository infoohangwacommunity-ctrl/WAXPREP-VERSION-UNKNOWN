"""
Architectural Fitness Tests - Stage 03

Permanent tests that assert structural properties remain true.
These tests run on every pull request and block merge on failure.

Tests in this package verify:
1. Domain purity (no external imports in domain)
2. Layer dependencies (one-directional only)
3. Adapter isolation (no cross-adapter imports)
4. Composition root protection (only main.py wires all layers)
5. No cycles in the import graph
"""
