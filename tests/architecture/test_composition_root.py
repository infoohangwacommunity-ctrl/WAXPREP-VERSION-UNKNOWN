"""
Composition Root Tests - Stage 03

Verify that main.py is the only composition root.
"""

import ast
from pathlib import Path

import pytest


class TestCompositionRoot:
    """Test composition root protection."""

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

    def test_main_imports_all_layers(self) -> None:
        """Test that main.py imports from all necessary layers."""
        modules = self.get_all_modules()
        main_path = modules.get("waxprep.main")
        if not main_path:
            pytest.skip("main.py not found")

        imports = self.parse_imports(main_path)
        imported_layers = set()
        for import_name in imports:
            if import_name.startswith("waxprep"):
                layer = self.get_layer(import_name)
                if layer != "unknown":
                    imported_layers.add(layer)

        # main.py should import from domain, application, adapters, infrastructure, registries
        expected_layers = {"domain", "application", "adapters", "infrastructure", "registries"}
        if not expected_layers.issubset(imported_layers):
            pytest.fail(
                f"Composition root incomplete: main.py should import from "
                f"{expected_layers}, but only imports from {imported_layers}"
            )

    def test_no_other_module_imports_all_layers(self) -> None:
        """Test that no other module imports from all layers."""
        modules = self.get_all_modules()

        for module_path, file_path in modules.items():
            if module_path == "waxprep.main" or module_path == "main":
                continue  # main.py is the composition root

            imports = self.parse_imports(file_path)
            imported_layers = set()
            for import_name in imports:
                if import_name.startswith("waxprep"):
                    layer = self.get_layer(import_name)
                    if layer != "unknown":
                        imported_layers.add(layer)

            # Check if this module imports from both adapters and infrastructure
            # (which would be a composition root violation)
            if "adapters" in imported_layers and "infrastructure" in imported_layers:
                pytest.fail(
                    f"Composition root violation: {module_path} imports from "
                    f"both adapters and infrastructure. "
                    f"Only main.py should wire all layers together."
                )

    def test_main_wires_registries(self) -> None:
        """Test that main.py wires up the registries."""
        modules = self.get_all_modules()
        main_path = modules.get("waxprep.main")
        if not main_path:
            pytest.skip("main.py not found")

        with open(main_path, encoding="utf-8") as f:
            content = f.read()

        # Check that main.py imports and uses registries
        assert "get_channel_registry" in content or "ChannelRegistry" in content
        assert "get_model_registry" in content or "ModelRegistry" in content
        assert "get_tool_registry" in content or "ToolRegistry" in content
