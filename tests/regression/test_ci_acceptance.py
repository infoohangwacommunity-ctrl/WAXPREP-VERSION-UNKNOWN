"""Adversarial acceptance-engine tests for Stage 10.

Every case here is a failure of the enforcement machinery itself: skipped jobs,
cancelled jobs, missing evidence, stale commits and duplicate records must all
prevent acceptance. These tests are what makes the CI decision trustworthy.
"""

from __future__ import annotations

import pytest

from waxprep.ci.acceptance import (
    ADVISORY_JOBS,
    REQUIRED_JOBS,
    TEST_CATEGORIES,
    CheckClass,
    JobRecord,
    Status,
    evaluate_acceptance,
    is_full_commit,
)

pytestmark = pytest.mark.regression

COMMIT = "a" * 40
OTHER_COMMIT = "b" * 40


def make_record(
    job: str,
    *,
    status: Status = Status.SUCCESS,
    commit: str = COMMIT,
    check_class: CheckClass = CheckClass.BLOCKING,
) -> JobRecord:
    return JobRecord(
        job=job,
        check_class=check_class,
        status=status,
        commit=commit,
        workflow_run_id="12345-1",
        recorded_at="2026-11-25T00:00:00+00:00",
        exit_code=0,
    )


def successful_evidence() -> list[JobRecord]:
    records = [make_record(job) for job in REQUIRED_JOBS]
    records.extend(make_record(job, check_class=CheckClass.ADVISORY) for job in ADVISORY_JOBS)
    return records


def failure_text(decision_failures: tuple[str, ...]) -> str:
    return "\n".join(decision_failures)


def test_all_required_jobs_succeed_and_advisories_succeed() -> None:
    decision = evaluate_acceptance(successful_evidence(), COMMIT)

    assert decision.accepted is True
    assert decision.failures == ()
    assert decision.warnings == ()
    assert decision.commit == COMMIT
    assert dict(decision.observed)["quality-gate"] == "success"


def test_required_jobs_cover_every_declared_test_category() -> None:
    for category in TEST_CATEGORIES:
        assert f"tests-{category}" in REQUIRED_JOBS


def test_advisory_failure_is_a_warning_not_a_rejection() -> None:
    records = successful_evidence()
    records = [
        make_record(record.job, status=Status.FAILURE, check_class=CheckClass.ADVISORY)
        if record.job == "pyright"
        else record
        for record in records
    ]

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is True
    assert decision.failures == ()
    assert any("pyright" in warning and "non-blocking" in warning for warning in decision.warnings)


def test_missing_advisory_evidence_is_a_warning() -> None:
    records = [record for record in successful_evidence() if record.job != "vulture"]

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is True
    assert any("vulture" in warning for warning in decision.warnings)


def test_advisory_evidence_for_another_commit_is_a_warning() -> None:
    records = [
        make_record("pyright", commit=OTHER_COMMIT, check_class=CheckClass.ADVISORY)
        if record.job == "pyright"
        else record
        for record in successful_evidence()
    ]

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is True
    assert any(OTHER_COMMIT in warning for warning in decision.warnings)


@pytest.mark.parametrize("status", [Status.FAILURE, Status.CANCELLED, Status.SKIPPED])
def test_required_job_not_succeeding_rejects(status: Status) -> None:
    records = [
        make_record("coverage-gate", status=status) if record.job == "coverage-gate" else record
        for record in successful_evidence()
    ]

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is False
    assert f"required job 'coverage-gate' finished as {status.value}" in decision.failures


def test_missing_required_evidence_rejects() -> None:
    records = [record for record in successful_evidence() if record.job != "smoke-test"]

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is False
    assert "required job 'smoke-test' produced no evidence (missing)" in decision.failures


def test_required_job_recorded_as_advisory_rejects() -> None:
    records = [
        make_record("quality-gate", check_class=CheckClass.ADVISORY)
        if record.job == "quality-gate"
        else record
        for record in successful_evidence()
    ]

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is False
    assert any("expected blocking" in failure for failure in decision.failures)


def test_evidence_for_another_commit_rejects() -> None:
    records = [
        make_record("tests-unit", commit=OTHER_COMMIT) if record.job == "tests-unit" else record
        for record in successful_evidence()
    ]

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is False
    assert any(OTHER_COMMIT in failure and "tests-unit" in failure for failure in decision.failures)


def test_duplicate_evidence_rejects() -> None:
    records = successful_evidence()
    records.append(make_record("quality-gate", status=Status.FAILURE))

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is False
    assert "duplicate evidence for job 'quality-gate'" in failure_text(decision.failures)


def test_unrecognised_evidence_is_ignored_with_a_warning() -> None:
    records = successful_evidence()
    records.append(make_record("legacy-job"))

    decision = evaluate_acceptance(records, COMMIT)

    assert decision.accepted is True
    assert any("legacy-job" in warning for warning in decision.warnings)


@pytest.mark.parametrize("commit", ["", "abc123", "A" * 40, "z" * 40])
def test_invalid_expected_commit_rejects(commit: str) -> None:
    decision = evaluate_acceptance([], commit)

    assert decision.accepted is False
    assert any("full 40-character SHA" in failure for failure in decision.failures)


def test_no_evidence_at_all_rejects_every_required_job() -> None:
    decision = evaluate_acceptance([], COMMIT)

    assert decision.accepted is False
    assert len(decision.failures) == len(REQUIRED_JOBS)
    assert decision.observed == ()


@pytest.mark.parametrize("value", ["a" * 40, "0" * 40])
def test_full_commit_accepts_lowercase_hex(value: str) -> None:
    assert is_full_commit(value) is True
