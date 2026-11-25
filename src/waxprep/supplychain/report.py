"""Reporting for Stage 09.

Two outputs matter to the team: a short gate summary, and the Dependency Trust
Intelligence report that shows the evidence per dependency. Both are rendered
from the same assessment, so they cannot disagree.
"""

from __future__ import annotations

from waxprep.supplychain.checks import Assessment, Severity, advisory_count


def render_summary(assessment: Assessment) -> str:
    """Render the compact gate summary."""
    direct = sum(1 for record in assessment.records if record.direct)
    lines = [
        f"Dependency Trust: {'PASSED' if assessment.passed else 'BLOCKED'}",
        f"Evaluated: {assessment.today.isoformat()}",
        f"Runtime packages: {len(assessment.records)} ({direct} direct)",
        f"Vulnerabilities: {advisory_count(assessment)}",
        f"Blocking findings: {len(assessment.blocking)}",
        f"Review findings: {len(assessment.review)}",
    ]
    for finding in assessment.blocking:
        package = f" [{finding.package}]" if finding.package else ""
        lines.append(f"  BLOCK {finding.code}{package}: {finding.message}")
    for finding in assessment.review:
        package = f" [{finding.package}]" if finding.package else ""
        lines.append(f"  REVIEW {finding.code}{package}: {finding.message}")
    return "\n".join(lines)


def _escape(value: str) -> str:
    return value.replace("|", "\\|")


def render_trust_markdown(assessment: Assessment) -> str:
    """Render the Dependency Trust Intelligence report."""
    # Report template, not a student-classification vocabulary.
    lines = [  # nosemgrep: semgrep.whd-008-vocabulary-assignment
        "# Dependency Trust Intelligence",
        "",
        f"- Decision: **{'PASS' if assessment.passed else 'BLOCK'}**",
        f"- Evaluated: {assessment.today.isoformat()}",
        f"- Runtime packages: {len(assessment.records)}",
        f"- Known vulnerabilities: {advisory_count(assessment)}",
        "",
        "## Dependency inventory",
        "",
        "| Package | Version | Scope | Source | Hashes | License | Advisories | Provenance |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for record in assessment.records:
        advisories = ", ".join(record.advisories) or "none"
        lines.append(
            "| "
            + " | ".join(
                _escape(value)
                for value in (
                    record.name,
                    record.version,
                    "direct" if record.direct else "transitive",
                    record.source_type,
                    "verified" if record.has_hashes else "missing",
                    f"{record.license_id or 'unknown'} ({record.license_decision.value})",
                    advisories,
                    record.provenance,
                )
            )
            + " |"
        )

    for title, findings in (
        ("Blocking findings", assessment.blocking),
        ("Review findings", assessment.review),
        (
            "Informational findings",
            tuple(finding for finding in assessment.findings if finding.severity is Severity.INFO),
        ),
    ):
        lines.extend(["", f"## {title}", ""])
        if not findings:
            lines.append("None.")
            continue
        for finding in findings:
            package = f" (`{finding.package}`)" if finding.package else ""
            lines.append(f"- **{finding.code}**{package}: {finding.message}")

    lines.extend([
        "",
        "## Notes",
        "",
        "- A clean vulnerability scan does not prove a package is trustworthy.",
        "- No malicious-package match is not the same as verified provenance;",
        "  this report records provenance separately and does not claim it.",
        "- Development-only tools are excluded from this runtime inventory.",
        "",
    ])
    return "\n".join(lines)


def assessment_to_dict(assessment: Assessment) -> dict[str, object]:
    """Serialize the assessment for JSON consumers."""
    return {
        "passed": assessment.passed,
        "evaluated": assessment.today.isoformat(),
        "runtime_packages": len(assessment.records),
        "records": [record.to_dict() for record in assessment.records],
        "findings": [finding.to_dict() for finding in assessment.findings],
        "blocking": len(assessment.blocking),
        "review": len(assessment.review),
    }
