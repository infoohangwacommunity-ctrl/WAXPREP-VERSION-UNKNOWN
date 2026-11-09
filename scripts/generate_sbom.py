#!/usr/bin/env python3
"""
SBOM Generation Script - Stage 07

Generates a Software Bill of Materials (SBOM) for WaxPrep.
Supports SPDX and CycloneDX formats.

Usage:
    python scripts/generate_sbom.py [--format spdx|cx] [--output FILE]
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def generate_spdx_sbom(output_path: Path) -> int:
    """Generate SBOM in SPDX format using pip-licenses."""
    try:
        # Install pip-licenses if not available
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pip-licenses"],
            check=True,
            capture_output=True,
        )
        
        # Generate SPDX JSON
        result = subprocess.run(
            [
                sys.executable, "-m", "pip_licenses",
                "--format=json",
                "--allow-only", "MIT;BSD;Apache;GPL;LGPL;AGPL;Mozilla;CC0;Unlicense;Zlib;ISC",
                "--output", str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"Error generating SPDX SBOM: {result.stderr}")
            return 1
        
        print(f"SPDX SBOM generated: {output_path}")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def generate_cyclonedx_sbom(output_path: Path) -> int:
    """Generate SBOM in CycloneDX format using cyclonedx-bom."""
    try:
        # Install cyclonedx-bom if not available
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "cyclonedx-bom"],
            check=True,
            capture_output=True,
        )
        
        # Generate CycloneDX JSON
        result = subprocess.run(
            [
                sys.executable, "-m", "cyclonedx_py",
                "-r", "--output", "json",
                "-o", str(output_path),
            ],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"Error generating CycloneDX SBOM: {result.stderr}")
            return 1
        
        print(f"CycloneDX SBOM generated: {output_path}")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        return 1


def generate_sbom_metadata() -> dict:
    """Generate SBOM metadata."""
    return {
        "name": "waxprep",
        "version": "0.3.0",
        "description": "WaxPrep Foundation - AI Learning Companion",
        "creationTime": datetime.now(timezone.utc).isoformat(),
        "licenses": ["MIT"],
        "supplier": "WaxPrep Team",
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate SBOM for WaxPrep",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--format",
        choices=["spdx", "cx"],
        default="spdx",
        help="SBOM format (spdx or cx for CycloneDX)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("sbom.json"),
        help="Output file path",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        print(f"Generating {args.format.upper()} SBOM...")
        print(f"Output: {args.output}")
    
    if args.format == "spdx":
        return generate_spdx_sbom(args.output)
    else:
        return generate_cyclonedx_sbom(args.output)


if __name__ == "__main__":
    sys.exit(main())
