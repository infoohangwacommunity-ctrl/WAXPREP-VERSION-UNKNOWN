"""Scanner and license-adapter tests for Stage 09."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from datetime import date
from pathlib import Path

import httpx
import pytest

from waxprep.supplychain.audit import (
    Advisory,
    AuditOutcome,
    parse_audit_report,
    run_pip_audit,
)
from waxprep.supplychain.checks import Assessment, Finding, Severity
from waxprep.supplychain.licenses import (
    license_from_metadata,
    normalize_license,
    read_distribution_metadata,
)
from waxprep.supplychain.osv import (
    MALICIOUS_PREFIX,
    MaliciousMatch,
    check_malicious,
    parse_osv_response,
)
from waxprep.supplychain.policy import LicenseDecision, LicensePolicy
from waxprep.supplychain.report import render_summary


def test_parse_audit_report_reads_advisories_and_skips_unaudited_entries() -> None:
    advisories = parse_audit_report({
        "dependencies": [
            {
                "name": "wcmatch",
                "version": "8.5.2",
                "vulns": [
                    {
                        "id": "GHSA-53pm-wgxf-c6qf",
                        "aliases": ["CVE-2025-1"],
                        "fix_versions": ["11.2"],
                        "description": "issue",
                    }
                ],
            },
            {"name": "waxprep", "skip_reason": "local project"},
            {"name": "clean", "version": "1.0", "vulns": [{"id": "GHSA-2"}]},
        ]
    })
    assert advisories == (
        Advisory(
            advisory_id="GHSA-53pm-wgxf-c6qf",
            package="wcmatch",
            version="8.5.2",
            aliases=("CVE-2025-1",),
            fix_versions=("11.2",),
            description="issue",
        ),
        Advisory(advisory_id="GHSA-2", package="clean", version="1.0"),
    )
    assert advisories[0].identifiers == ("GHSA-53pm-wgxf-c6qf", "CVE-2025-1")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (1, "expected an object"),
        ({}, "'dependencies' must be an array"),
        ({"dependencies": [1]}, "expected an object"),
        ({"dependencies": [{"name": "x"}]}, "name and version are required"),
        ({"dependencies": [{"name": "x", "version": "1", "vulns": 1}]}, "expected an array"),
        ({"dependencies": [{"name": "x", "version": "1", "vulns": [1]}]}, "expected an object"),
        (
            {"dependencies": [{"name": "x", "version": "1", "vulns": [{"id": ""}]}]},
            "'id' is required",
        ),
        (
            {
                "dependencies": [
                    {"name": "x", "version": "1", "vulns": [{"id": "GHSA-1", "aliases": "x"}]}
                ]
            },
            "array of strings",
        ),
    ],
)
def test_parse_audit_report_rejects_bad_shape(payload: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_audit_report(payload)


def completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["pip-audit"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def test_run_pip_audit_accepts_zero_and_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed(0, '{"dependencies": []}'),
    )
    assert run_pip_audit() == AuditOutcome(advisories=())
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: completed(1, '{"dependencies": []}')
    )
    assert run_pip_audit(("pip-audit",)).advisories == ()


def test_run_pip_audit_reports_tool_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(2, stderr="boom"))
    outcome = run_pip_audit()
    assert outcome.error is not None
    assert "exited 2" in outcome.error
    assert "boom" in outcome.error

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(2))
    outcome = run_pip_audit()
    assert outcome.error is not None
    assert "no diagnostic output" in outcome.error

    def explode(*args: object, **kwargs: object) -> None:
        raise OSError("no binary")

    monkeypatch.setattr(subprocess, "run", explode)
    assert run_pip_audit().error is not None

    def timeout(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="pip-audit", timeout=1)

    monkeypatch.setattr(subprocess, "run", timeout)
    assert run_pip_audit().error is not None

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(0, "not json"))
    assert run_pip_audit().error is not None

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: completed(0, "{}"))
    assert run_pip_audit().error is not None


def test_normalize_license() -> None:
    assert normalize_license(None) is None
    assert normalize_license("  ") is None
    assert normalize_license("UNKNOWN") is None
    assert normalize_license("MIT License") == "MIT"
    assert normalize_license("Apache Software License") == "Apache-2.0"
    assert normalize_license("MIT OR Apache-2.0") == "MIT OR Apache-2.0"
    assert normalize_license("Custom License") == "Custom License"


def test_license_from_metadata_prefers_expression_then_license_then_classifier() -> None:
    policies: Mapping[str, Mapping[str, str] | None] = {
        "expression": {"License-Expression": "MIT", "License": "ignored"},
        "legacy": {"License-Expression": "", "License": "BSD License"},
        "classifier": {
            "Classifiers": "Programming Language :: Python; License :: OSI Approved :: MIT License"
        },
        "unknown": {"Classifiers": "Programming Language :: Python"},
        "missing": None,
    }
    lookup = policies.__getitem__
    assert license_from_metadata("expression", lookup) == "MIT"
    assert license_from_metadata("legacy", lookup) == "BSD-3-Clause"
    assert license_from_metadata("classifier", lookup) == "MIT"
    assert license_from_metadata("unknown", lookup) is None
    assert license_from_metadata("missing", lookup) is None


def test_read_distribution_metadata() -> None:
    assert read_distribution_metadata("pytest") is not None
    assert read_distribution_metadata("package-that-does-not-exist") is None


def test_parse_osv_response_keeps_only_malicious_advisories() -> None:
    packages = (("alpha", "1.0"), ("beta", "2.0"))
    matches = parse_osv_response(
        {
            "results": [
                {"vulns": [{"id": "MAL-1", "summary": "malicious"}, {"id": "GHSA-1"}]},
                {},
            ]
        },
        packages,
    )
    assert matches == (MaliciousMatch("alpha", "1.0", "MAL-1", "malicious"),)
    assert MALICIOUS_PREFIX == "MAL-"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (1, "expected an object"),
        ({}, "do not match"),
        ({"results": [1]}, "expected an object"),
        ({"results": [{"vulns": 1}]}, "expected an array"),
        ({"results": [{"vulns": [1]}]}, "expected an object"),
    ],
)
def test_parse_osv_response_rejects_bad_shape(payload: object, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_osv_response(payload, (("alpha", "1.0"),))


def test_check_malicious_uses_injected_transport() -> None:
    assert check_malicious(()) == check_malicious(())
    assert check_malicious(()).matches == ()

    def poster(payload: dict[str, object]) -> object:
        assert payload["queries"]
        return {"results": [{"vulns": [{"id": "MAL-2", "summary": "bad"}]}]}

    outcome = check_malicious([("alpha", "1.0")], poster)
    assert outcome.error is None
    assert outcome.matches[0].advisory_id == "MAL-2"

    def broken(payload: dict[str, object]) -> object:
        raise RuntimeError("offline")

    failed = check_malicious([("alpha", "1.0")], broken)
    assert failed.error is not None
    assert "offline" in failed.error


def test_default_osv_poster_uses_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> object:
            return {"results": [{}]}

    monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: Response())
    assert check_malicious([("alpha", "1.0")]).matches == ()


def test_report_and_policy_helpers() -> None:
    assessment = Assessment(
        root=Path("."),
        today=date(2026, 11, 25),
        records=(),
        findings=(
            Finding("SC-001", Severity.BLOCKING, "blocked", "alpha"),
            Finding("SC-009", Severity.REVIEW, "review", "beta"),
        ),
    )
    summary = render_summary(assessment)
    assert "BLOCKED" in summary
    assert "BLOCK SC-001 [alpha]" in summary
    assert "REVIEW SC-009 [beta]" in summary
    policy = LicensePolicy(frozenset({"MIT"}), frozenset(), frozenset())
    assert policy.classify("MIT OR MIT") is LicenseDecision.APPROVED
