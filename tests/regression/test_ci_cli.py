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
    ExecutionPhase,
    Status,
    evaluate_acceptance,
)
from waxprep.ci.cli import main
from waxprep.ci.evidence import build_record, write_record
from waxprep.ci.report import decision_to_dict, render_markdown

pytestmark = pytest.mark.regression

COMMIT = "a" * 40
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "quality-gate.yml"


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


def write_reports(directory: Path, rate: str = "1.0") -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    coverage = directory / "coverage.xml"
    coverage.write_text(f'<?xml version="1.0" ?><coverage line-rate="{rate}"></coverage>', "utf-8")
    sbom = directory / "sbom.json"
    sbom.write_text(
        json.dumps({
            "bomFormat": "CycloneDX",
            "components": [{"name": "fastapi", "purl": "pkg:pypi/fastapi@1.0.0"}],
        }),
        encoding="utf-8",
    )
    return coverage, sbom


def accept_arguments(tmp_path: Path, evidence: Path, coverage: Path, sbom: Path) -> list[str]:
    return [
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
    ]


def write_repository_workflow(root: Path) -> None:
    directory = root / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "quality-gate.yml").write_text(
        REPOSITORY_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8"
    )


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


def test_record_stores_the_execution_phase(tmp_path: Path) -> None:
    assert (
        main([
            "record",
            "--job",
            "pyright",
            "--class",
            "advisory",
            "--status",
            "failure",
            "--phase",
            "setup",
            "--commit",
            COMMIT,
            "--run-id",
            "1-1",
            "--output",
            str(tmp_path / "evidence"),
        ])
        == 0
    )

    payload = json.loads((tmp_path / "evidence" / "pyright.json").read_text(encoding="utf-8"))

    assert payload["phase"] == ExecutionPhase.SETUP.value


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


def test_record_rejects_an_unusable_run_id(
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
        "local",
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
        *accept_arguments(tmp_path, evidence, coverage, sbom),
        "--summary",
        str(summary),
    ])

    assert status == 0
    written = json.loads(report.read_text(encoding="utf-8"))
    assert written["accepted"] is True
    assert written["advisory"] == [
        {"job": "pyright", "state": "passed"},
        {"job": "vulture", "state": "passed"},
    ]
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

    status = main(accept_arguments(tmp_path, tmp_path / "absent-evidence", coverage, sbom))

    assert status == 1


def test_accept_rejects_an_empty_download_directory(tmp_path: Path) -> None:
    """A failed artifact download leaves an empty (or absent) evidence directory."""
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    coverage, sbom = write_reports(tmp_path / "reports")

    status = main(accept_arguments(tmp_path, evidence, coverage, sbom))

    written = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))

    assert status == 1
    assert len(written["failures"]) == len(REQUIRED_JOBS)


def test_accept_rejects_coverage_below_the_policy_threshold(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    write_evidence(evidence)
    coverage, sbom = write_reports(tmp_path / "reports", rate="0.99")

    status = main(accept_arguments(tmp_path, evidence, coverage, sbom))

    written = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))

    assert status == 1
    assert any("below the required" in failure for failure in written["failures"])


def test_accept_rejects_a_failing_required_job(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    write_evidence(evidence)
    write_record(
        evidence,
        build_record(
            job="smoke-test",
            check_class=CheckClass.BLOCKING.value,
            status=Status.FAILURE.value,
            commit=COMMIT,
            workflow_run_id="1-1",
            exit_code=1,
        ),
    )
    coverage, sbom = write_reports(tmp_path / "reports")

    status = main(accept_arguments(tmp_path, evidence, coverage, sbom))

    written = json.loads((tmp_path / "acceptance.json").read_text(encoding="utf-8"))

    assert status == 1
    assert "required job 'smoke-test' finished as failure" in written["failures"]


def test_accept_rejects_unreadable_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "broken.json").write_text("{", encoding="utf-8")
    coverage, sbom = write_reports(tmp_path / "reports")

    status = main(accept_arguments(tmp_path, evidence, coverage, sbom))

    assert status == 1
    assert "CI evidence error" in capsys.readouterr().err


def test_accept_rejects_a_job_record_filed_under_the_wrong_name(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    write_evidence(evidence)
    payload = json.loads((evidence / "smoke-test.json").read_text(encoding="utf-8"))
    payload["job"] = "quality-gate"
    (evidence / "smoke-test.json").write_text(json.dumps(payload), encoding="utf-8")
    coverage, sbom = write_reports(tmp_path / "reports")

    status = main(accept_arguments(tmp_path, evidence, coverage, sbom))

    assert status == 1


def test_audit_passes_for_the_repository_workflow(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_repository_workflow(tmp_path)

    assert main(["audit", "--root", str(tmp_path)]) == 0
    assert "Workflow audit PASSED" in capsys.readouterr().out


def test_module_main_block_exits_with_the_audit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_repository_workflow(tmp_path)
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
    assert "(none recorded)" in markdown
    assert decision_to_dict(decision)["observed"] == []
    assert decision_to_dict(decision)["advisory"] == []


def test_render_markdown_lists_failures_and_warnings() -> None:
    decision = evaluate_acceptance([], COMMIT)

    markdown = render_markdown(decision)
    payload = decision_to_dict(decision)

    assert "REJECTED" in markdown
    assert "produced no evidence" in markdown
    assert payload["accepted"] is False
    assert payload["failures"]
    assert payload["advisory"] == [
        {"job": "pyright", "state": "missing"},
        {"job": "vulture", "state": "missing"},
    ]


def test_render_markdown_separates_advisory_execution_states() -> None:
    records = [
        build_record(
            job=job,
            check_class=CheckClass.ADVISORY.value,
            status=Status.FAILURE.value,
            commit=COMMIT,
            workflow_run_id="1-1",
            exit_code=1,
            phase=ExecutionPhase.SETUP.value,
        )
        for job in ADVISORY_JOBS
    ]

    markdown = render_markdown(evaluate_acceptance(records, COMMIT))

    assert "### Advisory checks (non-blocking)" in markdown
    assert "| pyright | infrastructure-failure |" in markdown
    assert "| vulture | infrastructure-failure |" in markdown
