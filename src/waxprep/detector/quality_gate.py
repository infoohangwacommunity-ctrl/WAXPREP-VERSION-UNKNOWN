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

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from waxprep.detector import (
    DataFileInspector,
    UniversalHardcodingDetector,
)


class CheckResult(TypedDict):
    """Result of the hardcoding detection check."""

    passed: bool
    blocked: bool
    total_findings: int
    blocking_findings: int
    high_severity: int
    medium_severity: int
    low_severity: int
    findings: list[dict[str, object]]
    summary: str


def check_hardcoding(
    root_path: str | Path = "src",
    output_format: str = "summary",
    json_output_path: str | Path | None = None,
) -> CheckResult:
    """
    Run the Universal Hardcoding Detector as a quality gate check.

    Args:
        root_path: Path to scan (default: "src")
        output_format: Output format for reporting
        json_output_path: Optional path to write JSON report

    Returns:
        CheckResult with pass/fail status and findings
    """
    detector = UniversalHardcodingDetector(root_path)
    data_inspector = DataFileInspector(root_path)

    # Run Python code detection
    python_findings = detector.scan_project()

    # Run data file inspection
    data_findings = data_inspector.inspect_directory(root_path)

    all_findings = python_findings + data_findings

    # Categorize findings
    high_severity = sum(1 for f in all_findings if f.severity.value == "HIGH")
    medium_severity = sum(1 for f in all_findings if f.severity.value == "MEDIUM")
    low_severity = sum(1 for f in all_findings if f.severity.value == "LOW")
    blocking_findings = sum(1 for f in all_findings if f.blocks_merge)

    passed = blocking_findings == 0
    blocked = blocking_findings > 0

    # Generate summary
    summary_lines = [
        f"Universal Hardcoding Detection: {'PASSED' if passed else 'BLOCKED'}",
        f"Total findings: {len(all_findings)}",
        f"  HIGH (blocking): {high_severity}",
        f"  MEDIUM (review): {medium_severity}",
        f"  LOW (info): {low_severity}",
        f"Blocking: {blocking_findings}",
    ]

    if blocked:
        summary_lines.append("")
        summary_lines.append("Blocking findings:")
        for f in all_findings:
            if f.blocks_merge:
                summary_lines.append(f"  [{f.rule_id}] {f.file_path}:{f.line_number} - {f.message}")

    summary = "\n".join(summary_lines)

    # Output results
    if output_format == "json":
        result_dict = {
            "passed": passed,
            "blocked": blocked,
            "total_findings": len(all_findings),
            "blocking_findings": blocking_findings,
            "high_severity": high_severity,
            "medium_severity": medium_severity,
            "low_severity": low_severity,
            "findings": [f.to_dict() for f in all_findings],
        }
        print(json.dumps(result_dict, indent=2))

        if json_output_path:
            Path(json_output_path).write_text(json.dumps(result_dict, indent=2), encoding="utf-8")
    elif output_format == "summary":
        print(summary)
    else:
        print(summary)

    return CheckResult(
        passed=passed,
        blocked=blocked,
        total_findings=len(all_findings),
        blocking_findings=blocking_findings,
        high_severity=high_severity,
        medium_severity=medium_severity,
        low_severity=low_severity,
        findings=[f.to_dict() for f in all_findings],
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
        "--continue-on-warning",
        action="store_true",
        help="Return 0 even if medium/LOW findings exist (only block on HIGH)",
    )

    args = parser.parse_args()

    result = check_hardcoding(
        root_path=args.path,
        output_format=args.format,
        json_output_path=args.json_output,
    )

    if args.continue_on_warning:
        # Only block on HIGH severity blocking findings
        blocking_high = sum(
            1 for f in result["findings"] if f.get("severity") == "HIGH" and f.get("blocks_merge")
        )
        return 1 if blocking_high > 0 else 0

    return 1 if result["blocked"] else 0
