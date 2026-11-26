"""CLI and report-rendering tests for Stage 10."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path

import pytest

from waxprep.ci.acceptance import (
    ADVISORY_JOBS,
    REQUIRED_JOBS,
    AcceptanceDecision,
    CheckClass,
    Status,
    evaluate_acceptance,
)
from waxprep.ci.cli import main
from waxprep.ci.evidence import build_record, write_record
from waxprep.ci.report import decision_to_dict, render_markdown

pytestmark = pytest.mark.regression

COMMIT = "a" * 40


def write_evidence(directory: Path, commit: str = COMMIT) -> None:
    for job in REQUIRED_JOBS:
        write_record(
            directory,
            build_record(
                job=job,
                check_class=CheckClass.BLOCKING.value,
                status=Status.SUCCESS.value,
                commit=commit,
                workflow_run_id="1-1",
                exit_code=0,
            ),
        )
    for job in ADVISORY_JOBS:
        write_record(
            directory,
            build_record(
                job=job,
                check_class=CheckClass.ADVISORY.value,
                status=Status.SUCCESS.value,
                commit=commit,
                workflow_run_id="1-1",
            ),
        )


def write_reports(directory: Path) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    coverage = directory / "coverage.xml"
    coverage.write_text('<?xml version="1.0" ?><coverage line-rate="1.0"></coverage>', "utf-8")
    sbom = directory / "sbom.json"
    sbom.write_text(
        json.dumps({
            "bomFormat": "CycloneDX",
            "components": [{"name": "fastapi", "purl": "pkg:pypi/fastapi@1.0.0"}],
        }),
        encoding="utf-8",
    )
    return coverage, sbom


def test_record_writes_evidence_and_reports_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = main([
        "record",
        "--job",
        "quality-gate",
        "--class",
        "blocking",
        "--status",
        "success",
        "--commit",
        COMMIT,
        "--run-id",
        "1-1",
        "--output",
        str(tmp_path / "evidence"),
    ])

    assert status == 0
    assert (tmp_path / "evidence" / "quality-gate.json").exists()
    assert "Recorded quality-gate evidence" in capsys.readouterr().out


def test_record_rejects_unusable_status(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    status = main([
        "record",
        "--job",
        "quality-gate",
        "--class",
        "blocking",
        "--status",
        "neutral",
        "--commit",
        COMMIT,
        "--run-id",
        "1-1",
        "--output",
        str(tmp_path),
    ])

    assert status == 1
    assert "CI evidence error" in capsys.readouterr().err


def test_accept_accepts_when_evidence_and_reports_are_valid(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evidence = tmp_path / "evidence"
    write_evidence(evidence)
    coverage, sbom = write_reports(tmp_path / "reports")
    report = tmp_path / "acceptance.json"
    summary = tmp_path / "summary.md"

    status = main([
        "accept",
        "--evidence-dir",
        str(evidence),
        "--commit",
        COMMIT,
        "--coverage",
        str(coverage),
        "--sbom",
        str(sbom),
        "--report",
        str(report),
        "--summary",
        str(summary),
    ])

    assert status == 0
    assert json.loads(report.read_text(encoding="utf-8"))["accepted"] is True
    assert "CI Acceptance Report" in summary.read_text(encoding="utf-8")
    assert "ACCEPTED" in capsys.readouterr().out


def test_accept_rejects_missing_required_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evidence = tmp_path / "evidence"
    write_evidence(evidence)
    report = tmp_path / "acceptance.json"

    status = main([
        "accept",
        "--evidence-dir",
        str(evidence),
        "--commit",
        COMMIT,
        "--coverage",
        str(tmp_path / "absent.xml"),
        "--sbom",
        str(tmp_path / "absent.json"),
        "--report",
        str(report),
    ])

    assert status == 1
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["accepted"] is False
    assert len(written["failures"]) == 2
    assert "REJECTED" in capsys.readouterr().err


def test_accept_rejects_missing_evidence(tmp_path: Path) -> None:
    coverage, sbom = write_reports(tmp_path / "reports")

    status = main([
        "accept",
        "--evidence-dir",
        str(tmp_path / "absent-evidence"),
        "--commit",
        COMMIT,
        "--coverage",
        str(coverage),
        "--sbom",
        str(sbom),
        "--report",
        str(tmp_path / "acceptance.json"),
    ])

    assert status == 1


def test_accept_rejects_unreadable_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "broken.json").write_text("{", encoding="utf-8")
    coverage, sbom = write_reports(tmp_path / "reports")

    status = main([
        "accept",
        "--evidence-dir",
        str(evidence),
        "--commit",
        COMMIT,
        "--coverage",
        str(coverage),
        "--sbom",
        str(sbom),
        "--report",
        str(tmp_path / "acceptance.json"),
    ])

    assert status == 1
    assert "CI evidence error" in capsys.readouterr().err


def test_audit_passes_for_clean_workflows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.regression.test_ci_workflows import build_workflow, write_workflow

    write_workflow(tmp_path, build_workflow())

    assert main(["audit", "--root", str(tmp_path)]) == 0
    assert "Workflow audit PASSED" in capsys.readouterr().out


def test_module_main_block_exits_with_the_audit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.regression.test_ci_workflows import build_workflow, write_workflow

    write_workflow(tmp_path, build_workflow())
    monkeypatch.setattr(sys, "argv", ["cli", "audit", "--root", str(tmp_path)])

    with pytest.warns(RuntimeWarning), pytest.raises(SystemExit) as exit_info:
        runpy.run_module("waxprep.ci.cli", run_name="__main__")

    assert exit_info.value.code == 0


def test_audit_reports_findings_and_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "quality-gate.yml").write_text("name: CI\n", encoding="utf-8")

    status = main(["audit", "--root", str(tmp_path)])

    assert status == 1
    output = capsys.readouterr()
    assert "workflow-invalid" in output.out
    assert "Workflow audit FAILED" in output.err


def test_render_markdown_handles_an_empty_decision() -> None:
    decision = AcceptanceDecision(
        accepted=True,
        commit=COMMIT,
        failures=(),
        warnings=(),
        observed=(),
    )

    markdown = render_markdown(decision)

    assert "ACCEPTED" in markdown
    assert "(no evidence recorded)" in markdown
    assert decision_to_dict(decision)["observed"] == []


def test_render_markdown_lists_failures_and_warnings() -> None:
    decision = evaluate_acceptance([], COMMIT)

    markdown = render_markdown(decision)
    payload = decision_to_dict(decision)

    assert "REJECTED" in markdown
    assert "produced no evidence" in markdown
    assert payload["accepted"] is False
    assert payload["failures"]
