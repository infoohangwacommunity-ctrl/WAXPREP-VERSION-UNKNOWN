# Entry point for Universal Hardcoding Detector CLI
"""CLI entry point for the Universal Hardcoding Detector."""

from __future__ import annotations

import argparse
import sys

from waxprep.detector import run_detection


def main() -> int:
    """Run the detector CLI."""
    parser = argparse.ArgumentParser(
        description="Universal Hardcoding Detector - Stage 08"
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root directory to scan (default: current directory)",
    )
    parser.add_argument(
        "--format",
        "-f",
        choices=["text", "json", "summary"],
        default="text",
        help="Output format (default: text)",
    )
    args = parser.parse_args()
    return run_detection(args.root, args.format)


if __name__ == "__main__":
    sys.exit(main())
