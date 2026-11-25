"""SBOM, report and CLI tests for Stage 09."""

from __future__ import annotations

import runpy
import sys
from datetime import date
from pathlib import Path

import pytest

from waxprep.supplychain.checks import Assessment, DependencyRecord, Finding, Severity
from waxprep.supplychain.cli import main
from waxprep.supplychain.policy import LicenseDecision, PolicyError
from waxprep.supplychain.report import assessment_to_dict, render_trust_markdown
from waxprep.supplychain.sbom import build_sbom, write_sbom


def record(
    name: str,
    *,
    version: str = "1.0",
    direct: bool = True,
    hashes: tuple[str, ...] = ("sha256:abc",),
    license_id: str | None = "MIT",
    decision: LicenseDecision = LicenseDecision.APPROVED,
    advisories: tuple[str, ...] = (),
) -> DependencyRecord:
    return DependencyRecord(
        name=name,
        version=version,
        direct=direct,
        source_type="registry",
        source_url="https://pypi.org/simple",
        has_hashes=bool(hashes),
        hashes=hashes,
        license_id=license_id,
        license_decision=decision,
        advisories=advisories,
    )


def assessment(
    *, findings: tuple[Finding, ...] = (), records: tuple[DependencyRecord, ...] | None = None
) -> Assessment:
    return Assessment(
        root=Path("."),
        today=date(2026, 11, 25),
        records=records if records is not None else (record("alpha"),),
        findings=findings,
    )


def test_sbom_contains_runtime_components_and_hashes() -> None:
    report = build_sbom(
        assessment(
            records=(
                record("alpha"),
                record(
                    "beta",
                    direct=False,
                    hashes=(),
                    license_id=None,
                    decision=LicenseDecision.UNKNOWN,
                ),
            )
        )
    )
    assert report["bomFormat"] == "CycloneDX"
    assert report["specVersion"] == "1.5"
    components = report["components"]
    assert isinstance(components, list)
    first = components[0]
    assert isinstance(first, dict)
    assert first["purl"] == "pkg:pypi/alpha@1.0"
    assert first["hashes"] == [{"alg": "SHA-256", "content": "abc"}]
    assert "licenses" in first
    second = components[1]
    assert isinstance(second, dict)
    assert "hashes" not in second
    assert "licenses" not in second
    metadata = report["metadata"]
    assert isinstance(metadata, dict)
    dependencies = report["dependencies"]
    assert isinstance(dependencies, list)
    assert len(dependencies) == 3


def test_sbom_ignores_unusable_hashes() -> None:
    report = build_sbom(assessment(records=(record("alpha", hashes=("md5:abc", "sha256:")),)))
    components = report["components"]
    assert isinstance(components, list)
    component = components[0]
    assert isinstance(component, dict)
    assert "hashes" not in component


def test_write_sbom_creates_parent_directories(tmp_path: Path) -> None:
    path = write_sbom(assessment(), tmp_path / "nested" / "sbom.json")
    assert path.exists()
    assert '"CycloneDX"' in path.read_text(encoding="utf-8")


def test_trust_report_renders_every_section() -> None:
    markdown = render_trust_markdown(
        assessment(
            records=(
                record("alpha", advisories=("GHSA-1",)),
                record(
                    "beta",
                    direct=False,
                    hashes=(),
                    license_id="GPL-3.0-only",
                    decision=LicenseDecision.PROHIBITED,
                ),
            ),
            findings=(
                Finding("SC-008", Severity.BLOCKING, "prohibited license", "beta"),
                Finding("SC-009", Severity.REVIEW, "needs review", "alpha"),
                Finding("SC-017", Severity.INFO, "provenance unverified"),
            ),
        )
    )
    assert "Decision: **BLOCK**" in markdown
    assert "GHSA-1" in markdown
    assert "GPL-3.0-only (prohibited)" in markdown
    assert "## Blocking findings" in markdown
    assert "## Review findings" in markdown
    assert "## Informational findings" in markdown
    assert "SC-017" in markdown


def test_trust_report_with_no_findings_says_none() -> None:
    markdown = render_trust_markdown(assessment())
    assert markdown.count("None.") == 3


def test_assessment_json_round_trip() -> None:
    payload = assessment_to_dict(
        assessment(findings=(Finding("SC-001", Severity.BLOCKING, "missing"),))
    )
    assert payload["passed"] is False
    assert payload["blocking"] == 1
    assert payload["review"] == 0
    assert isinstance(payload["records"], list)
    assert isinstance(payload["findings"], list)


@pytest.fixture
def stub_assess(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, object]]:
    calls: list[dict[str, object]] = []

    def fake(root: Path, *, today: date | None = None, online: bool = True) -> Assessment:
        calls.append({"root": root, "today": today, "online": online})
        return assessment()

    monkeypatch.setattr("waxprep.supplychain.cli.assess", fake)
    return calls


def test_cli_check_summary_and_json(
    stub_assess: list[dict[str, object]], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["check", "--offline", "--today", "2026-11-25"]) == 0
    assert "Dependency Trust: PASSED" in capsys.readouterr().out
    assert main(["check", "--format", "json"]) == 0
    payload = capsys.readouterr().out
    assert '"passed": true' in payload
    assert stub_assess[0]["today"] == date(2026, 11, 25)
    assert stub_assess[0]["online"] is False


def test_cli_check_returns_one_when_blocked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    blocked = assessment(findings=(Finding("SC-001", Severity.BLOCKING, "missing"),))
    monkeypatch.setattr("waxprep.supplychain.cli.assess", lambda *args, **kwargs: blocked)
    assert main(["check"]) == 1
    assert "BLOCKED" in capsys.readouterr().out


def test_cli_policy_error_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def explode(*args: object, **kwargs: object) -> Assessment:
        raise PolicyError("missing policy")

    monkeypatch.setattr("waxprep.supplychain.cli.assess", explode)
    assert main(["check"]) == 1
    assert "Dependency policy error: missing policy" in capsys.readouterr().err


def test_cli_trust_to_stdout_and_file(
    stub_assess: list[dict[str, object]],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["trust"]) == 0
    assert "# Dependency Trust Intelligence" in capsys.readouterr().out

    output = tmp_path / "reports" / "trust.md"
    assert main(["trust", "--output", str(output)]) == 0
    assert output.exists()
    assert "Dependency Trust report written" in capsys.readouterr().out


def test_cli_trust_returns_one_when_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    blocked = assessment(findings=(Finding("SC-001", Severity.BLOCKING, "missing"),))
    monkeypatch.setattr("waxprep.supplychain.cli.assess", lambda *args, **kwargs: blocked)
    assert main(["trust", "--output", str(tmp_path / "trust.md")]) == 1


def test_module_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("waxprep.supplychain.checks.assess", lambda *args, **kwargs: assessment())
    monkeypatch.setattr(sys, "argv", ["cli", "check", "--offline"])
    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as exit_info:
        runpy.run_module("waxprep.supplychain.cli", run_name="__main__")
    assert exit_info.value.code == 0


def test_cli_sbom_writes_file(
    stub_assess: list[dict[str, object]], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "sbom.json"
    assert main(["sbom", "--output", str(output)]) == 0
    assert output.exists()
    assert "CycloneDX SBOM written" in capsys.readouterr().out
