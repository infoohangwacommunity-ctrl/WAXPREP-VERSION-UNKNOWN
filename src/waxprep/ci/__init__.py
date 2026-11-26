"""Stage 10 — Continuous Integration (CI).

Development-time only. This package records what each workflow job actually
did, decides acceptance from that evidence, validates required reports and
audits the workflow definitions themselves. Nothing here is imported by the
request path and it adds no runtime service or database.
"""

from waxprep.ci.acceptance import (
    ADVISORY_JOBS,
    COMMIT_LENGTH,
    REQUIRED_JOBS,
    TEST_CATEGORIES,
    AcceptanceDecision,
    AdvisoryState,
    CheckClass,
    ExecutionPhase,
    JobRecord,
    Status,
    evaluate_acceptance,
    is_full_commit,
)
from waxprep.ci.evidence import (
    EvidenceError,
    build_record,
    load_evidence,
    parse_status,
    read_record,
    record_to_dict,
    validate_coverage_xml,
    validate_sbom_json,
    write_record,
)
from waxprep.ci.report import decision_to_dict, render_markdown

__all__ = [
    "ADVISORY_JOBS",
    "COMMIT_LENGTH",
    "REQUIRED_JOBS",
    "TEST_CATEGORIES",
    "AcceptanceDecision",
    "AdvisoryState",
    "CheckClass",
    "ExecutionPhase",
    "EvidenceError",
    "JobRecord",
    "Status",
    "build_record",
    "decision_to_dict",
    "evaluate_acceptance",
    "is_full_commit",
    "load_evidence",
    "parse_status",
    "read_record",
    "record_to_dict",
    "render_markdown",
    "validate_coverage_xml",
    "validate_sbom_json",
    "write_record",
]
