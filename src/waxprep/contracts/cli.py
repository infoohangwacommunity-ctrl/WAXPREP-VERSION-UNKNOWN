"""Contract schema CLI (Stage 17).

Commands:

* ``generate`` — publish schemas for the current registry;
* ``check`` — fail when committed schemas drift from the models;
* ``compat`` — classify structural changes between two schema files;
* ``list`` — print current contract identities.

The CI gate runs ``check`` so a model change cannot silently bypass the
published contract.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from waxprep.contracts.schema import (
    ContractSchemaRegistry,
    build_default_registry,
    canonical_json,
    load_schema,
)
from waxprep.contracts.versioning import compare_schemas


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="waxprep-contracts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser("generate", help="write current schemas")
    generate.add_argument("--output", type=Path, default=Path("contracts/schemas"))

    check = subparsers.add_parser("check", help="check committed schemas for drift")
    check.add_argument("--schemas", type=Path, default=Path("contracts/schemas"))

    compat = subparsers.add_parser("compat", help="classify schema compatibility")
    compat.add_argument("--old", type=Path, required=True)
    compat.add_argument("--new", type=Path, required=True)

    subparsers.add_parser("list", help="list current contract identities")
    return parser


def _registry() -> ContractSchemaRegistry:
    return build_default_registry()


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    match args.command:
        case "generate":
            registry = _registry()
            paths = registry.write_to(args.output)
            print(f"Wrote {len(paths)} contract schema files to {args.output}")
            return 0
        case "check":
            drift = _registry().check_drift(args.schemas)
            if drift.ok:
                print("Contract schemas are in sync")
                return 0
            for name in drift.missing:
                print(f"missing contract schema: {name}")
            for name in drift.changed:
                print(f"changed contract schema: {name}")
            print("Run: uv run python -m waxprep.contracts.cli generate")
            return 1
        case "compat":
            compat = compare_schemas(load_schema(args.old), load_schema(args.new))
            print(f"classification: {compat.classification.value}")
            print(f"recommended bump: {compat.recommended_bump.value}")
            for change in compat.changes:
                print(f"{change.compatibility.value}: {change.path} ({change.change.value})")
            return 0 if compat.compatible else 1
        case _:
            print(
                canonical_json({"contracts": [str(item) for item in _registry().identities()]}),
                end="",
            )
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
