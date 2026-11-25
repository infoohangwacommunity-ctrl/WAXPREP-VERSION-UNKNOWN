"""OSV malicious-package intelligence for Stage 09.

A clean vulnerability scan does not make a package trustworthy: a malicious
release may have no CVE yet. The OpenSSF malicious-package reports are
published through OSV with ``MAL-`` identifiers, so this check asks OSV about
the exact resolved versions and fails only on malicious matches.

Network failure is a review finding, not a silent pass.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"
MALICIOUS_PREFIX = "MAL-"
REQUEST_TIMEOUT_SECONDS = 30.0

Poster = Callable[[dict[str, object]], object]


@dataclass(frozen=True)
class MaliciousMatch:
    """An OSV malicious-package advisory matching a resolved dependency."""

    package: str
    version: str
    advisory_id: str
    summary: str


@dataclass(frozen=True)
class OsvOutcome:
    """Result of the OSV malicious-package lookup."""

    matches: tuple[MaliciousMatch, ...] = ()
    error: str | None = None


def _default_poster(payload: dict[str, object]) -> object:
    import httpx

    response = httpx.post(OSV_BATCH_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _table(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{where}: expected an object")
    return {str(key): item for key, item in value.items()}


def parse_osv_response(
    payload: object, packages: Sequence[tuple[str, str]]
) -> tuple[MaliciousMatch, ...]:
    """Parse a batch response aligned with the queried packages."""
    document = _table(payload, "OSV response")
    results = document.get("results")
    if not isinstance(results, list) or len(results) != len(packages):
        raise ValueError("OSV response: results do not match the queried packages")

    matches: list[MaliciousMatch] = []
    for index, result in enumerate(results):
        table = _table(result, f"results[{index}]")
        vulnerabilities = table.get("vulns", [])
        if not isinstance(vulnerabilities, list):
            raise ValueError(f"results[{index}].vulns: expected an array")
        package, version = packages[index]
        for vuln_index, vuln in enumerate(vulnerabilities):
            advisory = _table(vuln, f"results[{index}].vulns[{vuln_index}]")
            advisory_id = advisory.get("id")
            if not isinstance(advisory_id, str) or not advisory_id.startswith(MALICIOUS_PREFIX):
                continue
            summary = advisory.get("summary", "")
            matches.append(
                MaliciousMatch(
                    package=package,
                    version=version,
                    advisory_id=advisory_id,
                    summary=summary if isinstance(summary, str) else "",
                )
            )
    return tuple(matches)


def check_malicious(
    packages: Sequence[tuple[str, str]], poster: Poster | None = None
) -> OsvOutcome:
    """Query OSV for malicious-package advisories for resolved versions."""
    if not packages:
        return OsvOutcome()
    payload: dict[str, object] = {
        "queries": [
            {"package": {"name": name, "ecosystem": "PyPI"}, "version": version}
            for name, version in packages
        ]
    }
    try:
        response = (poster or _default_poster)(payload)
        return OsvOutcome(matches=parse_osv_response(response, packages))
    except Exception as exc:  # noqa: BLE001 - any transport/parse failure must not pass silently
        return OsvOutcome(error=f"OSV lookup failed: {exc}")
