"""Dependency Trust assessment for Stage 09.

This module combines the individual controls into one evidence-based result.
It does not replace the existing scanners; it decides what their evidence means
for this repository and produces the dependency record that reports and the
SBOM share.

Severity is separate from evidence: a finding can be informational, require
review, or block the gate. Only ``blocking`` findings fail the quality gate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path

from waxprep.supplychain.audit import AuditOutcome, run_pip_audit
from waxprep.supplychain.licenses import MetadataReader, license_from_metadata
from waxprep.supplychain.lockfile import (
    RUNTIME_GROUP,
    LockedPackage,
    Lockfile,
    LockfileError,
    read_lockfile,
    read_requirements,
)
from waxprep.supplychain.names import canonical_name
from waxprep.supplychain.osv import OsvOutcome, Poster, check_malicious
from waxprep.supplychain.policy import DependencyPolicy, LicenseDecision, load_policy


class Severity(StrEnum):
    """How a supply-chain finding affects the gate."""

    BLOCKING = "blocking"
    REVIEW = "review"
    INFO = "info"


@dataclass(frozen=True)
class Finding:
    """One supply-chain finding."""

    code: str
    severity: Severity
    message: str
    package: str = ""

    def to_dict(self) -> dict[str, str]:
        """Serialize the finding for JSON output."""
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "package": self.package,
        }


@dataclass(frozen=True)
class DependencyRecord:
    """Trust evidence for one resolved runtime dependency."""

    name: str
    version: str
    direct: bool
    source_type: str
    source_url: str
    has_hashes: bool
    hashes: tuple[str, ...]
    license_id: str | None
    license_decision: LicenseDecision
    advisories: tuple[str, ...]
    provenance: str = "not-verified"

    @property
    def key(self) -> str:
        """Canonical package name."""
        return canonical_name(self.name)

    @property
    def purl(self) -> str:
        """Package URL for the SBOM."""
        return f"pkg:pypi/{self.key}@{self.version}"

    def to_dict(self) -> dict[str, object]:
        """Serialize the record for JSON output."""
        return {
            "package": self.name,
            "version": self.version,
            "dependency": "direct" if self.direct else "transitive",
            "source": self.source_type,
            "source_url": self.source_url,
            "hashes": "verified" if self.has_hashes else "missing",
            "license": self.license_id or "unknown",
            "license_decision": self.license_decision.value,
            "advisories": list(self.advisories),
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class Assessment:
    """Complete supply-chain assessment for one checkout."""

    root: Path
    today: date
    records: tuple[DependencyRecord, ...]
    findings: tuple[Finding, ...]

    @property
    def blocking(self) -> tuple[Finding, ...]:
        """Findings that fail the gate."""
        return tuple(finding for finding in self.findings if finding.severity is Severity.BLOCKING)

    @property
    def review(self) -> tuple[Finding, ...]:
        """Findings that require a human decision but do not block."""
        return tuple(finding for finding in self.findings if finding.severity is Severity.REVIEW)

    @property
    def passed(self) -> bool:
        """True when nothing blocks the gate."""
        return not self.blocking

    def findings_for(self, package: str) -> tuple[Finding, ...]:
        """Return findings attributable to one package."""
        key = canonical_name(package)
        return tuple(
            finding
            for finding in self.findings
            if finding.package and canonical_name(finding.package) == key
        )

    def record_for(self, package: str) -> DependencyRecord | None:
        """Return the runtime record for one package."""
        key = canonical_name(package)
        for record in self.records:
            if record.key == key:
                return record
        return None


AuditRunner = Callable[[], AuditOutcome]


def _policy_findings(
    policy: DependencyPolicy, runtime: tuple[LockedPackage, ...], lockfile: Lockfile
) -> list[Finding]:
    findings: list[Finding] = []
    direct = {requirement.key: requirement for requirement in lockfile.direct(RUNTIME_GROUP)}

    for requirement in lockfile.direct(RUNTIME_GROUP):
        if not lockfile.find(requirement.name):
            findings.append(
                Finding(
                    "SC-003",
                    Severity.BLOCKING,
                    f"Direct runtime dependency '{requirement.name}' is not resolved in uv.lock",
                    requirement.name,
                )
            )
        if not requirement.specifier:
            findings.append(
                Finding(
                    "SC-004",
                    Severity.BLOCKING,
                    f"Direct runtime dependency '{requirement.name}' has no version constraint",
                    requirement.name,
                )
            )
        if not policy.inventory.purpose_for(requirement.name):
            findings.append(
                Finding(
                    "SC-014",
                    Severity.BLOCKING,
                    f"Direct runtime dependency '{requirement.name}' has no documented purpose",
                    requirement.name,
                )
            )

    for package in runtime:
        # Dependency source classification, not student input routing.
        if package.source_type == "registry":  # nosemgrep: semgrep.whd-001-fixed-string-comparison
            if not policy.sources.registry_allowed(package.source_url):
                findings.append(
                    Finding(
                        "SC-005",
                        Severity.BLOCKING,
                        f"'{package.name}' resolves from an unapproved registry: {package.source_url}",
                        package.name,
                    )
                )
            if not package.has_hashes:
                findings.append(
                    Finding(
                        "SC-006",
                        Severity.BLOCKING,
                        f"'{package.name}' has no artifact hash in uv.lock",
                        package.name,
                    )
                )
        elif package.source_type == "vcs" and not policy.sources.allow_vcs:
            findings.append(
                Finding(
                    "SC-005",
                    Severity.BLOCKING,
                    f"'{package.name}' uses a Git source, which this policy does not allow",
                    package.name,
                )
            )
        elif package.source_type == "url" and not policy.sources.allow_url:
            findings.append(
                Finding(
                    "SC-005",
                    Severity.BLOCKING,
                    f"'{package.name}' uses a direct URL source, which this policy does not allow",
                    package.name,
                )
            )
        elif package.source_type not in {"registry", "vcs", "url"}:
            findings.append(
                Finding(
                    "SC-005",
                    Severity.BLOCKING,
                    f"'{package.name}' has an unexpected source type: {package.source_type}",
                    package.name,
                )
            )

        if canonical_name(package.name) in direct and not policy.sources.major_reviewed(
            package.name, package.version
        ):
            findings.append(
                Finding(
                    "SC-007",
                    Severity.REVIEW,
                    f"Major version {package.version} of '{package.name}' has not been reviewed",
                    package.name,
                )
            )

    return findings


def _vulnerability_findings(
    policy: DependencyPolicy, outcome: AuditOutcome, today: date
) -> tuple[list[Finding], dict[str, list[str]]]:
    findings: list[Finding] = []
    by_package: dict[str, list[str]] = {}
    reported_expired: set[tuple[str, str]] = set()

    if outcome.error is not None:
        findings.append(Finding("SC-010", Severity.BLOCKING, outcome.error))
        return findings, by_package

    for advisory in outcome.advisories:
        by_package.setdefault(canonical_name(advisory.package), []).append(advisory.advisory_id)
        matching = [
            exception
            for exception in policy.exceptions
            if exception.matches_any(advisory.identifiers, advisory.package, advisory.version)
        ]
        active = [exception for exception in matching if not exception.is_expired(today)]
        if active:
            findings.append(
                Finding(
                    "SC-016",
                    Severity.INFO,
                    f"{advisory.advisory_id} for '{advisory.package}' {advisory.version} "
                    f"is covered by a tracked exception until {active[0].review_by.isoformat()}",
                    advisory.package,
                )
            )
            continue

        if matching:
            for exception in matching:
                key = (exception.advisory, canonical_name(exception.package))
                if key not in reported_expired:
                    reported_expired.add(key)
                    findings.append(
                        Finding(
                            "SC-011",
                            Severity.BLOCKING,
                            f"Exception for {exception.advisory} ({exception.package}) expired "
                            f"on {exception.review_by.isoformat()}",
                            exception.package,
                        )
                    )
            continue

        fixes = ", ".join(advisory.fix_versions) if advisory.fix_versions else "no fix published"
        findings.append(
            Finding(
                "SC-012",
                Severity.BLOCKING,
                f"{advisory.advisory_id} affects '{advisory.package}' {advisory.version} ({fixes})",
                advisory.package,
            )
        )

    for exception in policy.exceptions:
        key = (exception.advisory, canonical_name(exception.package))
        if exception.is_expired(today) and key not in reported_expired:
            reported_expired.add(key)
            findings.append(
                Finding(
                    "SC-011",
                    Severity.BLOCKING,
                    f"Exception for {exception.advisory} ({exception.package}) expired "
                    f"on {exception.review_by.isoformat()}",
                    exception.package,
                )
            )

    return findings, by_package


def _license_findings(
    policy: DependencyPolicy,
    runtime: tuple[LockedPackage, ...],
    reader: MetadataReader | None,
) -> tuple[list[Finding], dict[str, tuple[str | None, LicenseDecision]]]:
    findings: list[Finding] = []
    resolved: dict[str, tuple[str | None, LicenseDecision]] = {}

    for package in runtime:
        license_id = license_from_metadata(package.name, reader)
        decision = policy.licenses.classify(license_id)
        resolved[canonical_name(package.name)] = (license_id, decision)
        if decision is LicenseDecision.PROHIBITED:
            findings.append(
                Finding(
                    "SC-008",
                    Severity.BLOCKING,
                    f"'{package.name}' uses prohibited license {license_id}",
                    package.name,
                )
            )
        elif decision in {LicenseDecision.REVIEW, LicenseDecision.UNKNOWN}:
            findings.append(
                Finding(
                    "SC-009",
                    Severity.REVIEW,
                    f"'{package.name}' license requires review: {license_id or 'unknown'}",
                    package.name,
                )
            )

    return findings, resolved


def _malicious_findings(runtime: tuple[LockedPackage, ...], outcome: OsvOutcome) -> list[Finding]:
    if outcome.error is not None:
        return [Finding("SC-013", Severity.REVIEW, outcome.error)]
    findings = [
        Finding(
            "SC-015",
            Severity.BLOCKING,
            f"{match.advisory_id} marks '{match.package}' {match.version} as malicious",
            match.package,
        )
        for match in outcome.matches
    ]
    findings.append(
        Finding(
            "SC-017",
            Severity.INFO,
            "No malicious-package advisory matched the resolved runtime set; "
            "release provenance attestations remain unverified by this gate",
        )
    )
    return findings


def assess(
    root: Path = Path("."),
    *,
    today: date | None = None,
    audit: AuditRunner | None = None,
    license_reader: MetadataReader | None = None,
    osv_poster: Poster | None = None,
    online: bool = True,
) -> Assessment:
    """Assess the dependency set of one checkout.

    Args:
        root: Project root containing ``uv.lock``, ``pyproject.toml`` and the
            ``security/dependency-policy`` directory.
        today: Evaluation date for exception expiry (defaults to today).
        audit: Vulnerability scan runner, injectable for tests.
        license_reader: Installed-metadata reader, injectable for tests.
        osv_poster: OSV transport, injectable for tests.
        online: When false, skip the OSV lookup and report it as review.

    Raises:
        PolicyError: when a dependency policy is missing or invalid.
    """
    evaluated = today or date.today()
    policy = load_policy(root)

    try:
        requirements = read_requirements(root / "pyproject.toml")
    except LockfileError as exc:
        return Assessment(
            root,
            evaluated,
            (),
            (Finding("SC-002", Severity.BLOCKING, str(exc)),),
        )

    try:
        lockfile = read_lockfile(root / "uv.lock", requirements)
    except LockfileError as exc:
        return Assessment(
            root,
            evaluated,
            (),
            (Finding("SC-001", Severity.BLOCKING, str(exc)),),
        )

    runtime = lockfile.runtime_closure()
    findings = _policy_findings(policy, runtime, lockfile)

    audit_outcome = (audit or run_pip_audit)()
    vulnerability_findings, advisories = _vulnerability_findings(policy, audit_outcome, evaluated)
    findings.extend(vulnerability_findings)

    license_findings, licenses = _license_findings(policy, runtime, license_reader)
    findings.extend(license_findings)

    if online:
        osv_outcome = check_malicious(
            [(package.name, package.version) for package in runtime], osv_poster
        )
    else:
        osv_outcome = OsvOutcome(error="OSV malicious-package check skipped (offline)")
    findings.extend(_malicious_findings(runtime, osv_outcome))

    direct = {requirement.key for requirement in lockfile.direct(RUNTIME_GROUP)}
    records = tuple(
        DependencyRecord(
            name=package.name,
            version=package.version,
            direct=canonical_name(package.name) in direct,
            source_type=package.source_type,
            source_url=package.source_url,
            has_hashes=package.has_hashes,
            hashes=package.hashes,
            license_id=licenses[canonical_name(package.name)][0],
            license_decision=licenses[canonical_name(package.name)][1],
            advisories=tuple(advisories.get(canonical_name(package.name), ())),
        )
        for package in runtime
    )

    return Assessment(root, evaluated, records, tuple(findings))


def advisory_count(assessment: Assessment) -> int:
    """Number of distinct advisories recorded across the runtime set."""
    return len({advisory for record in assessment.records for advisory in record.advisories})
