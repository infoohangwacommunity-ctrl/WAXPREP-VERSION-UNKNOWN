"""CycloneDX SBOM generation for Stage 09.

The SBOM is generated from the resolved runtime closure in ``uv.lock``, not
from the installed environment, so it describes the dependency set CI approved.
Development tools are excluded. Output is deterministic to keep diffs and
artifacts comparable between commits.
"""

from __future__ import annotations

import json
from pathlib import Path

from waxprep.supplychain.checks import Assessment, DependencyRecord
from waxprep.supplychain.names import canonical_name
from waxprep.supplychain.policy import LicenseDecision

BOM_FORMAT = "CycloneDX"
SPEC_VERSION = "1.5"


def _hash_entry(value: str) -> dict[str, str] | None:
    algorithm, _, digest = value.partition(":")
    if algorithm.lower() != "sha256" or not digest:
        return None
    return {"alg": "SHA-256", "content": digest}


def _depends_on(record: DependencyRecord, by_key: dict[str, DependencyRecord]) -> list[str]:
    """Resolve one component's edges to the packages it actually depends on."""
    refs = {
        by_key[key].purl
        for name in record.dependencies
        if (key := canonical_name(name)) in by_key and key != record.key
    }
    return sorted(refs)


def build_sbom(
    assessment: Assessment, app_name: str = "waxprep", app_version: str = "0.1.0"
) -> dict[str, object]:
    """Build a CycloneDX 1.5 document for the runtime dependency set.

    Dependency relationships are taken from ``uv.lock``: the root application
    references only its direct dependencies, and each component references the
    packages it declares. Transitive dependencies are never flattened into
    direct application dependencies.
    """
    root_ref = f"pkg:pypi/{app_name}@{app_version}"
    by_key = {record.key: record for record in assessment.records}
    direct_refs = sorted(record.purl for record in assessment.records if record.direct)
    components: list[dict[str, object]] = []
    for record in assessment.records:
        component: dict[str, object] = {
            "type": "library",
            "name": record.name,
            "version": record.version,
            "purl": record.purl,
        }
        hashes = [
            entry for entry in (_hash_entry(value) for value in record.hashes) if entry is not None
        ]
        if hashes:
            component["hashes"] = hashes
        if record.license_id and record.license_decision is not LicenseDecision.UNKNOWN:
            component["licenses"] = [{"license": {"id": record.license_id}}]
        components.append(component)

    return {
        "bomFormat": BOM_FORMAT,
        "specVersion": SPEC_VERSION,
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": app_name,
                "version": app_version,
                "purl": root_ref,
                "licenses": [{"license": {"id": "MIT"}}],
            }
        },
        "components": components,
        "dependencies": [
            {"ref": root_ref, "dependsOn": direct_refs},
            *[
                {"ref": record.purl, "dependsOn": _depends_on(record, by_key)}
                for record in assessment.records
            ],
        ],
    }


def write_sbom(assessment: Assessment, path: Path) -> Path:
    """Write the SBOM as pretty-printed JSON and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_sbom(assessment), indent=2) + "\n", encoding="utf-8")
    return path
