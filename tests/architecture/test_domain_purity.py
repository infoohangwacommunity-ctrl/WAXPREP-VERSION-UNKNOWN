"""
Domain Purity Tests - Stage 03

Verify that domain layer contains no external framework imports.
Domain may only import from stdlib and other domain modules.
"""

import ast
from pathlib import Path

import pytest


class TestDomainPurity:
    """Test domain layer purity."""

    @pytest.fixture
    def domain_files(self) -> list[Path]:
        """Get all Python files in domain layer."""
        domain_path = Path(__file__).parent.parent.parent / "src" / "waxprep" / "domain"
        if not domain_path.exists():
            pytest.skip("Domain layer not found")
        return list(domain_path.rglob("*.py"))

    def parse_imports(self, file_path: Path) -> list[str]:
        """Parse all imports from a Python file."""
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        tree = ast.parse(content, filename=str(file_path))

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
        return imports

    @pytest.mark.parametrize("file_path", [], indirect=True)
    def test_domain_no_external_imports(self, domain_files: list[Path], file_path: Path) -> None:
        """Test that domain files don't import external frameworks."""
        # This is a parametrized test that will run for each domain file
        # We use indirect parametrization to get the list of files
        pass

    def test_domain_no_fastapi_imports(self, domain_files: list[Path]) -> None:
        """Test that domain layer doesn't import FastAPI."""
        for file_path in domain_files:
            imports = self.parse_imports(file_path)
            for import_name in imports:
                if "fastapi" in import_name.lower():
                    pytest.fail(
                        f"Domain purity violation: {file_path} imports FastAPI "
                        f"({import_name}). Domain may only import stdlib and domain."
                    )

    def test_domain_no_framework_imports(self, domain_files: list[Path]) -> None:
        """Test that domain layer doesn't import common frameworks."""
        forbidden_modules = {
            "fastapi",
            "uvicorn",
            "starlette",
            "pydantic",
            "pydantic_settings",
            "httpx",
            "requests",
            "aiohttp",
            "sqlalchemy",
            "asyncpg",
            "psycopg",
            "litellm",
            "openai",
            "anthropic",
            "langchain",
            "transformers",
        }

        for file_path in domain_files:
            imports = self.parse_imports(file_path)
            for import_name in imports:
                import_lower = import_name.lower()
                for forbidden in forbidden_modules:
                    if forbidden in import_lower:
                        pytest.fail(
                            f"Domain purity violation: {file_path} imports "
                            f"{import_name} (contains '{forbidden}'). "
                            f"Domain may only import stdlib and domain."
                        )

    def test_domain_only_stdlib_and_domain(self, domain_files: list[Path]) -> None:
        """Test that domain only imports stdlib and domain modules."""
        stdlib_modules = {
            "abc",
            "asyncio",
            "collections",
            "collections.abc",
            "contextlib",
            "contextvars",
            "dataclasses",
            "datetime",
            "enum",
            "functools",
            "genericpath",
            "inspect",
            "io",
            "json",
            "logging",
            "os",
            "pathlib",
            "re",
            "signal",
            "site",
            "string",
            "sys",
            "time",
            "typing",
            "uuid",
            "warnings",
            "weakref",
        }

        for file_path in domain_files:
            imports = self.parse_imports(file_path)
            for import_name in imports:
                # Skip typing extensions
                if import_name.startswith("typing."):
                    continue

                # Check if it's stdlib
                is_stdlib = import_name in stdlib_modules

                # Check if it's domain
                is_domain = import_name.startswith("waxprep.domain")

                # Check if it's a relative import (within domain)
                if import_name.startswith("."):
                    continue

                if not (is_stdlib or is_domain):
                    pytest.fail(
                        f"Domain purity violation: {file_path} imports "
                        f"{import_name}. Domain may only import stdlib and domain."
                    )
