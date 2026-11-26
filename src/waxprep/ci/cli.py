"""Stage 10 CI CLI.

Usage:
    python -m waxprep.ci.cli record --job quality-gate --class blocking \
        --status failure --commit <sha> --run-id <id> --output ci-evidence
    python -m waxprep.ci.cli accept --evidence-dir ci-evidence --commit <sha> \
        --coverage coverage.xml --sbom sbom.json --report acceptance.json
    python -m waxprep.ci.cli audit [--root .]

``record`` writes one job's evidence. ``accept`` validates evidence and
required reports, writes a machine-readable decision and fails the job unless
the commit is accepted. ``audit`` checks the workflow definitions themselves.
No subcommand installs, upgrades or deploys anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

from waxprep.ci.acceptance import evaluate_acceptance
from waxprep.ci.evidence import (
    EvidenceError,
    build_record,
    load_evidence,
    validate_coverage_xml,
    validate_sbom_json,
    write_record,
)
from waxprep.ci.report import decision_to_dict, render_markdown
from waxprep.ci.workflows import audit_workflows


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WaxPrep continuous integration (Stage 10)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    record = subparsers.add_parser("record", help="Record one job's evidence")
    record.add_argument("--job", required=True, help="Stable job identifier")
    record.add_argument(
        "--class",
        dest="check_class",
        required=True,
        choices=["blocking", "advisory"],
        help="Whether this job blocks acceptance",
    )
    record.add_argument("--status", required=True, help="Job outcome (success, failure, ...)")
    record.add_argument("--commit", required=True, help="Commit SHA the job assessed")
    record.add_argument("--run-id", required=True, help="Workflow run identifier")
    record.add_argument("--exit-code", type=int, help="Exit code of the executed check")
    record.add_argument("--output", required=True, help="Evidence output directory")

    accept = subparsers.add_parser("accept", help="Decide acceptance from recorded evidence")
    accept.add_argument("--evidence-dir", required=True, help="Directory of evidence records")
    accept.add_argument("--commit", required=True, help="Commit SHA under assessment")
    accept.add_argument("--coverage", required=True, help="Required coverage XML report")
    accept.add_argument("--sbom", required=True, help="Required CycloneDX SBOM")
    accept.add_argument("--report", required=True, help="Machine-readable decision output path")
    accept.add_argument("--summary", help="Append the Markdown report to this file")
    accept.add_argument(
        "--minimum-coverage",
        type=float,
        default=1.0,
        help="Required coverage line rate (default: 1.0)",
    )

    audit = subparsers.add_parser("audit", help="Audit workflow definitions")
    audit.add_argument("--root", default=".", help="Project root (default: .)")
    return parser


def _record(args: argparse.Namespace) -> int:
    try:
        record = build_record(
            job=args.job,
            check_class=args.check_class,
            status=args.status,
            commit=args.commit,
            workflow_run_id=args.run_id,
            exit_code=args.exit_code,
        )
    except EvidenceError as exc:
        print(f"CI evidence error: {exc}", file=sys.stderr)
        return 1

    path = write_record(Path(args.output), record)
    print(f"Recorded {record.job} evidence as {record.status.value} in {path}")
    return 0


def _collect_report_failures(args: argparse.Namespace) -> list[str]:
    try:
        validate_coverage_xml(Path(args.coverage), minimum=args.minimum_coverage)
    except EvidenceError as exc:
        coverage_failure = str(exc)
        failures = [coverage_failure]
    else:
        failures = []

    try:
        validate_sbom_json(Path(args.sbom))
    except EvidenceError as exc:
        failures.append(str(exc))
    return failures


def _write_summary(path: str, markdown: str) -> None:
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(markdown)


def _accept(args: argparse.Namespace) -> int:
    try:
        records = load_evidence(Path(args.evidence_dir))
    except EvidenceError as exc:
        print(f"CI evidence error: {exc}", file=sys.stderr)
        return 1

    decision = evaluate_acceptance(records, args.commit)
    report_failures = _collect_report_failures(args)
    if report_failures:
        decision = replace(
            decision,
            accepted=False,
            failures=(*decision.failures, *report_failures),
        )

    markdown = render_markdown(decision)
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(decision_to_dict(decision), indent=2) + "\n", encoding="utf-8"
    )
    if args.summary:
        _write_summary(args.summary, markdown)

    print(markdown)
    if not decision.accepted:
        for failure in decision.failures:
            print(f"REJECTED: {failure}", file=sys.stderr)
        return 1
    return 0


def _audit(args: argparse.Namespace) -> int:
    findings = audit_workflows(Path(args.root))
    for finding in findings:
        print(f"{finding.workflow}: {finding.rule}: {finding.message}")
    if findings:
        print(f"Workflow audit FAILED with {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("Workflow audit PASSED")
    return 0


_DISPATCH = {
    "record": _record,
    "accept": _accept,
    "audit": _audit,
}


def _run(args: argparse.Namespace) -> int:
    return _DISPATCH[args.command](args)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the Stage 10 CI CLI and return its exit status."""
    return _run(_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
