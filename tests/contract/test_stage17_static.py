"""Stage 17 — structural contract-bypass checks."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architecture

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
FORBIDDEN_ATTRIBUTES = {"model_construct", "construct"}


def _bypass_lines(source: str) -> list[int]:
    tree = ast.parse(source)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        name = node.func.attr
        if name in FORBIDDEN_ATTRIBUTES:
            lines.append(node.lineno)
        elif name == "model_copy" and any(keyword.arg == "update" for keyword in node.keywords):
            lines.append(node.lineno)
        elif name in {"model_validate", "model_validate_json"}:
            for keyword in node.keywords:
                if keyword.arg == "strict" and isinstance(keyword.value, ast.Constant):
                    if keyword.value.value is False:
                        lines.append(node.lineno)
    return lines


def test_no_contract_bypass_in_source() -> None:
    violations: list[str] = []
    for path in SOURCE_ROOT.rglob("*.py"):
        violations.extend(
            f"{path.relative_to(SOURCE_ROOT)}:{line}"
            for line in _bypass_lines(path.read_text(encoding="utf-8"))
        )
    assert violations == [], f"Pydantic contract bypass: {violations}"


@pytest.mark.parametrize(
    "snippet",
    [
        "Model.model_construct(x=1)\n",
        "Model.construct(x=1)\n",
        "Model.model_copy(update={'x': 1})\n",
        "Model.model_validate(data, strict=False)\n",
        "Model.model_validate_json(text, strict=False)\n",
    ],
)
def test_bypass_check_catches_synthetic_violations(snippet: str) -> None:
    assert _bypass_lines(snippet)


def test_bypass_check_allows_validated_construction() -> None:
    snippet = "Model.model_validate(data)\nModel(x=1)\n"
    assert _bypass_lines(snippet) == []
