"""Stage 09 supply-chain CLI.

Usage:
    python -m waxprep.supplychain.cli check [--root .] [--format summary|json]
    python -m waxprep.supplychain.cli trust [--output report.md]
    python -m waxprep.supplychain.cli sbom [--output artifacts/sbom.cdx.json]

``check`` is the blocking gate command. ``trust`` and ``sbom`` produce the two
human-usable outputs of the stage. None of them install, upgrade or deploy
anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from waxprep.supplychain.checks import Assessment, assess
from waxprep.supplychain.policy import PolicyError
from waxprep.supplychain.report import assessment_to_dict, render_summary, render_trust_markdown
from waxprep.supplychain.sbom import write_sbom

DEFAULT_SBOM_PATH = Path("artifacts") / "waxprep-sbom.cdx.json"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="WaxPrep dependency and supply-chain security (Stage 09)"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--root", default=".", help="Project root (default: .)")
        subparser.add_argument(
            "--today",
            type=date.fromisoformat,
            help="Evaluation date (YYYY-MM-DD) for exception expiry; defaults to today",
        )
        subparser.add_argument(
            "--offline",
            action="store_true",
            help="Skip the OSV malicious-package lookup and report it as review",
        )

    check = subparsers.add_parser("check", help="Run the blocking dependency trust gate")
    add_common(check)
    check.add_argument(
        "--format",
        choices=["summary", "json"],
        default="summary",
        help="Output format (default: summary)",
    )

    trust = subparsers.add_parser("trust", help="Render the Dependency Trust Intelligence report")
    add_common(trust)
    trust.add_argument("--output", help="Write the Markdown report to this path")

    sbom = subparsers.add_parser("sbom", help="Write a CycloneDX 1.5 SBOM for runtime dependencies")
    add_common(sbom)
    sbom.add_argument(
        "--output",
        default=str(DEFAULT_SBOM_PATH),
        help=f"Output path (default: {DEFAULT_SBOM_PATH})",
    )
    return parser


def _evaluate(args: argparse.Namespace) -> Assessment:
    return assess(Path(args.root), today=args.today, online=not args.offline)


def _run(args: argparse.Namespace) -> int:
    try:
        assessment = _evaluate(args)
    except PolicyError as exc:
        print(f"Dependency policy error: {exc}", file=sys.stderr)
        return 1

    # CLI subcommand dispatch; no student input is involved.
    if args.command == "check":  # nosemgrep: semgrep.whd-001-fixed-string-comparison
        if args.format == "json":  # nosemgrep: semgrep.whd-001-fixed-string-comparison
            print(json.dumps(assessment_to_dict(assessment), indent=2))
        else:
            print(render_summary(assessment))
        return 0 if assessment.passed else 1

    if args.command == "trust":  # nosemgrep: semgrep.whd-001-fixed-string-comparison
        markdown = render_trust_markdown(assessment)
        if args.output:
            path = Path(args.output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(markdown, encoding="utf-8")
            print(f"Dependency Trust report written to {path}")
        else:
            print(markdown)
        return 0 if assessment.passed else 1

    path = write_sbom(assessment, Path(args.output))
    print(f"CycloneDX SBOM written to {path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the supply-chain CLI and return its exit status."""
    return _run(_parser().parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
