# Quality Gate Integration for Universal Hardcoding Detector (Stage 08)
#
# This module provides integration with the existing WaxPrep Quality Gate.
#
# Usage:
#   from waxprep.detector.quality_gate import check_hardcoding
#
#   result = check_hardcoding("src/")
#   if result.blocked:
#       print(f"Build blocked: {len(result.findings)} findings")
#       for finding in result.findings:
#           if finding.blocks_merge:
#               print(f"  [{finding.rule_id}] {finding.file_path}:{finding.line_number}")
#
# This entry point uses the same analysis and enforcement policy as the CLI:
# only findings with `blocks_merge` set stop the gate, and an incomplete scan
# is reported separately instead of being treated as "no findings".

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from waxprep.detector import ScanTargets, analyze


class CheckResult(TypedDict):
    """Result of the hardcoding detection check."""

    passed: bool
    blocked: bool
    complete: bool
    targets: list[str]
    total_findings: int
    blocking_findings: int
    review_findings: int
    high_severity: int
    medium_severity: int
    low_severity: int
    scan_problems: list[dict[str, str]]
    findings: list[dict[str, object]]
    summary: str


def check_hardcoding(
    root_path: str | Path = "src",
    output_format: str = "summary",
    json_output_path: str | Path | None = None,
    targets: ScanTargets = None,
) -> CheckResult:
    """
    Run the Universal Hardcoding Detector as a quality gate check.

    Args:
        root_path: Project root used to resolve targets and module paths
        output_format: Output format for reporting
        json_output_path: Optional path to write JSON report
        targets: Explicit files/directories to scan. Defaults to root_path.

    Returns:
        CheckResult with pass/fail status and findings
    """
    result = analyze([root_path] if targets is None else targets, root_path)

    high_severity = sum(1 for f in result.findings if f.severity.value == "HIGH")
    medium_severity = sum(1 for f in result.findings if f.severity.value == "MEDIUM")
    low_severity = sum(1 for f in result.findings if f.severity.value == "LOW")
    blocking_findings = result.blocking_findings
    review_findings = sum(1 for f in result.findings if f.requires_review)

    # An incomplete scan cannot certify the codebase, so it does not pass.
    passed = result.complete and not blocking_findings
    blocked = not passed

    summary_lines = [
        f"Universal Hardcoding Detection: {'PASSED' if passed else 'BLOCKED'}",
        f"Scanned targets: {', '.join(result.targets)}",
        f"Total findings: {len(result.findings)}",
        f"  HIGH (blocking): {high_severity}",
        f"  MEDIUM (review): {medium_severity}",
        f"  LOW (info): {low_severity}",
        f"Blocking: {len(blocking_findings)}",
        f"Review: {review_findings}",
        f"Scan complete: {'yes' if result.complete else 'no'}",
    ]

    if result.problems:
        summary_lines.append("")
        summary_lines.append("Scan problems (files not inspected):")
        for problem in result.problems:
            detail = f": {problem.detail}" if problem.detail else ""
            summary_lines.append(f"  ! {problem.file_path} ({problem.reason}){detail}")

    if blocking_findings:
        summary_lines.append("")
        summary_lines.append("Blocking findings:")
        for f in blocking_findings:
            summary_lines.append(f"  [{f.rule_id}] {f.file_path}:{f.line_number} - {f.message}")

    summary = "\n".join(summary_lines)

    if output_format == "json":
        result_dict = {
            "passed": passed,
            "blocked": blocked,
            "complete": result.complete,
            "targets": result.targets,
            "total_findings": len(result.findings),
            "blocking_findings": len(blocking_findings),
            "review_findings": review_findings,
            "high_severity": high_severity,
            "medium_severity": medium_severity,
            "low_severity": low_severity,
            "scan_problems": [problem.to_dict() for problem in result.problems],
            "findings": [f.to_dict() for f in result.findings],
        }
        print(json.dumps(result_dict, indent=2))

        if json_output_path:
            Path(json_output_path).write_text(json.dumps(result_dict, indent=2), encoding="utf-8")
    else:
        print(summary)

    return CheckResult(
        passed=passed,
        blocked=blocked,
        complete=result.complete,
        targets=result.targets,
        total_findings=len(result.findings),
        blocking_findings=len(blocking_findings),
        review_findings=review_findings,
        high_severity=high_severity,
        medium_severity=medium_severity,
        low_severity=low_severity,
        scan_problems=[problem.to_dict() for problem in result.problems],
        findings=[f.to_dict() for f in result.findings],
        summary=summary,
    )


def main() -> int:
    """CLI entry point for quality gate check."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Universal Hardcoding Detection Quality Gate Check"
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="src",
        help="Path to scan (default: src)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "summary", "json"],
        default="summary",
        help="Output format",
    )
    parser.add_argument(
        "--json-output",
        help="Path to write JSON report",
    )
    parser.add_argument(
        "--allow-incomplete-scan",
        action="store_true",
        help="Return 0 when files could not be inspected (blocking findings still block)",
    )

    args = parser.parse_args()

    result = check_hardcoding(
        root_path=args.path,
        output_format=args.format,
        json_output_path=args.json_output,
    )

    if args.allow_incomplete_scan:
        return 1 if result["blocking_findings"] else 0

    return 1 if result["blocked"] else 0
