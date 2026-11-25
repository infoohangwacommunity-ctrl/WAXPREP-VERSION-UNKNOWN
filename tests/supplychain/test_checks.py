"""Aggregate supply-chain assessment tests for Stage 09."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from pathlib import Path

import pytest

from tests.supplychain.conftest import lock_entry, write_project
from waxprep.supplychain.audit import Advisory, AuditOutcome
from waxprep.supplychain.checks import Assessment, Severity, advisory_count, assess
from waxprep.supplychain.policy import PolicyError

TODAY = date(2026, 11, 25)

EXPIRED = (
    "[[exceptions]]\n"
    'advisory = "GHSA-53pm-wgxf-c6qf"\n'
    'package = "wcmatch"\n'
    'versions = ["8.5.2"]\n'
    'reason = "r"\n'
    'risk = "r"\n'
    'owner = "o"\n'
    "introduced = 2026-01-01\n"
    "review_by = 2026-02-01\n"
    'remediation_evidence = "e"\n'
    "[[exceptions]]\n"
    'advisory = "GHSA-OLD"\n'
    'package = "unused"\n'
    'versions = ["1.0"]\n'
    'reason = "r"\n'
    'risk = "r"\n'
    'owner = "o"\n'
    "introduced = 2026-01-01\n"
    "review_by = 2026-02-01\n"
    'remediation_evidence = "e"\n'
)

ACTIVE = (
    "[[exceptions]]\n"
    'advisory = "GHSA-53pm-wgxf-c6qf"\n'
    'package = "wcmatch"\n'
    'versions = ["8.5.2"]\n'
    'reason = "r"\n'
    'risk = "r"\n'
    'owner = "o"\n'
    "introduced = 2026-01-01\n"
    "review_by = 2026-12-22\n"
    'remediation_evidence = "e"\n'
)


def mit(name: str) -> Mapping[str, str]:
    return {"License-Expression": "MIT"}


def controlled_audit(*advisories: Advisory) -> AuditOutcome:
    return AuditOutcome(advisories=advisories)


def codes(assessment: Assessment) -> set[str]:
    return {finding.code for finding in assessment.findings}


def test_clean_project_passes_with_provenance_note(project: Path) -> None:
    assessment = assess(
        project,
        today=TODAY,
        audit=lambda: controlled_audit(),
        license_reader=mit,
        online=False,
    )
    assert assessment.passed
    assert codes(assessment) == {"SC-013"}
    assert [record.name for record in assessment.records] == ["alpha", "beta"]
    assert assessment.records[0].direct is True
    assert assessment.records[1].direct is False
    assert assessment.record_for("alpha") is not None
    assert assessment.record_for("missing") is None
    assert assessment.findings_for("alpha") == ()
    assert assessment.findings_for("beta") == ()
    assert advisory_count(assessment) == 0


def test_full_check_combines_every_control(tmp_path: Path) -> None:
    root = write_project(
        tmp_path / "bad",
        packages=(
            lock_entry(
                "alpha",
                "99.0",
                source='{ url = "../alpha.whl" }',
                hashed=False,
                dependencies=("beta", "gitpkg", "pathpkg", "weird", "mirror"),
            ),
            lock_entry("beta", "2.0", hashed=False),
            lock_entry("mirror", "1.0", source='{ registry = "https://mirror.example/simple" }'),
            lock_entry("gitpkg", "1.0", source='{ git = "https://example.invalid/repo" }'),
            lock_entry("pathpkg", "1.0", source='{ path = "../pathpkg" }'),
            lock_entry("weird", "1.0", source='{ mystery = "x" }'),
        ),
        dependencies=("alpha>=1.0", "ghost>=1", "nomaj"),
        reviewed_majors="[reviewed_majors]\nalpha = [1]\n",
        purpose='[purpose]\nalpha = "x"\n',
        owner='[owner]\nalpha = "team"\n',
        exceptions=EXPIRED,
    )

    def license_lookup(name: str) -> Mapping[str, str] | None:
        return {"alpha": {"License": "GPL-3.0-only"}, "beta": {"Classifiers": ""}}.get(name)

    advisories = (
        Advisory("GHSA-Y", "alpha", "99.0"),
        Advisory("GHSA-X", "beta", "2.0", fix_versions=("2.1",)),
        Advisory("GHSA-53pm-wgxf-c6qf", "wcmatch", "8.5.2"),
    )

    def poster(payload: dict[str, object]) -> object:
        return {
            "results": [
                {"vulns": [{"id": "MAL-9", "summary": "malicious"}]},
                *[{} for _ in range(len(payload["queries"]) - 1)],
            ]
        }

    assessment = assess(
        root,
        today=TODAY,
        audit=lambda: controlled_audit(*advisories),
        license_reader=license_lookup,
        osv_poster=poster,
    )

    expected = {
        "SC-003",
        "SC-004",
        "SC-005",
        "SC-006",
        "SC-007",
        "SC-008",
        "SC-009",
        "SC-011",
        "SC-012",
        "SC-014",
        "SC-015",
    }
    assert expected <= codes(assessment)
    assert not assessment.passed
    assert len(assessment.blocking) >= 9
    assert any(finding.package == "alpha" for finding in assessment.blocking)
    assert "2.1" in next(
        finding.message
        for finding in assessment.findings
        if finding.code == "SC-012" and finding.package == "beta"
    )


def test_audit_failure_blocks(project: Path) -> None:
    assessment = assess(
        project,
        today=TODAY,
        audit=lambda: AuditOutcome((), error="scanner down"),
        license_reader=mit,
        online=False,
    )
    assert codes(assessment) == {"SC-010", "SC-013"}
    assert not assessment.passed


def test_active_exception_is_informational(project: Path) -> None:
    root = write_project(
        project,
        packages=(lock_entry("alpha", "1.2.3", dependencies=("beta",)), lock_entry("beta", "2.0")),
        exceptions=ACTIVE,
    )
    assessment = assess(
        root,
        today=TODAY,
        audit=lambda: controlled_audit(Advisory("GHSA-53pm-wgxf-c6qf", "wcmatch", "8.5.2")),
        license_reader=mit,
        online=False,
    )
    assert codes(assessment) == {"SC-013", "SC-016"}
    assert assessment.passed
    assert "2026-12-22" in next(
        finding.message for finding in assessment.findings if finding.code == "SC-016"
    )


def test_expired_exception_blocks(project: Path) -> None:
    assessment = assess(
        write_project(
            project,
            packages=(lock_entry("alpha", "1.2.3"),),
            exceptions=EXPIRED,
        ),
        today=TODAY,
        audit=lambda: controlled_audit(Advisory("GHSA-53pm-wgxf-c6qf", "wcmatch", "8.5.2")),
        license_reader=mit,
        online=False,
    )
    expired = [finding for finding in assessment.findings if finding.code == "SC-011"]
    assert len(expired) == 2  # matched advisory + unused stale exception
    assert not assessment.passed


def test_malicious_match_blocks_and_offline_is_review(project: Path) -> None:
    def poster(payload: dict[str, object]) -> object:
        return {"results": [{"vulns": [{"id": "MAL-1"}]}, {}]}

    blocked = assess(
        project,
        today=TODAY,
        audit=lambda: controlled_audit(),
        license_reader=mit,
        osv_poster=poster,
    )
    assert "SC-015" in codes(blocked)
    assert not blocked.passed

    def failing(payload: dict[str, object]) -> object:
        raise RuntimeError("network down")

    reviewed = assess(
        project,
        today=TODAY,
        audit=lambda: controlled_audit(),
        license_reader=mit,
        osv_poster=failing,
    )
    assert "SC-013" in codes(reviewed)
    assert reviewed.passed


def test_missing_policy_raises(tmp_path: Path) -> None:
    with pytest.raises(PolicyError):
        assess(tmp_path, audit=lambda: controlled_audit(), online=False)


def test_invalid_pyproject_blocks_with_sc_002(project: Path) -> None:
    (project / "pyproject.toml").write_text("not toml [", encoding="utf-8")
    assessment = assess(project, audit=lambda: controlled_audit(), online=False)
    assert codes(assessment) == {"SC-002"}
    assert assessment.records == ()


def test_missing_lockfile_blocks_with_sc_001(project: Path) -> None:
    (project / "uv.lock").unlink()
    assessment = assess(project, audit=lambda: controlled_audit(), online=False)
    assert codes(assessment) == {"SC-001"}


def test_vcs_and_url_sources_are_rejected(project: Path) -> None:
    root = write_project(
        project,
        packages=(lock_entry("alpha", "1.2.3", source='{ git = "https://example.invalid/a" }'),),
        dependencies=("alpha>=1.0",),
    )
    assessment = assess(
        root, today=TODAY, audit=lambda: controlled_audit(), license_reader=mit, online=False
    )
    assert "SC-005" in codes(assessment)
    assert any(finding.severity is Severity.BLOCKING for finding in assessment.findings)
