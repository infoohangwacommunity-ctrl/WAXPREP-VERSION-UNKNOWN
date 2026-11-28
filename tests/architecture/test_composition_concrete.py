"""Stage 18 — structural composition boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
ALLOWED_ADAPTER_IMPORTERS = {
    (SOURCE_ROOT / "waxprep" / "composition").resolve(),
    (SOURCE_ROOT / "waxprep" / "registries").resolve(),
    (SOURCE_ROOT / "waxprep" / "adapters").resolve(),
}


def _adapter_import_lines(path: Path, source: str) -> list[int]:
    tree = ast.parse(source, filename=str(path))
    allowed = any(
        path.resolve() == directory or directory in path.resolve().parents
        for directory in ALLOWED_ADAPTER_IMPORTERS
    )
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "waxprep.adapters" or node.module.startswith("waxprep.adapters."):
                if not allowed:
                    lines.append(node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "waxprep.adapters" or alias.name.startswith("waxprep.adapters."):
                    if not allowed:
                        lines.append(node.lineno)
    return lines


def test_only_composition_and_legacy_registries_import_concrete_adapters() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        violations.extend(
            f"{path.relative_to(SOURCE_ROOT)}:{line}"
            for line in _adapter_import_lines(path, path.read_text(encoding="utf-8"))
        )
    assert violations == [], f"concrete adapter imported outside composition: {violations}"


@pytest.mark.parametrize(
    "snippet",
    [
        "from waxprep.adapters.fake_model import FakeModelAdapter\n",
        "import waxprep.adapters.fake_tool\n",
    ],
)
def test_adapter_import_check_catches_synthetic_violations(snippet: str) -> None:
    assert _adapter_import_lines(Path("src/waxprep/services/rogue.py"), snippet)


def test_adapter_import_check_allows_composition() -> None:
    snippet = "from waxprep.adapters.fake_model import FakeModelAdapter\n"
    path = SOURCE_ROOT / "waxprep" / "composition" / "root.py"
    assert _adapter_import_lines(path, snippet) == []


def _global_graph_instances(path: Path, source: str) -> list[int]:
    tree = ast.parse(source, filename=str(path))
    lines: list[int] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        value = node.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if value.func.id in {"DependencyGraph", "CompositionRoot"}:
                lines.append(node.lineno)
    return lines


def test_no_global_dependency_graph_or_composition_root() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        violations.extend(
            f"{path.relative_to(SOURCE_ROOT)}:{line}"
            for line in _global_graph_instances(path, path.read_text(encoding="utf-8"))
        )
    assert violations == [], f"global composition/service-locator state: {violations}"


def test_global_graph_check_catches_synthetic_violation() -> None:
    source = "graph = DependencyGraph()\nroot = CompositionRoot(settings)\n"
    assert _global_graph_instances(Path("rogue.py"), source) == [1, 2]
