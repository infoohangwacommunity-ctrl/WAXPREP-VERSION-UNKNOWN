"""Stage 10 acceptance engine.

The engine is deliberately pure: it receives the evidence that each workflow
job recorded and decides whether the exact commit under assessment is
accepted. It never runs a quality system itself, never reads the working tree
and never treats an absent result as a pass.

Acceptance rules (see ``docs/CI_ACCEPTANCE_POLICY.md``):

* every required job must have evidence, recorded as blocking;
* every required job must have finished ``success`` — ``failure``,
  ``cancelled``, ``skipped`` and anything unrecognised reject the commit;
* every record must name the exact commit being assessed;
* duplicate evidence never resolves to a pass;
* advisory jobs are reported by execution state — passed, failed, never
  executed, infrastructure failure, cancelled, missing — and never block.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

COMMIT_LENGTH = 40
HEX_DIGITS = frozenset("0123456789abcdef")

#: Test categories that run as independent matrix jobs. The workflow matrix
#: and this tuple are reconciled by the workflow audit.
TEST_CATEGORIES: tuple[str, ...] = (
    "unit",
    "integration",
    "contract",
    "lifecycle",
    "architecture",
    "configuration",
    "regression",
)

#: Jobs whose success is required before a commit may be accepted.
REQUIRED_JOBS: tuple[str, ...] = (
    "ci-audit",
    "quality-setup",
    "quality-gate",
    "coverage-gate",
    "smoke-test",
    "supply-chain-evidence",
    *(f"tests-{category}" for category in TEST_CATEGORIES),
)

#: Jobs that are reported but never block acceptance.
ADVISORY_JOBS: tuple[str, ...] = ("pyright", "vulture")


class Status(StrEnum):
    """Normalised job outcomes. Anything else is not a pass."""

    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"


class CheckClass(StrEnum):
    """Whether a job blocks acceptance or is advisory."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"


class ExecutionPhase(StrEnum):
    """Which stage of a job produced the recorded status.

    Advisory jobs run after environment preparation. Recording ``setup`` means
    the check itself never ran, which is an infrastructure failure and must not
    be reported as a failed or a passed check.
    """

    CHECK = "check"
    SETUP = "setup"


class AdvisoryState(StrEnum):
    """How an advisory job ended, as reported in the decision."""

    PASSED = "passed"
    FAILED = "failed"
    NOT_EXECUTED = "not-executed"
    INFRASTRUCTURE_FAILURE = "infrastructure-failure"
    CANCELLED = "cancelled"
    MISSING = "missing"
    STALE_EVIDENCE = "stale-evidence"


@dataclass(frozen=True)
class JobRecord:
    """One machine-readable job result recorded by the workflow."""

    job: str
    check_class: CheckClass
    status: Status
    commit: str
    workflow_run_id: str
    recorded_at: str
    exit_code: int | None = None
    phase: ExecutionPhase = ExecutionPhase.CHECK


@dataclass(frozen=True)
class AcceptanceDecision:
    """The acceptance decision and the reasons behind it."""

    accepted: bool
    commit: str
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    observed: tuple[tuple[str, str], ...]
    advisory: tuple[tuple[str, str], ...] = ()


def is_full_commit(value: str) -> bool:
    """Return True only for a lowercase 40-character hexadecimal SHA."""
    return len(value) == COMMIT_LENGTH and all(character in HEX_DIGITS for character in value)


def _index_records(records: Sequence[JobRecord], failures: list[str]) -> dict[str, JobRecord]:
    index: dict[str, JobRecord] = {}
    for record in records:
        if record.job in index:
            failures.append(
                f"duplicate evidence for job '{record.job}': two records cannot be "
                "resolved into one result"
            )
            continue
        index[record.job] = record
    return index


def _check_required(index: dict[str, JobRecord], expected_commit: str, failures: list[str]) -> None:
    for job in REQUIRED_JOBS:
        record = index.get(job)
        if record is None:
            failures.append(f"required job '{job}' produced no evidence (missing)")
            continue
        if record.check_class is not CheckClass.BLOCKING:
            failures.append(
                f"required job '{job}' is classified {record.check_class.value}, expected blocking"
            )
        if record.commit != expected_commit:
            failures.append(
                f"required job '{job}' recorded commit {record.commit!r}, "
                f"expected {expected_commit!r}"
            )
        if record.status is not Status.SUCCESS:
            failures.append(f"required job '{job}' finished as {record.status.value}")


def _advisory_state(record: JobRecord | None, expected_commit: str) -> AdvisoryState:
    """Classify an advisory job's recorded execution."""
    if record is None:
        return AdvisoryState.MISSING
    if record.commit != expected_commit:
        return AdvisoryState.STALE_EVIDENCE
    if record.phase is ExecutionPhase.SETUP:
        return AdvisoryState.INFRASTRUCTURE_FAILURE
    if record.status is Status.SUCCESS:
        return AdvisoryState.PASSED
    if record.status is Status.CANCELLED:
        return AdvisoryState.CANCELLED
    if record.status is Status.SKIPPED:
        return AdvisoryState.NOT_EXECUTED
    return AdvisoryState.FAILED


def _advisory_warning(
    job: str, record: JobRecord | None, state: AdvisoryState, expected_commit: str
) -> str | None:
    """Render the warning for one advisory state (``None`` when it passed)."""
    if state is AdvisoryState.PASSED:
        return None
    if state is AdvisoryState.MISSING:
        return f"advisory job '{job}' produced no evidence: its check never executed (non-blocking)"
    if state is AdvisoryState.STALE_EVIDENCE:
        recorded = record.commit if record is not None else ""
        return (
            f"advisory job '{job}' recorded commit {recorded!r}, "
            f"expected {expected_commit!r} (non-blocking)"
        )
    if state is AdvisoryState.INFRASTRUCTURE_FAILURE:
        finished = record.status.value if record is not None else "unknown"
        return (
            f"advisory job '{job}' finished as {finished} before its check ran: "
            "infrastructure failure, not a check result (non-blocking)"
        )
    if state is AdvisoryState.CANCELLED:
        return f"advisory job '{job}' was cancelled before its check completed (non-blocking)"
    if state is AdvisoryState.NOT_EXECUTED:
        return f"advisory job '{job}' was skipped, so its check never executed (non-blocking)"
    detail = record.status.value if record is not None else "unknown"
    if record is not None and record.exit_code is not None:
        detail = f"{detail}, exit code {record.exit_code}"
    return f"advisory job '{job}' executed and failed ({detail}, non-blocking)"


def _check_advisory(
    index: dict[str, JobRecord], expected_commit: str, warnings: list[str]
) -> tuple[tuple[str, str], ...]:
    reported: list[tuple[str, str]] = []
    for job in ADVISORY_JOBS:
        record = index.get(job)
        if record is not None and record.check_class is not CheckClass.ADVISORY:
            warnings.append(
                f"advisory job '{job}' is recorded as {record.check_class.value}; "
                "its classification is ignored (non-blocking)"
            )
        state = _advisory_state(record, expected_commit)
        reported.append((job, state.value))
        warning = _advisory_warning(job, record, state, expected_commit)
        if warning is not None:
            warnings.append(warning)
    return tuple(reported)


def _check_extras(index: dict[str, JobRecord], warnings: list[str]) -> None:
    for job in index:
        if job not in REQUIRED_JOBS and job not in ADVISORY_JOBS:
            warnings.append(f"unrecognised evidence for job '{job}' was ignored")


def evaluate_acceptance(records: Sequence[JobRecord], expected_commit: str) -> AcceptanceDecision:
    """Decide acceptance from recorded job evidence for one exact commit.

    A required job that is absent, skipped, cancelled, failed, misclassified or
    bound to another commit rejects the assessment. Advisory outcomes are
    reported by execution state and never reject.
    """
    failures: list[str] = []
    warnings: list[str] = []

    if not is_full_commit(expected_commit):
        failures.append(
            f"expected commit {expected_commit!r} is not a full 40-character SHA; "
            "evidence cannot be bound to a commit"
        )

    index = _index_records(records, failures)
    _check_required(index, expected_commit, failures)
    advisory = _check_advisory(index, expected_commit, warnings)
    _check_extras(index, warnings)

    observed = tuple((job, index[job].status.value) for job in sorted(index))
    return AcceptanceDecision(
        accepted=not failures,
        commit=expected_commit,
        failures=tuple(failures),
        warnings=tuple(warnings),
        observed=observed,
        advisory=advisory,
    )
