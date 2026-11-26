"""Workflow audit tests for Stage 10 (pinning, triggers, jobs, evidence, matrix)."""

from __future__ import annotations

from pathlib import Path

import pytest

from waxprep.ci.acceptance import ADVISORY_JOBS, REQUIRED_JOBS, TEST_CATEGORIES
from waxprep.ci.workflows import (
    MATRIX_EVIDENCE_ARGUMENT,
    audit_workflows,
)

pytestmark = pytest.mark.regression

PINNED = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_workflow(
    *,
    triggers: tuple[str, ...] = ("push", "pull_request", "workflow_dispatch"),
    permissions: bool = True,
    skip_job: str | None = None,
    categories: tuple[str, ...] = TEST_CATEGORIES,
    matrix: bool = True,
    record_evidence: bool = True,
    action: str = PINNED,
) -> str:
    lines = ["name: CI", "on:"]
    lines.extend(f"  {trigger}:" for trigger in triggers)
    if permissions:
        lines.extend(["permissions:", "  contents: read"])
    lines.append("jobs:")

    for job in (*REQUIRED_JOBS, *ADVISORY_JOBS):
        if job.startswith("tests-") or job == skip_job:
            continue
        lines.extend([
            f"  {job}:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            f"      - uses: {action}",
        ])
        if record_evidence:
            lines.append(f"      - run: python -m waxprep.ci.cli record --job {job}")

    if skip_job != "tests":
        lines.extend(["  tests:", "    runs-on: ubuntu-latest"])
        if matrix:
            lines.extend(["    strategy:", "      matrix:", "        category:"])
            lines.extend(f"          - {category}" for category in categories)
        lines.extend(["    steps:", f"      - uses: {action}"])
        if record_evidence:
            lines.append(f"      - run: python -m waxprep.ci.cli record {MATRIX_EVIDENCE_ARGUMENT}")
    return "\n".join(lines) + "\n"


def write_workflow(root: Path, text: str, name: str = "quality-gate.yml") -> None:
    directory = root / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")


def rules(root: Path) -> set[str]:
    return {finding.rule for finding in audit_workflows(root)}


def test_repository_workflows_are_clean() -> None:
    assert audit_workflows(PROJECT_ROOT) == ()


def test_missing_workflow_directory_is_reported(tmp_path: Path) -> None:
    findings = audit_workflows(tmp_path)

    assert [finding.rule for finding in findings] == ["missing-workflows"]


def test_valid_workflow_passes(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow())

    assert audit_workflows(tmp_path) == ()


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, "name: CI\non: [\n")

    assert "workflow-invalid" in rules(tmp_path)


def test_non_mapping_workflow_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, "- just a list\n")

    assert "workflow-invalid" in rules(tmp_path)


def test_missing_permissions_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(permissions=False))

    assert "workflow-permissions" in rules(tmp_path)


def test_missing_jobs_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, "on:\n  push:\npermissions:\n  contents: read\n")

    assert "workflow-invalid" in rules(tmp_path)


def test_workflow_without_triggers_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, "permissions:\n  contents: read\njobs:\n  ci-audit:\n    steps: []\n")

    assert "workflow-invalid" in rules(tmp_path)


@pytest.mark.parametrize("action", ["actions/checkout@v5", "actions/checkout@main"])
def test_mutable_action_reference_is_reported(tmp_path: Path, action: str) -> None:
    write_workflow(tmp_path, build_workflow(action=action))

    assert "action-not-pinned" in rules(tmp_path)


def test_container_action_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(action="docker://alpine:3.20"))

    assert "action-not-pinned" in rules(tmp_path)


def test_local_composite_action_is_allowed(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(action="./.github/actions/ci-evidence"))

    assert audit_workflows(tmp_path) == ()


def test_missing_trigger_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(triggers=("push", "pull_request")))

    assert "missing-trigger" in rules(tmp_path)


def test_missing_required_job_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(skip_job="coverage-gate"))

    assert "missing-job" in rules(tmp_path)


def test_missing_test_matrix_job_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(skip_job="tests"))

    assert "missing-job" in rules(tmp_path)


def test_matrix_without_strategy_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(matrix=False))

    assert "matrix-mismatch" in rules(tmp_path)


def test_matrix_diverging_from_declared_categories_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(categories=("unit", "integration")))

    assert "matrix-mismatch" in rules(tmp_path)


def test_missing_evidence_recording_is_reported(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow(record_evidence=False))

    assert "missing-evidence-recording" in rules(tmp_path)


def test_unreadable_workflow_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_workflow(tmp_path, build_workflow())
    original = Path.read_text

    def deny(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "quality-gate.yml":
            raise OSError("permission denied")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", deny)

    assert "workflow-unreadable" in rules(tmp_path)


def test_findings_are_scoped_to_the_offending_workflow(tmp_path: Path) -> None:
    write_workflow(tmp_path, build_workflow())
    write_workflow(tmp_path, "name: Dependency Review\non:\n  pull_request:\n", "other.yml")

    findings = audit_workflows(tmp_path)

    assert findings
    assert {finding.workflow for finding in findings} == {"other.yml"}
