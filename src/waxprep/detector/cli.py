# Entry point for Universal Hardcoding Detector CLI
"""CLI entry point for the Universal Hardcoding Detector."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from waxprep.detector import DEFAULT_SCAN_TARGETS, run_detection


def main() -> int:
    """Run the detector CLI."""
    parser = argparse.ArgumentParser(description="Universal Hardcoding Detector - Stage 08")
    parser.add_argument(
        "targets",
        nargs="*",
        default=None,
        help=(
            "Files or directories to scan (explicit scope). When omitted, the default "
            f"project scope is used: {', '.join(DEFAULT_SCAN_TARGETS)}"
        ),
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "summary"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    if args.targets:
        return run_detection(targets=args.targets, output_format=args.format)

    # Default scope: named project targets that actually exist in this checkout.
    default_targets = [target for target in DEFAULT_SCAN_TARGETS if Path(target).exists()]
    return run_detection(targets=default_targets, output_format=args.format)


if __name__ == "__main__":
    sys.exit(main())
