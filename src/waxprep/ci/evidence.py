"""Machine-readable CI evidence: job records and required report validation.

Every blocking job writes one JSON record. Acceptance reads those records and
also validates the reports they point at, so a required artifact must exist
*and* be well formed before the commit can be accepted.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from waxprep.ci.acceptance import CheckClass, JobRecord, Status

EVIDENCE_SUFFIX = ".json"
COVERAGE_ROOT_TAG = "coverage"
COVERAGE_RATE_ATTRIBUTE = "line-rate"
SBOM_FORMAT = "CycloneDX"


class EvidenceError(RuntimeError):
    """Raised when evidence or a required report is missing or invalid."""


def parse_status(raw: str) -> Status:
    """Return the normalised status for a raw job outcome."""
    try:
        return Status(raw)
    except ValueError as exc:
        raise EvidenceError(f"unrecognised job status {raw!r}") from exc


def build_record(
    *,
    job: str,
    check_class: str,
    status: str,
    commit: str,
    workflow_run_id: str,
    exit_code: int | None = None,
    recorded_at: datetime | None = None,
) -> JobRecord:
    """Build a validated record without touching the filesystem."""
    if not job:
        raise EvidenceError("job id must not be empty")
    if not commit:
        raise EvidenceError("commit must not be empty")
    try:
        parsed_class = CheckClass(check_class)
    except ValueError as exc:
        raise EvidenceError(f"unrecognised check class {check_class!r}") from exc

    moment = recorded_at if recorded_at is not None else datetime.now(UTC)
    return JobRecord(
        job=job,
        check_class=parsed_class,
        status=parse_status(status),
        commit=commit,
        workflow_run_id=workflow_run_id,
        recorded_at=moment.isoformat(timespec="seconds"),
        exit_code=exit_code,
    )


def record_to_dict(record: JobRecord) -> dict[str, Any]:
    """Serialise a record into its on-disk representation."""
    return {
        "job": record.job,
        "check_class": record.check_class.value,
        "status": record.status.value,
        "commit": record.commit,
        "workflow_run_id": record.workflow_run_id,
        "recorded_at": record.recorded_at,
        "exit_code": record.exit_code,
    }


def write_record(directory: Path, record: JobRecord) -> Path:
    """Write one record into ``directory`` and return its path."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.job}{EVIDENCE_SUFFIX}"
    path.write_text(json.dumps(record_to_dict(record), indent=2) + "\n", encoding="utf-8")
    return path


def _require_string(payload: Mapping[str, Any], key: str, path: Path) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise EvidenceError(f"evidence {path} has no usable '{key}' string")
    return value


def read_record(path: Path) -> JobRecord:
    """Read and strictly validate one evidence record."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvidenceError(f"cannot read evidence {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"evidence {path} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise EvidenceError(f"evidence {path} must be a JSON object")

    status = parse_status(_require_string(payload, "status", path))
    raw_class = _require_string(payload, "check_class", path)
    try:
        check_class = CheckClass(raw_class)
    except ValueError as exc:
        raise EvidenceError(f"evidence {path} has unknown check_class {raw_class!r}") from exc

    exit_code: int | None = None
    raw_exit_code = payload.get("exit_code")
    if raw_exit_code is not None:
        if isinstance(raw_exit_code, bool) or not isinstance(raw_exit_code, int):
            raise EvidenceError(f"evidence {path} has a non-integer exit_code")
        exit_code = raw_exit_code

    return JobRecord(
        job=_require_string(payload, "job", path),
        check_class=check_class,
        status=status,
        commit=_require_string(payload, "commit", path),
        workflow_run_id=_require_string(payload, "workflow_run_id", path),
        recorded_at=_require_string(payload, "recorded_at", path),
        exit_code=exit_code,
    )


def load_evidence(directory: Path) -> tuple[JobRecord, ...]:
    """Load every record in ``directory`` (an absent directory yields nothing)."""
    if not directory.exists():
        return ()
    return tuple(read_record(path) for path in sorted(directory.glob(f"*{EVIDENCE_SUFFIX}")))


def validate_coverage_xml(path: Path, minimum: float = 1.0) -> None:
    """Require a real coverage report whose measured line rate meets policy."""
    try:
        root = ElementTree.parse(path).getroot()
    except OSError as exc:
        raise EvidenceError(f"required coverage report {path} is missing: {exc}") from exc
    except ElementTree.ParseError as exc:
        raise EvidenceError(f"coverage report {path} is not valid XML: {exc}") from exc

    if root.tag != COVERAGE_ROOT_TAG:
        raise EvidenceError(
            f"coverage report {path} has root element '{root.tag}', expected '{COVERAGE_ROOT_TAG}'"
        )

    raw_rate = root.get(COVERAGE_RATE_ATTRIBUTE)
    if raw_rate is None:
        raise EvidenceError(f"coverage report {path} has no {COVERAGE_RATE_ATTRIBUTE} attribute")
    try:
        rate = float(raw_rate)
    except ValueError as exc:
        raise EvidenceError(
            f"coverage report {path} has non-numeric {COVERAGE_RATE_ATTRIBUTE} {raw_rate!r}"
        ) from exc

    if rate < minimum:
        raise EvidenceError(
            f"coverage report {path} records {COVERAGE_RATE_ATTRIBUTE}={rate:.4f}, "
            f"below the required {minimum:.4f}"
        )


def validate_sbom_json(path: Path) -> None:
    """Require a CycloneDX SBOM whose components each identify a package."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise EvidenceError(f"required SBOM {path} is missing: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"SBOM {path} is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise EvidenceError(f"SBOM {path} must be a JSON object")
    if payload.get("bomFormat") != SBOM_FORMAT:
        raise EvidenceError(f"SBOM {path} does not declare bomFormat '{SBOM_FORMAT}'")

    components = payload.get("components")
    if not isinstance(components, list) or not components:
        raise EvidenceError(f"SBOM {path} contains no components")

    unidentified = [
        component
        for component in components
        if not isinstance(component, dict) or not isinstance(component.get("purl"), str)
    ]
    if unidentified:
        raise EvidenceError(
            f"SBOM {path} has {len(unidentified)} component(s) without a purl identifier"
        )
