"""
Pytest Configuration - Root conftest.py - Stage 05

This file contains fixtures that are available to all tests.

Test Layer Structure:
- tests/unit/: Unit tests for domain logic (fastest)
- tests/contract/: Contract tests for port implementations (fast)
- tests/integration/: Integration tests for application lifecycle (slower)
- tests/regression/: Regression tests for known failure modes (varies)
- tests/architecture/: Architectural fitness tests (permanent CI checks)

All tests must be:
1. Isolated (no shared mutable state)
2. Order-independent (pass in random order)
3. Parallelizable (pass with pytest-xdist)
"""

import sys
from pathlib import Path

import pytest

# Add src directory to Python path for imports
src_path = Path(__file__).parent.parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest."""
    # Mark all tests with their layer
    config.addinivalue_line("markers", "unit: Unit tests for domain logic")
    config.addinivalue_line("markers", "contract: Contract tests for port implementations")
    config.addinivalue_line("markers", "integration: Integration tests for application lifecycle")
    config.addinivalue_line("markers", "regression: Regression tests for known failure modes")
    config.addinivalue_line("markers", "architecture: Architectural fitness tests")


# Global fixtures available to all tests


@pytest.fixture
def anyio_backend() -> str:
    """Use asyncio backend for anyio."""
    return "asyncio"
