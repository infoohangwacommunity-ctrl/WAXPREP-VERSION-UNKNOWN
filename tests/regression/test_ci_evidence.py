"""Evidence serialisation and required-report validation tests for Stage 10."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from waxprep.ci.acceptance import CheckClass, ExecutionPhase, Status
from waxprep.ci.evidence import (
    EvidenceError,
    build_record,
    load_evidence,
    parse_status,
    read_record,
    record_to_dict,
    validate_coverage_xml,
    validate_sbom_json,
    write_record,
)

pytestmark = pytest.mark.regression

COMMIT = "a" * 40


def coverage_xml(path: Path, *, rate: str | None = "1.0", root: str = "coverage") -> Path:
    attribute = "" if rate is None else f' line-rate="{rate}"'
    path.write_text(f'<?xml version="1.0" ?><{root}{attribute}></{root}>', encoding="utf-8")
    return path


def sbom_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job": "quality-gate",
        "check_class": "blocking",
        "status": "success",
        "commit": COMMIT,
        "workflow_run_id": "1-1",
        "recorded_at": "2026-11-25T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def write_payload(path: Path, payload: dict[str, Any]) -> Path:
    return sbom_json(path, payload)


def test_parse_status_normalises_known_outcomes() -> None:
    assert parse_status("success") is Status.SUCCESS
    assert parse_status("skipped") is Status.SKIPPED


def test_parse_status_rejects_unknown_outcomes() -> None:
    with pytest.raises(EvidenceError, match="unrecognised job status"):
        parse_status("neutral")


def test_build_record_uses_current_time_and_keeps_exit_code() -> None:
    record = build_record(
        job="quality-gate",
        check_class="blocking",
        status="success",
        commit=COMMIT,
        workflow_run_id="99-1",
        exit_code=0,
    )

    assert record.check_class is CheckClass.BLOCKING
    assert record.status is Status.SUCCESS
    assert record.exit_code == 0
    assert record.phase is ExecutionPhase.CHECK
    assert record.recorded_at


def test_build_record_accepts_an_explicit_timestamp() -> None:
    moment = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)

    record = build_record(
        job="pyright",
        check_class="advisory",
        status="failure",
        commit=COMMIT,
        workflow_run_id="99-2",
        phase="setup",
        recorded_at=moment,
    )

    assert record.recorded_at == "2026-11-25T12:00:00+00:00"
    assert record.exit_code is None
    assert record.phase is ExecutionPhase.SETUP


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"job": ""}, "job id must not be empty"),
        ({"job": "Quality Gate"}, "unusable job id"),
        ({"job": "../escape"}, "unusable job id"),
        ({"commit": ""}, "commit must not be empty"),
        ({"check_class": "optional"}, "unrecognised check class"),
        ({"status": "neutral"}, "unrecognised job status"),
        ({"phase": "deploy"}, "unrecognised execution phase"),
        ({"workflow_run_id": "run-1"}, "unusable workflow_run_id"),
        ({"workflow_run_id": "0-1"}, "unusable workflow_run_id"),
        ({"workflow_run_id": ""}, "unusable workflow_run_id"),
        ({"exit_code": 2}, "status 'success' with exit code 2"),
        ({"status": "failure", "exit_code": 0}, "status 'failure' with exit code 0"),
    ],
)
def test_build_record_rejects_invalid_input(kwargs: dict[str, Any], message: str) -> None:
    arguments: dict[str, Any] = {
        "job": "quality-gate",
        "check_class": "blocking",
        "status": "success",
        "commit": COMMIT,
        "workflow_run_id": "1-1",
    }
    arguments.update(kwargs)

    with pytest.raises(EvidenceError, match=message):
        build_record(**arguments)


def test_write_and_read_record_round_trip(tmp_path: Path) -> None:
    record = build_record(
        job="coverage-gate",
        check_class="blocking",
        status="failure",
        commit=COMMIT,
        workflow_run_id="7-1",
        exit_code=1,
    )

    path = write_record(tmp_path / "evidence", record)
    restored = read_record(path)

    assert restored == record
    assert record_to_dict(record)["status"] == "failure"
    assert record_to_dict(record)["exit_code"] == 1
    assert record_to_dict(record)["phase"] == "check"


def test_load_evidence_returns_records_in_name_order(tmp_path: Path) -> None:
    for job in ("vulture", "coverage-gate"):
        write_record(
            tmp_path,
            build_record(
                job=job,
                check_class="advisory" if job == "vulture" else "blocking",
                status="success",
                commit=COMMIT,
                workflow_run_id="1-1",
            ),
        )

    loaded = load_evidence(tmp_path)

    assert [record.job for record in loaded] == ["coverage-gate", "vulture"]


def test_load_evidence_of_absent_directory_is_empty(tmp_path: Path) -> None:
    assert load_evidence(tmp_path / "missing") == ()


def test_read_record_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(EvidenceError, match="cannot read evidence"):
        read_record(tmp_path / "absent.json")


def test_read_record_rejects_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(EvidenceError, match="not valid JSON"):
        read_record(path)


def test_read_record_rejects_non_object_payload(tmp_path: Path) -> None:
    path = sbom_json(tmp_path / "list.json", [])

    with pytest.raises(EvidenceError, match="must be a JSON object"):
        read_record(path)


def test_read_record_rejects_missing_field(tmp_path: Path) -> None:
    path = sbom_json(tmp_path / "partial.json", {"job": "quality-gate"})

    with pytest.raises(EvidenceError, match="no usable 'status' string"):
        read_record(path)


def test_read_record_rejects_unknown_check_class(tmp_path: Path) -> None:
    path = write_payload(tmp_path / "class.json", valid_payload(check_class="optional"))

    with pytest.raises(EvidenceError, match="unknown check_class"):
        read_record(path)


@pytest.mark.parametrize("value", [True, "0", 1.5])
def test_read_record_rejects_non_integer_exit_code(tmp_path: Path, value: object) -> None:
    path = write_payload(tmp_path / "exit.json", valid_payload(exit_code=value))

    with pytest.raises(EvidenceError, match="non-integer exit_code"):
        read_record(path)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"job": "Bad Job"}, "unusable job id"),
        ({"workflow_run_id": "workflow-7"}, "unusable workflow_run_id"),
        ({"recorded_at": "yesterday"}, "not an ISO 8601 timestamp"),
        ({"recorded_at": "2026-11-25T00:00:00"}, "without a timezone"),
        ({"recorded_at": "2026-11-25"}, "without a timezone"),
        ({"exit_code": 4}, "status 'success' with exit code 4"),
        ({"status": "failure", "exit_code": 0}, "status 'failure' with exit code 0"),
        ({"phase": "deploy"}, "unknown phase"),
        ({"phase": 7}, "non-string phase"),
    ],
)
def test_read_record_rejects_inconsistent_payloads(
    tmp_path: Path, overrides: dict[str, Any], message: str
) -> None:
    payload = valid_payload(**overrides)
    file_name = "quality-gate.json" if payload.get("job") == "quality-gate" else "record.json"
    if not isinstance(payload.get("job"), str) or payload["job"] != "quality-gate":
        file_name = "record.json"
    path = write_payload(tmp_path / file_name, payload)

    with pytest.raises(EvidenceError, match=message):
        read_record(path)


def test_read_record_rejects_a_job_that_does_not_match_its_file_name(tmp_path: Path) -> None:
    path = write_payload(tmp_path / "smoke-test.json", valid_payload(job="quality-gate"))

    with pytest.raises(EvidenceError, match="does not match its file name"):
        read_record(path)


def test_read_record_accepts_a_setup_phase_advisory_record(tmp_path: Path) -> None:
    path = write_payload(
        tmp_path / "pyright.json",
        valid_payload(
            job="pyright",
            check_class="advisory",
            status="failure",
            exit_code=1,
            phase="setup",
        ),
    )

    record = read_record(path)

    assert record.phase is ExecutionPhase.SETUP
    assert record.status is Status.FAILURE


def test_valid_coverage_report_passes(tmp_path: Path) -> None:
    validate_coverage_xml(coverage_xml(tmp_path / "coverage.xml"))


def test_missing_coverage_report_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(EvidenceError, match="is missing"):
        validate_coverage_xml(tmp_path / "absent.xml")


def test_malformed_coverage_report_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "coverage.xml"
    path.write_text("<coverage", encoding="utf-8")

    with pytest.raises(EvidenceError, match="not valid XML"):
        validate_coverage_xml(path)


def test_coverage_report_with_wrong_root_is_rejected(tmp_path: Path) -> None:
    path = coverage_xml(tmp_path / "coverage.xml", root="report")

    with pytest.raises(EvidenceError, match="expected 'coverage'"):
        validate_coverage_xml(path)


def test_coverage_report_without_rate_is_rejected(tmp_path: Path) -> None:
    path = coverage_xml(tmp_path / "coverage.xml", rate=None)

    with pytest.raises(EvidenceError, match="no line-rate attribute"):
        validate_coverage_xml(path)


def test_coverage_report_with_unparseable_rate_is_rejected(tmp_path: Path) -> None:
    path = coverage_xml(tmp_path / "coverage.xml", rate="high")

    with pytest.raises(EvidenceError, match="non-numeric line-rate"):
        validate_coverage_xml(path)


def test_coverage_below_threshold_is_rejected(tmp_path: Path) -> None:
    path = coverage_xml(tmp_path / "coverage.xml", rate="0.9949")

    with pytest.raises(EvidenceError, match="below the required"):
        validate_coverage_xml(path)


def valid_sbom() -> dict[str, object]:
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "components": [{"name": "fastapi", "purl": "pkg:pypi/fastapi@1.0.0"}],
    }


def test_valid_sbom_passes(tmp_path: Path) -> None:
    validate_sbom_json(sbom_json(tmp_path / "sbom.json", valid_sbom()))


def test_missing_sbom_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(EvidenceError, match="is missing"):
        validate_sbom_json(tmp_path / "absent.json")


def test_sbom_with_invalid_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "sbom.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(EvidenceError, match="not valid JSON"):
        validate_sbom_json(path)


def test_sbom_non_object_payload_is_rejected(tmp_path: Path) -> None:
    path = sbom_json(tmp_path / "sbom.json", ["components"])

    with pytest.raises(EvidenceError, match="must be a JSON object"):
        validate_sbom_json(path)


def test_sbom_with_wrong_format_is_rejected(tmp_path: Path) -> None:
    payload = valid_sbom()
    payload["bomFormat"] = "SPDX"
    path = sbom_json(tmp_path / "sbom.json", payload)

    with pytest.raises(EvidenceError, match="bomFormat"):
        validate_sbom_json(path)


def test_sbom_without_components_is_rejected(tmp_path: Path) -> None:
    payload = valid_sbom()
    payload["components"] = []
    path = sbom_json(tmp_path / "sbom.json", payload)

    with pytest.raises(EvidenceError, match="contains no components"):
        validate_sbom_json(path)


def test_sbom_with_non_list_components_is_rejected(tmp_path: Path) -> None:
    payload = valid_sbom()
    payload["components"] = "fastapi"
    path = sbom_json(tmp_path / "sbom.json", payload)

    with pytest.raises(EvidenceError, match="contains no components"):
        validate_sbom_json(path)


@pytest.mark.parametrize("component", [{"name": "fastapi"}, "fastapi"])
def test_sbom_component_without_purl_is_rejected(tmp_path: Path, component: object) -> None:
    payload = valid_sbom()
    payload["components"] = [component]
    path = sbom_json(tmp_path / "sbom.json", payload)

    with pytest.raises(EvidenceError, match="without a purl identifier"):
        validate_sbom_json(path)
