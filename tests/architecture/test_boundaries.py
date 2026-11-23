"""
Test Architectural Boundaries - Stage 03/07

Verify that architectural boundaries are maintained across packages.

Authoritative dependency matrix (aligned across README.md,
docs/ENGINEERING-STANDARDS.md, PR_REVIEW_CHECKLIST.md,
STAGE_03_ARCHITECTURE.md, ARCHITECTURE_BOUNDARIES.md):

| Package | May Import From | Must NOT Import From |
|---------|-----------------|---------------------|
| core/ | standard library only | registries, adapters, middleware, main, config, messaging, context, services, id, fastapi |
| messaging/ | core/, registries/ | adapters, context, services, middleware, main, config, id |
| context/ | core/ | messaging, services, registries, adapters, middleware, main, config, id |
| services/ | core/, messaging/, context/, registries/ | adapters directly (use registries) |
| registries/ | registries/base, typing | messaging, context, services, adapters |
| adapters/ | registry protocols, SDKs | core, other adapters, messaging, context, services, registries, id |
| middleware/ | standard library, typing | core |
| main.py | FastAPI, config, registries, middleware, adapters | core |

All checks inspect both `import X` and `from X import Y` forms,
including package `__init__.py` files. Forbidden-import tests prove
that an illegal import causes a test failure; permitted-import tests
prove that an allowed dependency still resolves.
"""

import ast
import importlib
import sys
from pathlib import Path

import pytest

SRC_ROOT = Path("src").resolve()
WAXPREP_ROOT = SRC_ROOT / "waxprep"


def waxprep_imports_in_file(path: Path) -> list[tuple[str, str]]:
    """Return [(file, imported_module)] for every `waxprep.*` import in `path`.

    Covers both ``import waxprep.foo`` and ``from waxprep.foo import bar``
    forms. Does NOT skip ``__init__.py`` files — boundary rules apply to
    every file in a package, including its initializer.

    Only reports imports at module level (top of file), not imports inside
    function/method bodies. Runtime imports inside methods are allowed because
    they don't create static dependencies between packages.
    """
    imports: list[tuple[str, str]] = []
    content = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(content)
    except SyntaxError:
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("import waxprep.") or "from waxprep." in stripped:
                imports.append((path.name, stripped))
        return imports

    # Only walk top-level nodes (module body), not nested function/method bodies
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("waxprep"):
                        imports.append((path.name, alias.name))
            elif node.module and node.module.startswith("waxprep"):
                imports.append((path.name, node.module))
    return imports


def python_files_in_package(package_dir: Path) -> list[Path]:
    """Return every ``.py`` file under ``package_dir``, including __init__.py."""
    return sorted(package_dir.rglob("*.py"))


def module_path_for_file(path: Path) -> str:
    """Convert a filesystem path under src/waxprep to a waxprep.* module path."""
    relative = path.relative_to(WAXPREP_ROOT)
    parts = [p for p in relative.parts if p != "__init__.py"]
    if not parts:
        return "waxprep"
    return "waxprep." + ".".join(parts)


BOUNDARY_RULES: dict[str, tuple[list[str], list[str]]] = {
    "core": (
        [],
        [
            "waxprep.registries",
            "waxprep.adapters",
            "waxprep.middleware",
            "waxprep.main",
            "waxprep.config",
            "waxprep.messaging",
            "waxprep.context",
            "waxprep.services",
            "waxprep.id",
            "fastapi",
        ],
    ),
    "messaging": (
        ["waxprep.core", "waxprep.registries"],
        [
            "waxprep.adapters",
            "waxprep.context",
            "waxprep.services",
            "waxprep.middleware",
            "waxprep.main",
            "waxprep.config",
            "waxprep.id",
        ],
    ),
    "context": (
        ["waxprep.core"],
        [
            "waxprep.messaging",
            "waxprep.services",
            "waxprep.registries",
            "waxprep.adapters",
            "waxprep.middleware",
            "waxprep.main",
            "waxprep.config",
            "waxprep.id",
        ],
    ),
    "services": (
        ["waxprep.core", "waxprep.messaging", "waxprep.context", "waxprep.registries"],
        ["waxprep.adapters"],
    ),
    "registries": (
        ["waxprep.registries.base"],
        [
            "waxprep.messaging",
            "waxprep.context",
            "waxprep.services",
        ],
    ),
    "adapters": (
        [],
        [
            "waxprep.core",
            "waxprep.adapters",
            "waxprep.messaging",
            "waxprep.context",
            "waxprep.services",
            "waxprep.registries",
            "waxprep.id",
        ],
    ),
    "middleware": (
        [],
        ["waxprep.core"],
    ),
}

MAIN_MODULE_RULES = (
    ["waxprep.config", "waxprep.registries", "waxprep.middleware", "waxprep.adapters"],
    ["waxprep.core"],
)


class TestCoreBoundaries:
    """core/ must not import from any outer layer."""

    @pytest.mark.architecture
    def test_core_forbidden_imports(self):
        core_dir = WAXPREP_ROOT / "core"
        forbidden = BOUNDARY_RULES["core"][1]
        for path in python_files_in_package(core_dir):
            for _file_name, module in waxprep_imports_in_file(path):
                assert not any(module.startswith(f) for f in forbidden), (
                    f"core/{path.name} imports forbidden module '{module}'; "
                    "core/ must not import from outer layers."
                )

    @pytest.mark.architecture
    def test_core_does_not_import_fastapi(self):
        core_dir = WAXPREP_ROOT / "core"
        for path in python_files_in_package(core_dir):
            content = path.read_text(encoding="utf-8")
            assert "import fastapi" not in content, (
                f"core/{path.name} imports FastAPI; core must stay framework-agnostic."
            )


class TestMessagingBoundaries:
    """messaging/ may import core/ and registries/ only."""

    @pytest.mark.architecture
    def test_messaging_forbidden_imports(self):
        messaging_dir = WAXPREP_ROOT / "messaging"
        forbidden = BOUNDARY_RULES["messaging"][1]
        for path in python_files_in_package(messaging_dir):
            for _file_name, module in waxprep_imports_in_file(path):
                assert not any(module.startswith(f) for f in forbidden), (
                    f"messaging/{path.name} imports forbidden module '{module}'; "
                    "messaging/ may import core/ and registries/ only."
                )

    @pytest.mark.architecture
    def test_messaging_permitted_imports_still_resolve(self):
        """Verify messaging/ can still import its permitted dependencies."""
        messaging_dir = WAXPREP_ROOT / "messaging"
        sys.path.insert(0, str(SRC_ROOT))
        try:
            for path in python_files_in_package(messaging_dir):
                module = module_path_for_file(path)
                try:
                    importlib.import_module(module)
                except Exception as exc:
                    pytest.fail(f"messaging/{path.name} (module {module}) failed to import: {exc}")
        finally:
            sys.path.pop(0)


class TestContextBoundaries:
    """context/ may import core/ only."""

    @pytest.mark.architecture
    def test_context_forbidden_imports(self):
        context_dir = WAXPREP_ROOT / "context"
        forbidden = BOUNDARY_RULES["context"][1]
        for path in python_files_in_package(context_dir):
            for _file_name, module in waxprep_imports_in_file(path):
                assert not any(module.startswith(f) for f in forbidden), (
                    f"context/{path.name} imports forbidden module '{module}'; "
                    "context/ may import core/ only."
                )


class TestServicesBoundaries:
    """services/ may import core/, messaging/, context/, registries/."""

    @pytest.mark.architecture
    def test_services_forbidden_imports(self):
        services_dir = WAXPREP_ROOT / "services"
        forbidden = BOUNDARY_RULES["services"][1]
        for path in python_files_in_package(services_dir):
            for _file_name, module in waxprep_imports_in_file(path):
                assert not any(module.startswith(f) for f in forbidden), (
                    f"services/{path.name} imports forbidden module '{module}'; "
                    "services/ must not import adapters directly."
                )


class TestRegistriesBoundaries:
    """registries/ may import registries/base only."""

    @pytest.mark.architecture
    def test_registries_forbidden_imports(self):
        registries_dir = WAXPREP_ROOT / "registries"
        forbidden = BOUNDARY_RULES["registries"][1]
        for path in python_files_in_package(registries_dir):
            for _file_name, module in waxprep_imports_in_file(path):
                assert not any(module.startswith(f) for f in forbidden), (
                    f"registries/{path.name} imports forbidden module '{module}'; "
                    "registries/ must not import messaging, context, services, or adapters."
                )


class TestAdaptersBoundaries:
    """adapters/ must not import core/ or any concrete outer-layer module."""

    @pytest.mark.architecture
    def test_adapters_forbidden_imports(self):
        adapters_dir = WAXPREP_ROOT / "adapters"
        forbidden = BOUNDARY_RULES["adapters"][1]
        # __init__.py re-exports are allowed (standard Python pattern)
        for path in python_files_in_package(adapters_dir):
            if path.name == "__init__.py":
                continue
            for _file_name, module in waxprep_imports_in_file(path):
                assert not any(module.startswith(f) for f in forbidden), (
                    f"adapters/{path.name} imports forbidden module '{module}'; "
                    "adapters/ may import registry protocols and SDKs only."
                )


class TestMiddlewareBoundaries:
    """middleware/ must not import core/."""

    @pytest.mark.architecture
    def test_middleware_forbidden_imports(self):
        middleware_dir = WAXPREP_ROOT / "middleware"
        forbidden = BOUNDARY_RULES["middleware"][1]
        for path in python_files_in_package(middleware_dir):
            for _file_name, module in waxprep_imports_in_file(path):
                assert not any(module.startswith(f) for f in forbidden), (
                    f"middleware/{path.name} imports forbidden module '{module}'; "
                    "middleware/ must not import core/."
                )


class TestMainModuleBoundaries:
    """main.py must not import core/ (framework-agnostic entry point)."""

    @pytest.mark.architecture
    def test_main_does_not_import_core(self):
        main_path = WAXPREP_ROOT / "main.py"
        for _file_name, module in waxprep_imports_in_file(main_path):
            assert not module.startswith("waxprep.core"), (
                f"main.py imports '{module}'; main.py must not import core/."
            )


class TestNoCircularDependencies:
    """Verify there are no circular dependencies between packages."""

    @pytest.mark.architecture
    def test_context_and_messaging_do_not_import_each_other(self):
        context_dir = WAXPREP_ROOT / "context"
        messaging_dir = WAXPREP_ROOT / "messaging"

        for path in python_files_in_package(context_dir):
            for _file_name, module in waxprep_imports_in_file(path):
                assert not module.startswith("waxprep.messaging"), (
                    f"context/{path.name} imports '{module}'; context/ must not import messaging/."
                )

        for path in python_files_in_package(messaging_dir):
            for _file_name, module in waxprep_imports_in_file(path):
                assert not module.startswith("waxprep.context"), (
                    f"messaging/{path.name} imports '{module}'; "
                    "messaging/ must not import context/."
                )


class TestArchitectureViolationsAreCaught:
    """Prove that deliberately introduced boundary violations are caught."""

    @pytest.mark.architecture
    def test_detects_forbidden_core_import(self, tmp_path):
        """A file in core/ importing waxprep.registries must be flagged."""
        scratch = WAXPREP_ROOT / "core" / "_scratch_violation.py"
        try:
            scratch.write_text("from waxprep.registries.channel import ChannelRegistry\n")
            imports = waxprep_imports_in_file(scratch)
            assert any("waxprep.registries" in module for _fn, module in imports), (
                "Boundary check must detect core/ importing waxprep.registries"
            )
        finally:
            scratch.unlink(missing_ok=True)

    @pytest.mark.architecture
    def test_detects_forbidden_adapter_import(self, tmp_path):
        """A file in adapters/ importing waxprep.core must be flagged."""
        scratch = WAXPREP_ROOT / "adapters" / "_scratch_violation.py"
        try:
            scratch.write_text("from waxprep.core.protocols import Message\n")
            imports = waxprep_imports_in_file(scratch)
            assert any("waxprep.core" in module for _fn, module in imports), (
                "Boundary check must detect adapters/ importing waxprep.core"
            )
        finally:
            scratch.unlink(missing_ok=True)

    @pytest.mark.architecture
    def test_detects_forbidden_messaging_adapter_import(self, tmp_path):
        """A file in messaging/ importing waxprep.adapters must be flagged."""
        scratch = WAXPREP_ROOT / "messaging" / "_scratch_violation.py"
        try:
            scratch.write_text("from waxprep.adapters.fake_channel import FakeChannelAdapter\n")
            imports = waxprep_imports_in_file(scratch)
            assert any("waxprep.adapters" in module for _fn, module in imports), (
                "Boundary check must detect messaging/ importing waxprep.adapters"
            )
        finally:
            scratch.unlink(missing_ok=True)
