"""Workflow audit tests for Stage 10.

The fixture is the repository's own workflow, parsed and mutated. That keeps
the tests honest: if the real pipeline changes shape, these tests still assert
the audited properties, and a rule that stops firing shows up immediately.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from waxprep.ci.acceptance import ADVISORY_JOBS, REQUIRED_JOBS, TEST_CATEGORIES
from waxprep.ci.workflows import AuditFinding, audit_workflows

pytestmark = pytest.mark.regression

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = PROJECT_ROOT / ".github" / "workflows" / "quality-gate.yml"
PINNED = "actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683"
Mutator = Callable[[dict[str, Any]], None]


def workflow_document() -> dict[str, Any]:
    document = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def write_document(root: Path, document: Any, name: str = "quality-gate.yml") -> None:
    directory = root / ".github" / "workflows"
    directory.mkdir(parents=True, exist_ok=True)
    dumped = document if isinstance(document, str) else yaml.safe_dump(document, sort_keys=False)
    (directory / name).write_text(dumped, encoding="utf-8")


def audit_mutation(tmp_path: Path, mutate: Mutator) -> tuple[AuditFinding, ...]:
    document = workflow_document()
    mutate(document)
    write_document(tmp_path, document)
    return audit_workflows(tmp_path)


def rules(root: Path) -> set[str]:
    return {finding.rule for finding in audit_workflows(root)}


def job(document: dict[str, Any], job_id: str) -> dict[str, Any]:
    jobs: dict[str, Any] = document["jobs"]
    return jobs[job_id]


def step_containing(document: dict[str, Any], job_id: str, fragment: str) -> dict[str, Any]:
    for step in job(document, job_id)["steps"]:
        if fragment in str(step):
            return step
    raise AssertionError(f"job {job_id} has no step containing {fragment!r}")


def on_key(document: dict[str, Any]) -> Any:
    """Return whichever key carries the triggers (PyYAML reads ``on`` as True)."""
    return "on" if "on" in document else True


def drop_step(document: dict[str, Any], job_id: str, fragment: str) -> None:
    steps = job(document, job_id)["steps"]
    target = step_containing(document, job_id, fragment)
    steps.remove(target)


def replace_run(document: dict[str, Any], job_id: str, old: str, new: str) -> None:
    for step in job(document, job_id)["steps"]:
        text = step.get("run")
        if isinstance(text, str) and old in text:
            step["run"] = text.replace(old, new)
            return
    raise AssertionError(f"job {job_id} has no run step containing {old!r}")


def test_repository_workflows_are_clean() -> None:
    assert audit_workflows(PROJECT_ROOT) == ()


def test_parsed_and_redumped_workflow_passes(tmp_path: Path) -> None:
    write_document(tmp_path, workflow_document())

    assert audit_workflows(tmp_path) == ()


def test_missing_workflow_directory_is_reported(tmp_path: Path) -> None:
    findings = audit_workflows(tmp_path)

    assert [finding.rule for finding in findings] == ["missing-workflows"]


def test_invalid_yaml_is_reported(tmp_path: Path) -> None:
    write_document(tmp_path, "name: CI\non: [\n")

    assert "workflow-invalid" in rules(tmp_path)


def test_non_mapping_workflow_is_reported(tmp_path: Path) -> None:
    write_document(tmp_path, "- just a list\n")

    assert "workflow-invalid" in rules(tmp_path)


def test_missing_permissions_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document["permissions"]

    assert "workflow-permissions" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


def test_missing_jobs_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document["jobs"]

    findings = audit_mutation(tmp_path, mutate)

    assert "workflow-invalid" in {finding.rule for finding in findings}


def test_workflow_without_triggers_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document[on_key(document)]

    assert "workflow-invalid" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


@pytest.mark.parametrize("action", ["actions/checkout@v5", "actions/checkout@main"])
def test_mutable_action_reference_is_reported(tmp_path: Path, action: str) -> None:
    def mutate(document: dict[str, Any]) -> None:
        step_containing(document, "ci-audit", "actions/checkout")["uses"] = action

    assert "action-not-pinned" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


def test_container_action_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        step_containing(document, "ci-audit", "actions/checkout")["uses"] = "docker://alpine:3.20"

    assert "action-not-pinned" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


def test_local_composite_action_is_allowed(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        step_containing(document, "ci-audit", "actions/checkout")["uses"] = (
            "./.github/actions/ci-evidence"
        )

    assert audit_mutation(tmp_path, mutate) == ()


def test_missing_trigger_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document[on_key(document)]["workflow_dispatch"]

    assert "missing-trigger" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


def test_missing_required_job_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document["jobs"]["coverage-gate"]

    assert "missing-job" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


def test_missing_acceptance_job_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document["jobs"]["ci-acceptance"]

    findings = audit_mutation(tmp_path, mutate)

    assert "missing-job" in {finding.rule for finding in findings}
    assert any(
        finding.rule == "missing-job" and "ci-acceptance" in finding.message for finding in findings
    )


def test_missing_test_matrix_job_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document["jobs"]["tests"]

    assert "missing-job" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


def test_matrix_without_strategy_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del job(document, "tests")["strategy"]

    assert "matrix-mismatch" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


def test_matrix_diverging_from_declared_categories_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        job(document, "tests")["strategy"]["matrix"]["category"] = ["unit", "integration"]

    findings = audit_mutation(tmp_path, mutate)

    assert "matrix-mismatch" in {finding.rule for finding in findings}


def test_missing_evidence_recording_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        drop_step(document, "quality-gate", "--job quality-gate")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "missing-evidence-recording" and "quality-gate" in finding.message
        for finding in findings
    )


def test_missing_matrix_evidence_recording_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        drop_step(document, "tests", '--job "tests-${{ matrix.category }}"')

    assert "missing-evidence-recording" in {
        finding.rule for finding in audit_mutation(tmp_path, mutate)
    }


def test_missing_advisory_evidence_recording_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        drop_step(document, "vulture", "--job vulture")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "missing-evidence-recording" and "vulture" in finding.message
        for finding in findings
    )


def test_blocking_job_recorded_as_advisory_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(document, "smoke-test", "--class blocking", "--class advisory")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "misclassified-evidence" and "smoke-test" in finding.message
        for finding in findings
    )


def test_advisory_job_recorded_as_blocking_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(document, "pyright", "--class advisory", "--class blocking")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "misclassified-evidence" and "pyright" in finding.message
        for finding in findings
    )


def test_missing_evidence_artifact_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        drop_step(document, "smoke-test", "ci-evidence-smoke-test")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "evidence-artifact-missing" and "smoke-test" in finding.message
        for finding in findings
    )


def test_evidence_artifact_from_the_wrong_directory_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        step = step_containing(document, "ci-audit", "ci-evidence-ci-audit")
        step["with"]["path"] = "artifacts/"

    findings = audit_mutation(tmp_path, mutate)

    assert any(finding.rule == "evidence-artifact-mismatch" for finding in findings)


def test_acceptance_without_an_evidence_download_pattern_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        drop_step(document, "ci-acceptance", "ci-evidence-*")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "acceptance-download-mismatch" and "pattern" in finding.message
        for finding in findings
    )


def test_acceptance_without_a_required_report_download_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        drop_step(document, "ci-acceptance", "coverage-report")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "acceptance-download-mismatch" and "coverage-report" in finding.message
        for finding in findings
    )


def test_report_artifact_from_an_unexpected_job_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        step = step_containing(document, "coverage-gate", "coverage-report")
        step["with"]["name"] = "coverage-xml"

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "report-producer-mismatch" and "coverage-report" in finding.message
        for finding in findings
    )


def test_acceptance_without_a_coverage_argument_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(document, "ci-acceptance", "--coverage reports/coverage.xml", "")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "acceptance-report-missing" and "coverage" in finding.message
        for finding in findings
    )


def test_acceptance_without_an_sbom_argument_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(
            document,
            "ci-acceptance",
            "--sbom reports/supply-chain/waxprep-sbom.cdx.json",
            "",
        )

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "acceptance-report-missing" and "SBOM" in finding.message
        for finding in findings
    )


def test_acceptance_validating_the_wrong_coverage_file_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(
            document,
            "ci-acceptance",
            "--coverage reports/coverage.xml",
            "--coverage evidence/coverage.xml",
        )

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "report-producer-mismatch" and "coverage" in finding.message
        for finding in findings
    )


def test_acceptance_validating_an_unrelated_sbom_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(
            document,
            "ci-acceptance",
            "reports/supply-chain/waxprep-sbom.cdx.json",
            "reports/supply-chain/old-sbom.json",
        )

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "report-producer-mismatch" and "SBOM" in finding.message
        for finding in findings
    )


def test_acceptance_job_not_running_always_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del job(document, "ci-acceptance")["if"]

    findings = audit_mutation(tmp_path, mutate)

    assert any(finding.rule == "acceptance-not-always" for finding in findings)


def test_acceptance_job_missing_a_mandatory_dependency_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        needs = job(document, "ci-acceptance")["needs"]
        needs.remove("smoke-test")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "acceptance-missing-dependency" and "smoke-test" in finding.message
        for finding in findings
    )


def test_acceptance_job_depending_on_an_undeclared_job_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        job(document, "ci-acceptance")["needs"].append("lint")

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "acceptance-unknown-dependency" and "lint" in finding.message
        for finding in findings
    )


@pytest.mark.parametrize("timeout", [None, 0, "ten"])
def test_job_without_a_positive_timeout_is_reported(tmp_path: Path, timeout: object) -> None:
    def mutate(document: dict[str, Any]) -> None:
        if timeout is None:
            del job(document, "smoke-test")["timeout-minutes"]
        else:
            job(document, "smoke-test")["timeout-minutes"] = timeout

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "missing-timeout" and "smoke-test" in finding.message
        for finding in findings
    )


def test_job_outside_the_acceptance_policy_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["jobs"]["lint"] = {
            "runs-on": "ubuntu-latest",
            "timeout-minutes": 5,
            "steps": [{"uses": PINNED}],
        }

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "unregistered-job" and "lint" in finding.message for finding in findings
    )


def test_job_definition_that_is_not_a_mapping_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["jobs"]["vulture"] = []

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "workflow-invalid" and "vulture" in finding.message for finding in findings
    )


def test_job_with_an_unusable_steps_block_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        job(document, "vulture")["steps"] = "uv run vulture"

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "missing-evidence-recording" and "vulture" in finding.message
        for finding in findings
    )


def test_jobs_block_that_is_not_a_mapping_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        document["jobs"] = ["ci-audit"]

    assert "workflow-invalid" in {finding.rule for finding in audit_mutation(tmp_path, mutate)}


def test_evidence_path_with_an_explicit_relative_prefix_is_accepted(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        step = step_containing(document, "ci-audit", "ci-evidence-ci-audit")
        step["with"]["path"] = "./ci-evidence/"

    assert audit_mutation(tmp_path, mutate) == ()


def test_acceptance_with_a_string_needs_entry_is_audited(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        job(document, "ci-acceptance")["needs"] = "smoke-test"

    findings = audit_mutation(tmp_path, mutate)

    assert any(finding.rule == "acceptance-missing-dependency" for finding in findings)


def test_acceptance_without_needs_is_audited(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del job(document, "ci-acceptance")["needs"]

    findings = audit_mutation(tmp_path, mutate)

    assert any(finding.rule == "acceptance-missing-dependency" for finding in findings)


def test_acceptance_with_an_unusable_needs_value_is_audited(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        job(document, "ci-acceptance")["needs"] = 42

    findings = audit_mutation(tmp_path, mutate)

    assert any(finding.rule == "acceptance-missing-dependency" for finding in findings)


def test_sbom_validated_outside_its_download_directory_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(
            document,
            "ci-acceptance",
            "reports/supply-chain/waxprep-sbom.cdx.json",
            "reports/other/waxprep-sbom.cdx.json",
        )

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "report-producer-mismatch" and "SBOM" in finding.message
        for finding in findings
    )


def test_sbom_argument_without_a_directory_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(
            document,
            "ci-acceptance",
            "reports/supply-chain/waxprep-sbom.cdx.json",
            "waxprep-sbom.cdx.json",
        )

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "report-producer-mismatch" and "SBOM" in finding.message
        for finding in findings
    )


def test_coverage_argument_without_a_directory_is_reported(tmp_path: Path) -> None:
    def mutate(document: dict[str, Any]) -> None:
        replace_run(
            document, "ci-acceptance", "--coverage reports/coverage.xml", "--coverage coverage.xml"
        )

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "report-producer-mismatch" and "coverage" in finding.message
        for finding in findings
    )


def test_acceptance_validating_an_sbom_from_a_missing_producer_is_reported(
    tmp_path: Path,
) -> None:
    def mutate(document: dict[str, Any]) -> None:
        del document["jobs"]["supply-chain-evidence"]

    findings = audit_mutation(tmp_path, mutate)

    assert any(
        finding.rule == "report-producer-mismatch" and "supply-chain-evidence" in finding.message
        for finding in findings
    )


def test_matrix_categories_match_the_declared_tuple() -> None:
    matrix = job(workflow_document(), "tests")["strategy"]["matrix"]["category"]

    assert tuple(matrix) == TEST_CATEGORIES


def test_required_jobs_are_all_declared_in_the_workflow() -> None:
    jobs = workflow_document()["jobs"]

    for job_id in (*REQUIRED_JOBS, *ADVISORY_JOBS):
        workflow_job = "tests" if job_id.startswith("tests-") else job_id
        assert workflow_job in jobs


def test_unreadable_workflow_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_document(tmp_path, workflow_document())
    original = Path.read_text

    def deny(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == "quality-gate.yml":
            raise OSError("permission denied")
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", deny)

    assert "workflow-unreadable" in rules(tmp_path)


def test_findings_are_scoped_to_the_offending_workflow(tmp_path: Path) -> None:
    write_document(tmp_path, workflow_document())
    write_document(tmp_path, "name: Dependency Review\non:\n  pull_request:\n", "other.yml")

    findings = audit_workflows(tmp_path)

    assert findings
    assert {finding.workflow for finding in findings} == {"other.yml"}
