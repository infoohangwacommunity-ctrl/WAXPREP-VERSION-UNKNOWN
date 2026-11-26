"""Static audit of the CI workflow definitions.

The audit protects the integrity of the acceptance system itself: a workflow
that references a mutable action tag, omits least-privilege permissions, drops
a required job, records evidence for the wrong job id or diverges from the
declared test categories would weaken acceptance silently.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from waxprep.ci.acceptance import ADVISORY_JOBS, REQUIRED_JOBS, TEST_CATEGORIES

WORKFLOW_DIRECTORY = Path(".github") / "workflows"
PRIMARY_WORKFLOW = "quality-gate.yml"
REQUIRED_TRIGGERS = ("push", "pull_request", "workflow_dispatch")
MATRIX_EVIDENCE_ARGUMENT = '--job "tests-${{ matrix.category }}"'
PINNED_ACTION = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
USES_LINE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<reference>\S+)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class AuditFinding:
    """One problem found in a workflow definition."""

    workflow: str
    rule: str
    message: str


def _load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _triggers(document: Mapping[Any, Any]) -> Mapping[Any, Any]:
    """Return the parsed ``on`` block.

    PyYAML reads the unquoted key ``on`` as boolean ``True``, so both spellings
    are accepted.
    """
    value = document.get("on", document.get(True))
    return value if isinstance(value, Mapping) else {}


def _check_pinning(name: str, text: str) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for match in USES_LINE.finditer(text):
        reference = match.group("reference").strip("\"'")
        if reference.startswith("./"):
            continue
        if reference.startswith("docker://"):
            findings.append(
                AuditFinding(
                    name, "action-not-pinned", f"container action {reference} is not pinned"
                )
            )
            continue
        if not PINNED_ACTION.match(reference):
            findings.append(
                AuditFinding(
                    name,
                    "action-not-pinned",
                    f"action reference '{reference}' is mutable; pin it to a full commit SHA",
                )
            )
    return findings


def _check_document(name: str, document: Any) -> list[AuditFinding]:
    if not isinstance(document, Mapping):
        return [AuditFinding(name, "workflow-invalid", "workflow is not a YAML mapping")]

    findings: list[AuditFinding] = []
    if "jobs" not in document or not isinstance(document.get("jobs"), Mapping):
        findings.append(AuditFinding(name, "workflow-invalid", "workflow defines no jobs"))
    if "permissions" not in document:
        findings.append(
            AuditFinding(
                name,
                "workflow-permissions",
                "workflow does not declare explicit least-privilege permissions",
            )
        )
    if document.get("on") is None and document.get(True) is None:
        findings.append(AuditFinding(name, "workflow-invalid", "workflow declares no triggers"))
    return findings


def _check_pipeline(name: str, text: str, document: Mapping[Any, Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    triggers = _triggers(document)
    for trigger in REQUIRED_TRIGGERS:
        if trigger not in triggers:
            findings.append(
                AuditFinding(
                    name, "missing-trigger", f"required trigger '{trigger}' is not configured"
                )
            )

    jobs = document.get("jobs")
    job_map: Mapping[Any, Any] = jobs if isinstance(jobs, Mapping) else {}
    for job in (*REQUIRED_JOBS, *ADVISORY_JOBS):
        if job.startswith("tests-"):
            continue
        if job not in job_map:
            findings.append(AuditFinding(name, "missing-job", f"required job '{job}' is absent"))

    findings.extend(_check_matrix(name, job_map))
    findings.extend(_check_evidence_recording(name, text))
    return findings


def _check_matrix(name: str, job_map: Mapping[Any, Any]) -> list[AuditFinding]:
    tests_job = job_map.get("tests")
    if not isinstance(tests_job, Mapping):
        return [AuditFinding(name, "missing-job", "test matrix job 'tests' is absent")]

    strategy = tests_job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, Mapping) else None
    categories = matrix.get("category") if isinstance(matrix, Mapping) else None
    if not isinstance(categories, list):
        return [AuditFinding(name, "matrix-mismatch", "test matrix declares no category list")]

    if tuple(categories) != TEST_CATEGORIES:
        return [
            AuditFinding(
                name,
                "matrix-mismatch",
                f"test matrix categories {tuple(categories)} do not match the declared "
                f"categories {TEST_CATEGORIES}",
            )
        ]
    return []


def _check_evidence_recording(name: str, text: str) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for job in REQUIRED_JOBS:
        if job.startswith("tests-"):
            if MATRIX_EVIDENCE_ARGUMENT not in text:
                findings.append(
                    AuditFinding(
                        name,
                        "missing-evidence-recording",
                        "test matrix does not record per-category evidence",
                    )
                )
            continue
        if f"--job {job}" not in text:
            findings.append(
                AuditFinding(
                    name,
                    "missing-evidence-recording",
                    f"job '{job}' does not record CI evidence",
                )
            )
    for job in ADVISORY_JOBS:
        if f"--job {job}" not in text:
            findings.append(
                AuditFinding(
                    name,
                    "missing-evidence-recording",
                    f"advisory job '{job}' does not record CI evidence",
                )
            )
    return findings


def audit_workflows(root: str | Path = ".") -> tuple[AuditFinding, ...]:
    """Audit every workflow under ``.github/workflows`` and return findings."""
    directory = Path(root) / WORKFLOW_DIRECTORY
    if not directory.is_dir():
        return (
            AuditFinding(str(directory), "missing-workflows", "no workflow directory was found"),
        )

    findings: list[AuditFinding] = []
    paths = sorted(directory.glob("*.yml")) + sorted(directory.glob("*.yaml"))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(AuditFinding(path.name, "workflow-unreadable", str(exc)))
            continue
        try:
            document = _load(path)
        except yaml.YAMLError as exc:
            findings.append(AuditFinding(path.name, "workflow-invalid", f"invalid YAML: {exc}"))
            continue

        findings.extend(_check_document(path.name, document))
        findings.extend(_check_pinning(path.name, text))
        if path.name == PRIMARY_WORKFLOW and isinstance(document, Mapping):
            findings.extend(_check_pipeline(path.name, text, document))
    return tuple(findings)
