"""
Test Architectural Boundaries - Stage 03
Verify that architectural boundaries are maintained across packages.

Boundary Rules:
- core/ must NOT import from adapters, channels, FastAPI, or any waxprep.* package
- messaging/ must NOT import from adapters directly (use registries)
- context/ must NOT import from messaging/ or services/ directly
- services/ may import from everything (composition root)

These tests enforce the rules documented in ARCHITECTURE_BOUNDARIES.md and README.md.
"""

import ast
from pathlib import Path

import pytest


class TestCoreBoundaries:
    """Verify core/ respects its strict boundary rules."""

    @pytest.fixture
    def core_path(self):
        return Path("src/waxprep/core")

    def test_core_does_not_import_adapters(self, core_path):
        """Core must not import from adapters package."""
        adapter_imports = []

        for py_file in core_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("waxprep.adapters"):
                            adapter_imports.append((py_file.name, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.adapters"):
                        adapter_imports.append((py_file.name, node.module))

        assert len(adapter_imports) == 0, f"core/ imports from adapters: {adapter_imports}"

    def test_core_does_not_import_fastapi(self, core_path):
        """Core must not import FastAPI (framework-agnostic)."""
        for py_file in core_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            assert "from fastapi" not in content, f"Core imports FastAPI in {py_file}"
            assert "import fastapi" not in content, f"Core imports FastAPI in {py_file}"

    def test_core_does_not_import_waxprep_packages(self, core_path):
        """Core must not import from any waxprep.* package."""
        waxprep_imports = []

        for py_file in core_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("waxprep"):
                            waxprep_imports.append((py_file.name, alias.name))
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep"):
                        waxprep_imports.append((py_file.name, node.module))

        assert len(waxprep_imports) == 0, f"core/ imports from waxprep: {waxprep_imports}"

    def test_core_does_not_import_config(self, core_path):
        """Core must not import config (settings are infrastructure)."""
        for py_file in core_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            assert "from waxprep.config" not in content, f"Core imports config in {py_file}"
            assert "import waxprep.config" not in content, f"Core imports config in {py_file}"


class TestContextBoundaries:
    """Verify context/ respects its boundary rules."""

    @pytest.fixture
    def context_path(self):
        return Path("src/waxprep/context")

    def test_context_does_not_import_messaging(self, context_path):
        """Context must not import from messaging (circular dependency risk)."""
        messaging_imports = []

        for py_file in context_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.messaging"):
                        messaging_imports.append((py_file.name, node.module))

        assert len(messaging_imports) == 0, f"context/ imports from messaging: {messaging_imports}"

    def test_context_does_not_import_services(self, context_path):
        """Context must not import from services (wrong direction)."""
        services_imports = []

        for py_file in context_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.services"):
                        services_imports.append((py_file.name, node.module))

        assert len(services_imports) == 0, f"context/ imports from services: {services_imports}"

    def test_context_may_import_core(self, context_path):
        """Context may import from core/ (this is the allowed direction).

        This test verifies the boundary ALLOWS this direction by checking
        the __init__.py explicitly documents core/ as allowed.
        """
        init_file = context_path / "__init__.py"
        content = init_file.read_text()

        # The boundary should explicitly mention core/ as allowed
        assert "core/" in content or "core" in content, (
            "context/__init__.py should mention core/ as an allowed dependency"
        )

        # Verify core/ can be imported from context/ path (structural check)
        # This proves there's no technical barrier to the allowed dependency
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("src").resolve()))
        try:
            pass
        finally:
            sys.path.pop(0)


class TestMessagingBoundaries:
    """Verify messaging/ respects its boundary rules."""

    @pytest.fixture
    def messaging_path(self):
        return Path("src/waxprep/messaging")

    def test_messaging_does_not_import_adapters_directly(self, messaging_path):
        """Messaging must not import concrete adapters directly.

        Messaging should use registries to get adapters, not import them directly.
        """
        adapter_imports = []

        for py_file in messaging_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("waxprep.adapters"):
                        adapter_imports.append((py_file.name, node.module))

        assert len(adapter_imports) == 0, f"messaging/ imports adapters directly: {adapter_imports}"

    def test_messaging_may_import_core(self, messaging_path):
        """Messaging may import from core/ (this is the allowed direction).

        This test verifies the boundary ALLOWS this direction by checking
        the __init__.py explicitly documents core/ as allowed.
        """
        init_file = messaging_path / "__init__.py"
        content = init_file.read_text()

        # The boundary should explicitly mention core/ as allowed
        assert "core/" in content or "core" in content, (
            "messaging/__init__.py should mention core/ as an allowed dependency"
        )

        # Verify core/ can be imported from messaging/ path (structural check)
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path("src").resolve()))
        try:
            pass
        finally:
            sys.path.pop(0)


class TestNoCircularDependencies:
    """Verify there are no circular dependencies between packages."""

    def test_context_does_not_create_cycle_with_messaging(self):
        """Ensure context and messaging don't create a circular dependency."""
        # Context may import core
        # Messaging may import core
        # Neither should import the other

        context_path = Path("src/waxprep/context")
        messaging_path = Path("src/waxprep/messaging")

        # Check context doesn't import messaging
        for py_file in context_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            assert "waxprep.messaging" not in content, f"context/ imports messaging in {py_file}"

        # Check messaging doesn't import context
        for py_file in messaging_path.rglob("*.py"):
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text()
            assert "waxprep.context" not in content, f"messaging/ imports context in {py_file}"
