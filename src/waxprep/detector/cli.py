# Entry point for Universal Hardcoding Detector CLI
"""CLI entry point for the Universal Hardcoding Detector."""

from __future__ import annotations

import sys

from waxprep.detector import run_detection


def main() -> int:
    """Run the detector CLI."""
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    fmt = sys.argv[2] if len(sys.argv) > 2 else "text"
    return run_detection(root, fmt)


if __name__ == "__main__":
    sys.exit(main())
