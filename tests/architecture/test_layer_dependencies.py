"""
Layer Dependency Tests - Stage 03

Verify that layer dependencies follow hexagonal architecture rules.
"""

import ast
from pathlib import Path

import pytest


class TestLayerDependencies:
    """Test layer dependency rules."""

    def get_layer(self, module_path: str) -> str:
        """Determine the layer of a module."""
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

    def get_all_modules(self) -> dict[str, Path]:
        """Get all Python modules in the waxprep package."""
        src_path = Path(__file__).parent.parent.parent / "src" / "waxprep"
        modules = {}
        for py_file in src_path.rglob("*.py"):
            rel_path = py_file.relative_to(src_path)
            module_path = str(rel_path).replace("/", ".").replace(".py", "")
            if module_path == "__init__":
                continue
            if module_path.endswith(".__init__"):
                module_path = module_path[:-9]
            modules[module_path] = py_file
        return modules

    def test_application_only_imports_domain_and_application(
        self,
    ) -> None:
        """Test that application layer only imports domain and application."""
        modules = self.get_all_modules()

        for module_path, file_path in modules.items():
            layer = self.get_layer(module_path)
            if layer != "application":
                continue

            imports = self.parse_imports(file_path)
            for import_name in imports:
                if import_name.startswith("waxprep"):
                    imported_layer = self.get_layer(import_name)
                    if imported_layer in ("adapters", "infrastructure"):
                        pytest.fail(
                            f"Layer violation: {module_path} ({layer}) imports "
                            f"{import_name} ({imported_layer}). "
                            f"Application may only import domain and application."
                        )

    def test_adapters_no_cross_imports(self) -> None:
        """Test that adapters don't import from other adapters."""
        modules = self.get_all_modules()

        for module_path, file_path in modules.items():
            layer = self.get_layer(module_path)
            if layer != "adapters":
                continue

            imports = self.parse_imports(file_path)
            for import_name in imports:
                if import_name.startswith("waxprep.adapters"):
                    # Allow same module imports
                    if not import_name.startswith(module_path):
                        pytest.fail(
                            f"Adapter isolation violation: {module_path} imports "
                            f"{import_name}. Adapters must not depend on each other."
                        )

    def test_infrastructure_no_adapter_imports(self) -> None:
        """Test that infrastructure doesn't import adapters."""
        modules = self.get_all_modules()

        for module_path, file_path in modules.items():
            layer = self.get_layer(module_path)
            if layer != "infrastructure":
                continue

            imports = self.parse_imports(file_path)
            for import_name in imports:
                if import_name.startswith("waxprep.adapters"):
                    pytest.fail(
                        f"Layer violation: {module_path} ({layer}) imports "
                        f"{import_name} (adapters). "
                        f"Infrastructure may not import adapters."
                    )

    def test_only_main_imports_all_layers(self) -> None:
        """Test that only main.py imports across all layers."""
        modules = self.get_all_modules()

        for module_path, file_path in modules.items():
            if module_path == "waxprep.main":
                continue  # main.py is allowed to import anything

            imports = self.parse_imports(file_path)
            imported_layers = set()
            for import_name in imports:
                if import_name.startswith("waxprep"):
                    layer = self.get_layer(import_name)
                    if layer != "unknown":
                        imported_layers.add(layer)

            # If a module imports from more than one layer, it might be a problem
            # unless it's infrastructure which can import domain and application
            layer = self.get_layer(module_path)
            if layer == "infrastructure":
                # Infrastructure can import domain and application
                allowed = {"domain", "application", "infrastructure"}
                if not imported_layers.issubset(allowed):
                    pytest.fail(
                        f"Layer violation: {module_path} ({layer}) imports "
                        f"layers: {imported_layers}. "
                        f"Infrastructure may only import domain, application, and infrastructure."
                    )
