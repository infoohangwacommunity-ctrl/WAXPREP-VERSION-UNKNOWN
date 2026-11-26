"""Static audit of the CI workflow definitions.

The audit protects the integrity of the acceptance system itself: a workflow
that references a mutable action tag, omits least-privilege permissions, drops
a required job, records evidence for the wrong job id, uploads evidence under a
name the acceptance job cannot download, lowers a blocking job to advisory, or
stops wiring a required report into the acceptance decision would weaken
acceptance silently.

The audit inspects the parsed workflow structure (jobs, steps, ``needs``,
``if``, ``timeout-minutes``, artifact names and the recorded evidence commands),
not just the presence of text, so the properties the design depends on are
checked rather than merely documented.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from waxprep.ci.acceptance import ADVISORY_JOBS, REQUIRED_JOBS, TEST_CATEGORIES, CheckClass

WORKFLOW_DIRECTORY = Path(".github") / "workflows"
PRIMARY_WORKFLOW = "quality-gate.yml"
ACCEPTANCE_JOB = "ci-acceptance"
MATRIX_JOB = "tests"
REQUIRED_TRIGGERS = ("push", "pull_request", "workflow_dispatch")
MATRIX_JOB_PLACEHOLDER = "tests-${{ matrix.category }}"
MATRIX_EVIDENCE_ARGUMENT = f'--job "{MATRIX_JOB_PLACEHOLDER}"'
EVIDENCE_ARTIFACT_PREFIX = "ci-evidence-"
EVIDENCE_DIRECTORY = "ci-evidence"
EVIDENCE_DOWNLOAD_PATTERN = "ci-evidence-*"
COVERAGE_ARTIFACT = "coverage-report"
COVERAGE_PRODUCER = "coverage-gate"
SUPPLY_CHAIN_ARTIFACT = "supply-chain-evidence"
SUPPLY_CHAIN_PRODUCER = "supply-chain-evidence"
REQUIRED_REPORTS = (
    (COVERAGE_ARTIFACT, COVERAGE_PRODUCER),
    (SUPPLY_CHAIN_ARTIFACT, SUPPLY_CHAIN_PRODUCER),
)
ALWAYS = "always()"
UPLOAD_ARTIFACT_ACTION = "actions/upload-artifact"
DOWNLOAD_ARTIFACT_ACTION = "actions/download-artifact"
PINNED_ACTION = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
USES_LINE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<reference>\S+)\s*$", re.MULTILINE)
RECORD_COMMAND = re.compile(
    r'--job\s+(?:"(?P<quoted>[^"]+)"|(?P<bare>\S+))\s+--class\s+(?P<check_class>[A-Za-z]+)'
)
COVERAGE_ARGUMENT = re.compile(r"--coverage\s+(?P<path>[^\s\"'\\]+)")
SBOM_ARGUMENT = re.compile(r"--sbom\s+(?P<path>[^\s\"'\\]+)")


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


def _as_list(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return ()


def _normalise(path: str) -> str:
    cleaned = path.strip().strip("\"'")
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return cleaned.rstrip("/")


def _jobs(document: Mapping[Any, Any]) -> Mapping[str, Any]:
    jobs = document.get("jobs")
    return jobs if isinstance(jobs, Mapping) else {}


def _steps(job: Mapping[Any, Any]) -> tuple[Mapping[Any, Any], ...]:
    steps = job.get("steps")
    if not isinstance(steps, list):
        return ()
    return tuple(step for step in steps if isinstance(step, Mapping))


def _run_texts(job: Mapping[Any, Any]) -> tuple[str, ...]:
    texts: list[str] = []
    for step in _steps(job):
        value = step.get("run")
        if isinstance(value, str):
            texts.append(value)
    return tuple(texts)


def _action_with_blocks(job: Mapping[Any, Any], action: str) -> tuple[Mapping[Any, Any], ...]:
    blocks: list[Mapping[Any, Any]] = []
    for step in _steps(job):
        uses = step.get("uses")
        if not isinstance(uses, str) or not uses.startswith(action):
            continue
        with_block = step.get("with")
        if isinstance(with_block, Mapping):
            blocks.append(with_block)
    return tuple(blocks)


def _uploads(job: Mapping[Any, Any]) -> dict[str, str]:
    uploads: dict[str, str] = {}
    for block in _action_with_blocks(job, UPLOAD_ARTIFACT_ACTION):
        name = block.get("name")
        if name is not None:
            uploads[str(name)] = str(block.get("path", ""))
    return uploads


def _downloads(job: Mapping[Any, Any]) -> dict[str, str]:
    downloads: dict[str, str] = {}
    for block in _action_with_blocks(job, DOWNLOAD_ARTIFACT_ACTION):
        name = block.get("name", block.get("pattern"))
        if name is not None:
            downloads[str(name)] = str(block.get("path", ""))
    return downloads


def _recorded_jobs(job: Mapping[Any, Any]) -> dict[str, str]:
    recorded: dict[str, str] = {}
    for text in _run_texts(job):
        for match in RECORD_COMMAND.finditer(text):
            job_id = match.group("quoted") or match.group("bare")
            recorded.setdefault(str(job_id), match.group("check_class"))
    return recorded


def _expected_records() -> tuple[tuple[str, str, CheckClass], ...]:
    """Return ``(workflow job id, recorded job id, required class)`` triples."""
    expected: list[tuple[str, str, CheckClass]] = [
        (job, job, CheckClass.BLOCKING) for job in REQUIRED_JOBS if not job.startswith("tests-")
    ]
    expected.append((MATRIX_JOB, MATRIX_JOB_PLACEHOLDER, CheckClass.BLOCKING))
    expected.extend((job, job, CheckClass.ADVISORY) for job in ADVISORY_JOBS)
    return tuple(expected)


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


def _check_triggers(name: str, document: Mapping[Any, Any]) -> list[AuditFinding]:
    triggers = _triggers(document)
    return [
        AuditFinding(name, "missing-trigger", f"required trigger '{trigger}' is not configured")
        for trigger in REQUIRED_TRIGGERS
        if trigger not in triggers
    ]


def _check_required_jobs(name: str, job_map: Mapping[str, Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for job in (*REQUIRED_JOBS, *ADVISORY_JOBS):
        if job.startswith("tests-"):
            continue
        if job not in job_map:
            findings.append(AuditFinding(name, "missing-job", f"required job '{job}' is absent"))
    if ACCEPTANCE_JOB not in job_map:
        findings.append(
            AuditFinding(name, "missing-job", f"acceptance job '{ACCEPTANCE_JOB}' is absent")
        )
    findings.extend(
        AuditFinding(name, "workflow-invalid", f"job '{job_id}' is not a job definition")
        for job_id, definition in job_map.items()
        if not isinstance(definition, Mapping)
    )
    return findings


def _check_matrix(name: str, job_map: Mapping[str, Any]) -> list[AuditFinding]:
    tests_job = job_map.get(MATRIX_JOB)
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


def _check_evidence_recording(name: str, job_map: Mapping[str, Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for workflow_job, recorded_id, expected_class in _expected_records():
        job = job_map.get(workflow_job)
        if not isinstance(job, Mapping):
            continue
        recorded = _recorded_jobs(job)
        actual = recorded.get(recorded_id)
        if actual is None:
            findings.append(
                AuditFinding(
                    name,
                    "missing-evidence-recording",
                    f"job '{workflow_job}' does not record evidence for '{recorded_id}'",
                )
            )
        elif actual != expected_class.value:
            findings.append(
                AuditFinding(
                    name,
                    "misclassified-evidence",
                    f"job '{workflow_job}' records '{recorded_id}' as {actual}, "
                    f"expected {expected_class.value}",
                )
            )
    return findings


def _check_evidence_artifacts(name: str, job_map: Mapping[str, Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for workflow_job, recorded_id, _ in _expected_records():
        job = job_map.get(workflow_job)
        if not isinstance(job, Mapping):
            continue
        artifact = f"{EVIDENCE_ARTIFACT_PREFIX}{recorded_id}"
        uploads = _uploads(job)
        if artifact not in uploads:
            findings.append(
                AuditFinding(
                    name,
                    "evidence-artifact-missing",
                    f"job '{workflow_job}' does not upload its evidence artifact '{artifact}'",
                )
            )
        elif _normalise(uploads[artifact]) != EVIDENCE_DIRECTORY:
            findings.append(
                AuditFinding(
                    name,
                    "evidence-artifact-mismatch",
                    f"job '{workflow_job}' uploads '{artifact}' from "
                    f"'{uploads[artifact]}', expected '{EVIDENCE_DIRECTORY}/'",
                )
            )

    acceptance = job_map.get(ACCEPTANCE_JOB)
    if not isinstance(acceptance, Mapping):
        return findings
    downloads = _downloads(acceptance)
    if EVIDENCE_DOWNLOAD_PATTERN not in downloads:
        findings.append(
            AuditFinding(
                name,
                "acceptance-download-mismatch",
                "acceptance does not download the evidence artifacts "
                f"(pattern '{EVIDENCE_DOWNLOAD_PATTERN}')",
            )
        )
    for artifact, _producer in REQUIRED_REPORTS:
        if artifact not in downloads:
            findings.append(
                AuditFinding(
                    name,
                    "acceptance-download-mismatch",
                    f"acceptance does not download the required report artifact '{artifact}'",
                )
            )
    return findings


def _coverage_is_wired(argument: str, downloads: Mapping[str, str], producer: Any) -> bool:
    destination = _normalise(downloads.get(COVERAGE_ARTIFACT, ""))
    uploaded = _uploads(producer) if isinstance(producer, Mapping) else {}
    source = _normalise(uploaded.get(COVERAGE_ARTIFACT, ""))
    candidate = _normalise(argument)
    if not destination or not source or "/" not in candidate:
        return False
    parent, _, file_name = candidate.rpartition("/")
    return parent == destination and file_name == source.rpartition("/")[2]


def _sbom_is_wired(argument: str, downloads: Mapping[str, str], producer: Any) -> bool:
    destination = _normalise(downloads.get(SUPPLY_CHAIN_ARTIFACT, ""))
    candidate = _normalise(argument)
    if not destination or "/" not in candidate:
        return False
    parent, _, file_name = candidate.rpartition("/")
    if parent != destination:
        return False
    if not isinstance(producer, Mapping):
        return False
    return any(file_name in text for text in _run_texts(producer))


def _check_report_wiring(name: str, job_map: Mapping[str, Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for artifact, producer_id in REQUIRED_REPORTS:
        producer = job_map.get(producer_id)
        if not isinstance(producer, Mapping) or artifact not in _uploads(producer):
            findings.append(
                AuditFinding(
                    name,
                    "report-producer-mismatch",
                    f"required report artifact '{artifact}' is not produced by job '{producer_id}'",
                )
            )

    acceptance = job_map.get(ACCEPTANCE_JOB)
    if not isinstance(acceptance, Mapping):
        return findings

    downloads = _downloads(acceptance)
    text = "\n".join(_run_texts(acceptance))

    coverage = COVERAGE_ARGUMENT.search(text)
    if coverage is None:
        findings.append(
            AuditFinding(
                name,
                "acceptance-report-missing",
                "acceptance does not validate a coverage report (no --coverage argument)",
            )
        )
    elif not _coverage_is_wired(coverage.group("path"), downloads, job_map.get(COVERAGE_PRODUCER)):
        findings.append(
            AuditFinding(
                name,
                "report-producer-mismatch",
                "acceptance validates a coverage report that is not the one produced by "
                f"'{COVERAGE_PRODUCER}' and downloaded as '{COVERAGE_ARTIFACT}'",
            )
        )

    sbom = SBOM_ARGUMENT.search(text)
    if sbom is None:
        findings.append(
            AuditFinding(
                name,
                "acceptance-report-missing",
                "acceptance does not validate an SBOM (no --sbom argument)",
            )
        )
    elif not _sbom_is_wired(sbom.group("path"), downloads, job_map.get(SUPPLY_CHAIN_PRODUCER)):
        findings.append(
            AuditFinding(
                name,
                "report-producer-mismatch",
                "acceptance validates an SBOM that is not the one generated by "
                f"'{SUPPLY_CHAIN_PRODUCER}' and downloaded as '{SUPPLY_CHAIN_ARTIFACT}'",
            )
        )
    return findings


def _required_dependencies() -> tuple[str, ...]:
    dependencies = {
        MATRIX_JOB if job.startswith("tests-") else job for job in (*REQUIRED_JOBS, *ADVISORY_JOBS)
    }
    return tuple(sorted(dependencies))


def _check_acceptance_job(name: str, job_map: Mapping[str, Any]) -> list[AuditFinding]:
    acceptance = job_map.get(ACCEPTANCE_JOB)
    if not isinstance(acceptance, Mapping):
        return []

    findings: list[AuditFinding] = []
    condition = acceptance.get("if")
    if not isinstance(condition, str) or condition.strip() != ALWAYS:
        findings.append(
            AuditFinding(
                name,
                "acceptance-not-always",
                "acceptance job must run with 'if: always()' so upstream failures are still "
                "assessed instead of silently skipped",
            )
        )

    declared = _required_dependencies()
    listed = _as_list(acceptance.get("needs"))
    for dependency in declared:
        if dependency not in listed:
            findings.append(
                AuditFinding(
                    name,
                    "acceptance-missing-dependency",
                    f"acceptance job does not depend on '{dependency}'",
                )
            )
    for dependency in listed:
        if dependency not in declared:
            findings.append(
                AuditFinding(
                    name,
                    "acceptance-unknown-dependency",
                    f"acceptance job depends on '{dependency}', which is not a declared "
                    "required or advisory job",
                )
            )
    return findings


def _check_timeouts(name: str, job_map: Mapping[str, Any]) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for job_id, job in job_map.items():
        if not isinstance(job, Mapping):
            continue
        timeout = job.get("timeout-minutes")
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            findings.append(
                AuditFinding(
                    name,
                    "missing-timeout",
                    f"job '{job_id}' has no positive 'timeout-minutes'",
                )
            )
    return findings


def _check_registration(name: str, job_map: Mapping[str, Any]) -> list[AuditFinding]:
    known = {
        MATRIX_JOB if job.startswith("tests-") else job for job in (*REQUIRED_JOBS, *ADVISORY_JOBS)
    } | {ACCEPTANCE_JOB}
    return [
        AuditFinding(
            name,
            "unregistered-job",
            f"job '{job_id}' is neither required nor advisory in the acceptance policy",
        )
        for job_id in job_map
        if str(job_id) not in known
    ]


def _check_pipeline(name: str, document: Mapping[Any, Any]) -> list[AuditFinding]:
    job_map = _jobs(document)
    findings: list[AuditFinding] = []
    findings.extend(_check_triggers(name, document))
    findings.extend(_check_required_jobs(name, job_map))
    findings.extend(_check_matrix(name, job_map))
    findings.extend(_check_evidence_recording(name, job_map))
    findings.extend(_check_evidence_artifacts(name, job_map))
    findings.extend(_check_report_wiring(name, job_map))
    findings.extend(_check_acceptance_job(name, job_map))
    findings.extend(_check_timeouts(name, job_map))
    findings.extend(_check_registration(name, job_map))
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
            findings.extend(_check_pipeline(path.name, document))
    return tuple(findings)
