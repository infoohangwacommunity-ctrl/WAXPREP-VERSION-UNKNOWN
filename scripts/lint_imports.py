#!/usr/bin/env python3
"""
Custom Import Linter - Stage 03

Enforces hexagonal architecture import rules.
This is a simple Python-based linter that doesn't require external packages.

Contracts enforced:
1. Layers: Strict one-directional dependencies (domain -> application -> adapters/infrastructure)
2. Domain purity: domain/ may only import stdlib and domain/
3. Adapter isolation: adapters.* modules must not depend on each other
4. Composition-root protection: Only main.py may import across all layers
5. No cycles: No circular dependencies

Usage:
    python scripts/lint_imports.py
    python scripts/lint_imports.py --check
    python scripts/lint_imports.py --verbose
"""

import ast
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


class ImportLinter:
    """Custom import linter for hexagonal architecture."""

    def __init__(self, root_path: Path, verbose: bool = False):
        self.root_path = root_path
        self.verbose = verbose
        self.violations: list[str] = []
        self.import_graph: dict[str, set[str]] = defaultdict(set)
        self.module_layers: dict[str, str] = {}

    def get_layer(self, module_path: str) -> str:
        """Determine the layer of a module based on its path."""
        if module_path.startswith("waxprep.domain"):
            return "domain"
        elif module_path.startswith("waxprep.application"):
            return "application"
        elif module_path.startswith("waxprep.adapters"):
            return "adapters"
        elif module_path.startswith("waxprep.infrastructure"):
            return "infrastructure"
        elif module_path.startswith("waxprep.registries"):
            return "registries"
        elif module_path == "waxprep.main":
            return "composition_root"
        elif module_path == "waxprep":
            return "root"
        else:
            return "unknown"

    def is_stdlib(self, module: str) -> bool:
        """Check if a module is from the standard library."""
        # Common stdlib modules
        stdlib_modules = {
            "abc", "asyncio", "collections", "contextlib", "contextvars",
            "dataclasses", "datetime", "enum", "functools", "genericpath",
            "inspect", "io", "json", "logging", "os", "pathlib", "re",
            "signal", "site", "string", "sys", "time", "typing", "uuid",
            "warnings", "weakref",
        }
        # Check exact match or if it starts with a stdlib module
        if module in stdlib_modules:
            return True
        if module.startswith("typing."):
            return True
        # Check if it starts with any stdlib module
        for stdlib in stdlib_modules:
            if module.startswith(stdlib + ".") or module.startswith(stdlib + ""):
                return True
        return False

    def is_external(self, module: str) -> bool:
        """Check if a module is external (not part of waxprep)."""
        return not module.startswith("waxprep") and not self.is_stdlib(module)

    def parse_imports(self, file_path: Path) -> list[str]:
        """Parse imports from a Python file."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ast.parse(content, filename=str(file_path))
        except Exception as e:
            self.violations.append(f"Error parsing {file_path}: {e}")
            return []

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
                for alias in node.names:
                    if node.module:
                        imports.append(f"{node.module}.{alias.name}")
                    else:
                        imports.append(alias.name)
        return imports

    def get_module_path(self, import_name: str) -> str:
        """Convert an import name to a module path."""
        if import_name.startswith("waxprep"):
            return import_name
        return import_name

    def check_file(self, file_path: Path) -> None:
        """Check a single Python file for import violations."""
        if not file_path.suffix == ".py":
            return

        # Get relative path from root
        try:
            rel_path = file_path.relative_to(self.root_path / "src")
        except ValueError:
            return

        module_path = str(rel_path).replace("/", ".").replace(".py", "")
        layer = self.get_layer(module_path)
        self.module_layers[module_path] = layer

        imports = self.parse_imports(file_path)
        for import_name in imports:
            # Check ALL imports, not just waxprep imports
            # External imports need to be checked for domain purity
            if import_name.startswith("waxprep") or not self.is_stdlib(import_name):
                if import_name.startswith("waxprep"):
                    imported_module = import_name
                    imported_layer = self.get_layer(imported_module)
                    self.import_graph[module_path].add(imported_module)

                    # Check layer dependencies
                    self.check_layer_dependency(module_path, layer, imported_module, imported_layer)
                else:
                    # External import - check domain purity
                    if layer == "domain" and self.is_external(import_name):
                        self.violations.append(
                            f"Domain purity violation: {module_path} imports external "
                            f"module {import_name}. Domain may only import stdlib and domain."
                        )

    def check_layer_dependency(
        self,
        source_module: str,
        source_layer: str,
        target_module: str,
        target_layer: str,
    ) -> None:
        """Check if a layer dependency is allowed."""
        # Allowed dependencies:
        # - domain: only stdlib and domain
        # - application: domain, application
        # - adapters: domain, application, adapters (but not cross-adapter)
        # - infrastructure: domain, application, infrastructure
        # - registries: domain, application (maybe adapters)
        # - main (composition root): ALL

        if source_layer == "domain":
            if target_layer != "domain" and not self.is_stdlib(target_module):
                if self.is_external(target_module):
                    self.violations.append(
                        f"Domain purity violation: {source_module} imports external "
                        f"module {target_module}. Domain may only import stdlib and domain."
                    )
                else:
                    self.violations.append(
                        f"Domain purity violation: {source_module} imports {target_module} "
                        f"({target_layer}). Domain may only import stdlib and domain."
                    )

        elif source_layer == "application":
            if target_layer in ("adapters", "infrastructure"):
                self.violations.append(
                    f"Layer violation: {source_module} ({source_layer}) imports "
                    f"{target_module} ({target_layer}). Application may only import domain and application."
                )

        elif source_layer == "adapters":
            if target_layer in ("adapters",):
                # Check if it's a cross-adapter import
                if not target_module.startswith(source_module):
                    self.violations.append(
                        f"Adapter isolation violation: {source_module} imports "
                        f"{target_module}. Adapters must not depend on each other."
                    )
            elif target_layer == "infrastructure":
                self.violations.append(
                    f"Layer violation: {source_module} ({source_layer}) imports "
                    f"{target_module} ({target_layer}). Adapters may not import infrastructure."
                )

        elif source_layer == "infrastructure":
            if target_layer == "adapters":
                self.violations.append(
                    f"Layer violation: {source_module} ({source_layer}) imports "
                    f"{target_module} ({target_layer}). Infrastructure may not import adapters."
                )

    def check_composition_root(self) -> None:
        """Check that only main.py imports across all layers."""
        # Check all modules that import from multiple layers
        for module_path, imports in self.import_graph.items():
            if module_path == "waxprep.main":
                # main.py is allowed to import anything
                continue
            
            # Check if this module imports from multiple layers
            layers_imported = set()
            for imp in imports:
                if imp.startswith("waxprep"):
                    layer = self.get_layer(imp)
                    layers_imported.add(layer)
            
            # If importing from more than one layer, it might be doing composition
            if len(layers_imported) > 1 and module_path != "waxprep.main":
                self.violations.append(
                    f"Composition root violation: {module_path} imports from multiple layers "
                    f"({', '.join(sorted(layers_imported))}). Only main.py should connect layers."
                )

    def check_cycles(self) -> None:
        """Check for circular dependencies."""
        # Simple cycle detection using depth-first search
        visited = set()
        path = set()

        def has_cycle(module: str) -> bool:
            if module in path:
                return True
            if module in visited:
                return False

            visited.add(module)
            path.add(module)

            for dependency in self.import_graph.get(module, set()):
                if dependency in self.import_graph:
                    if has_cycle(dependency):
                        return True

            path.remove(module)
            return False

        for module in self.import_graph:
            if has_cycle(module):
                self.violations.append(f"Cycle detected involving: {module}")

    def check_all_files(self) -> None:
        """Check all Python files in the src directory."""
        src_path = self.root_path / "src" / "waxprep"
        if not src_path.exists():
            self.violations.append(f"Source directory not found: {src_path}")
            return

        for py_file in src_path.rglob("*.py"):
            self.check_file(py_file)

        # Additional checks
        self.check_composition_root()
        self.check_cycles()

    def run(self, check_all: bool = True) -> tuple[int, list[str]]:
        """Run the linter and return exit code and violations."""
        if check_all:
            self.check_all_files()

        if self.verbose:
            print(f"Checked {len(self.module_layers)} modules")
            print(f"Found {len(self.violations)} violations")
            for violation in self.violations:
                print(f"  - {violation}")

        return (1 if self.violations else 0, self.violations)


def main() -> int:
    """Main entry point for the import linter."""
    root_path = Path(__file__).parent.parent
    if not root_path.exists():
        root_path = Path.cwd()

    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    check_only = "--check" in sys.argv
    
    # Check if a specific file is provided
    target_file = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
        target_file = Path(sys.argv[1])

    linter = ImportLinter(root_path, verbose=verbose or check_only)
    
    if target_file and target_file.exists():
        # Check only the specified file
        linter.check_file(target_file)
        exit_code, violations = linter.run(check_all=False)
    else:
        # Check all files
        exit_code, violations = linter.run(check_all=True)

    if violations:
        print("Import linting violations found:")
        for violation in violations:
            print(f"  ERROR: {violation}")
        print(f"\nFound {len(violations)} violations.")
        return 1

    if check_only or verbose:
        print("Import linting passed: No violations found.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
