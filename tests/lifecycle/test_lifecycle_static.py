"""Structural lifecycle checks (Stage 16).

Line coverage cannot prove that no future module creates an uncontrolled task.
This module parses the source tree and enforces the ownership boundary
structurally, and includes an adversarial case showing the check catches a
violation.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
ALLOWED_TASK_OWNER = SOURCE_ROOT / "waxprep" / "lifecycle" / "background.py"
ALLOWED_STATE_OWNERS = {
    (SOURCE_ROOT / "waxprep" / "lifecycle" / "manager.py").resolve(),
    (SOURCE_ROOT / "waxprep" / "lifecycle" / "states.py").resolve(),
}
TASK_APIS = {"create_task", "ensure_future"}


def _unmanaged_task_lines(path: Path, source: str) -> list[int]:
    tree = ast.parse(source, filename=str(path))
    allowed = path.resolve() == ALLOWED_TASK_OWNER.resolve()
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr not in TASK_APIS:
            continue
        if not allowed:
            lines.append(node.lineno)
    return lines


def test_only_the_supervisor_creates_tasks() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        violations.extend(
            f"{path.relative_to(SOURCE_ROOT)}:{line}"
            for line in _unmanaged_task_lines(path, path.read_text(encoding="utf-8"))
        )
    assert violations == [], f"unmanaged task creation outside supervisor: {violations}"


def test_structural_check_detects_a_synthetic_violation() -> None:
    synthetic = "import asyncio\n\nasync def rogue():\n    asyncio.create_task(work())\n"
    lines = _unmanaged_task_lines(Path("rogue.py"), synthetic)
    assert lines == [4]


def test_structural_check_allows_the_supervisor(tmp_path: Path) -> None:
    synthetic = "import asyncio\n\nasync def owned():\n    asyncio.create_task(work())\n"
    assert _unmanaged_task_lines(ALLOWED_TASK_OWNER, synthetic) == []


def _transition_lines(path: Path, source: str) -> list[int]:
    tree = ast.parse(source, filename=str(path))
    allowed = path.resolve() in ALLOWED_STATE_OWNERS
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if not isinstance(function, ast.Attribute) or function.attr != "transition_to":
            continue
        if not allowed:
            lines.append(node.lineno)
    return lines


def test_lifecycle_state_is_mutated_only_by_its_owner() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        violations.extend(
            f"{path.relative_to(SOURCE_ROOT)}:{line}"
            for line in _transition_lines(path, path.read_text(encoding="utf-8"))
        )
    assert violations == [], f"state transition outside lifecycle owner: {violations}"


def test_state_ownership_check_detects_a_synthetic_violation() -> None:
    synthetic = "def rogue(lifecycle):\n    lifecycle.transition_to(target)\n"
    assert _transition_lines(Path("rogue.py"), synthetic) == [2]
