"""CycloneDX SBOM generation for Stage 09.

The SBOM is generated from the resolved runtime closure in ``uv.lock``, not
from the installed environment, so it describes the dependency set CI approved.
Development tools are excluded. Output is deterministic to keep diffs and
artifacts comparable between commits.
"""

from __future__ import annotations

import json
from pathlib import Path

from waxprep.supplychain.checks import Assessment
from waxprep.supplychain.policy import LicenseDecision

BOM_FORMAT = "CycloneDX"
SPEC_VERSION = "1.5"


def _hash_entry(value: str) -> dict[str, str] | None:
    algorithm, _, digest = value.partition(":")
    if algorithm.lower() != "sha256" or not digest:
        return None
    return {"alg": "SHA-256", "content": digest}


def build_sbom(
    assessment: Assessment, app_name: str = "waxprep", app_version: str = "0.1.0"
) -> dict[str, object]:
    """Build a CycloneDX 1.5 document for the runtime dependency set."""
    root_ref = f"pkg:pypi/{app_name}@{app_version}"
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
            {"ref": root_ref, "dependsOn": [record.purl for record in assessment.records]},
            *[{"ref": record.purl, "dependsOn": []} for record in assessment.records],
        ],
    }


def write_sbom(assessment: Assessment, path: Path) -> Path:
    """Write the SBOM as pretty-printed JSON and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_sbom(assessment), indent=2) + "\n", encoding="utf-8")
    return path
