"""Stage 15 — error taxonomy, retry policy, and HTTP boundary tests."""

import pytest

from waxprep.errors import (
    CancellationError,
    ConfigurationError,
    DependencyTimeoutError,
    DependencyUnavailableError,
    ErrorCategory,
    InternalInvariantError,
    NotFoundError,
    ProgrammingDefectError,
    ProviderRejectedError,
    RateLimitedError,
    RetryPolicy,
    ValidationError,
    WaxPrepError,
    run_with_retry,
)
from waxprep.errors.http import public_body, should_expose_message, status_for

pytestmark = pytest.mark.unit


class TestTaxonomy:
    def test_every_error_has_stable_code_and_bounded_category(self):
        errors = [
            ValidationError(),
            ConfigurationError(),
            NotFoundError(),
            DependencyUnavailableError(),
            DependencyTimeoutError(),
            RateLimitedError(),
            ProviderRejectedError(),
            InternalInvariantError(),
            ProgrammingDefectError(),
            CancellationError(),
        ]
        codes = [e.code for e in errors]
        assert len(codes) == len(set(codes)), "codes must be unique and stable"
        for error in errors:
            assert isinstance(error.category, ErrorCategory)

    def test_default_message_is_safe_and_used_when_none_given(self):
        assert NotFoundError().safe_message == NotFoundError.default_message

    def test_custom_safe_message_is_kept(self):
        assert NotFoundError("Student not found").safe_message == "Student not found"

    def test_to_fields_never_includes_message_or_context(self):
        error = NotFoundError("secret path /etc/passwd", context={"token": "abc"})
        fields = error.to_fields()
        joined = str(fields)
        assert "passwd" not in joined
        assert "abc" not in joined
        assert fields["error.code"] == "WAX-1005"
        assert fields["error.category"] == "not_found"

    @pytest.mark.parametrize(
        "error",
        [DependencyUnavailableError(), DependencyTimeoutError(), RateLimitedError()],
    )
    def test_transient_errors_are_retryable(self, error):
        assert error.is_retryable is True
        assert error.to_fields()["error.retryable"] == "true"

    @pytest.mark.parametrize(
        "error",
        [ValidationError(), NotFoundError(), ProgrammingDefectError()],
    )
    def test_permanent_errors_are_not_retryable(self, error):
        assert error.is_retryable is False

    def test_is_an_exception_with_chained_cause_support(self):
        with pytest.raises(WaxPrepError):
            try:
                raise ValueError("provider blew up")
            except ValueError as cause:
                raise NotFoundError("wrapped") from cause


class TestHttpBoundary:
    @pytest.mark.parametrize(
        ("error", "expected"),
        [
            (ValidationError(), 422),
            (NotFoundError(), 404),
            (RateLimitedError(), 429),
            (DependencyUnavailableError(), 503),
            (DependencyTimeoutError(), 504),
            (ProgrammingDefectError(), 500),
        ],
    )
    def test_category_maps_to_http_status(self, error, expected):
        assert status_for(error.category) == expected

    def test_server_errors_stay_generic(self):
        body = public_body(ProgrammingDefectError("leaked internal path"))
        assert body == {
            "detail": "Internal server error",
            "message": "An unexpected error occurred",
        }
        assert "leaked" not in str(body)

    def test_client_errors_may_expose_safe_message(self):
        assert public_body(NotFoundError("Student not found")) == {"detail": "Student not found"}

    def test_should_expose_message_classification(self):
        assert should_expose_message(ErrorCategory.NOT_FOUND) is True
        assert should_expose_message(ErrorCategory.PROGRAMMING_DEFECT) is False


class TestRetryPolicy:
    def test_rejects_impossible_configuration(self):
        with pytest.raises(ValueError):
            RetryPolicy(max_attempts=0)
        with pytest.raises(ValueError):
            RetryPolicy(base_delay=-1)
        with pytest.raises(ValueError):
            RetryPolicy(total_budget=0)
        with pytest.raises(ValueError):
            RetryPolicy(jitter=2)

    def test_never_retries_permanent_failures(self):
        policy = RetryPolicy()
        assert policy.should_retry(ValidationError(), 1) is False
        assert policy.should_retry(ValueError("plain"), 1) is False

    def test_stops_at_attempt_ceiling(self):
        policy = RetryPolicy(max_attempts=2)
        assert policy.should_retry(RateLimitedError(), 1) is True
        assert policy.should_retry(RateLimitedError(), 2) is False

    def test_backoff_grows_then_caps(self):
        policy = RetryPolicy(base_delay=0.1, max_delay=0.4, jitter=0.0)
        assert policy.delay_for(1) == pytest.approx(0.1)
        assert policy.delay_for(2) == pytest.approx(0.2)
        assert policy.delay_for(9) == pytest.approx(0.4)

    def test_jitter_stays_within_bounds(self):
        import random as rng_module

        policy = RetryPolicy(base_delay=1.0, jitter=0.5)
        rng = rng_module.Random(1234)
        for _ in range(20):
            delay = policy.delay_for(1, rng=rng)
            assert 0.5 <= delay <= 1.5


@pytest.mark.asyncio
class TestRunWithRetry:
    async def test_returns_first_success_without_sleeping(self):
        calls = []

        async def operation():  # noqa: RUF029
            calls.append(1)
            return "ok"

        async def no_sleep(_seconds):  # noqa: RUF029
            raise AssertionError("must not sleep on success")

        assert await run_with_retry(operation, sleep=no_sleep) == "ok"
        assert len(calls) == 1

    async def test_retries_transient_failure_then_succeeds(self):
        attempts = []

        async def operation():  # noqa: RUF029
            attempts.append(1)
            if len(attempts) < 2:
                raise DependencyTimeoutError()
            return "recovered"

        slept = []

        async def record_sleep(seconds):  # noqa: RUF029
            slept.append(seconds)

        result = await run_with_retry(
            operation, policy=RetryPolicy(base_delay=0.1, jitter=0.0), sleep=record_sleep
        )
        assert result == "recovered"
        assert len(attempts) == 2
        assert slept == [pytest.approx(0.1)]

    async def test_does_not_retry_permanent_failure(self):
        async def operation():  # noqa: RUF029
            raise ValidationError("bad input")

        async def no_sleep(_seconds):  # noqa: RUF029
            raise AssertionError("must not sleep for a permanent failure")

        with pytest.raises(ValidationError):
            await run_with_retry(operation, sleep=no_sleep)

    async def test_reraises_once_attempts_exhausted(self):
        async def operation():  # noqa: RUF029
            raise RateLimitedError()

        slept = []

        async def record_sleep(seconds):  # noqa: RUF029
            slept.append(seconds)

        with pytest.raises(RateLimitedError):
            await run_with_retry(
                operation,
                policy=RetryPolicy(max_attempts=2, base_delay=0.01, jitter=0.0),
                sleep=record_sleep,
            )
        assert len(slept) == 1

    async def test_deadline_stops_retrying(self):
        """A retry that would cross the total budget must not be attempted."""

        async def operation():  # noqa: RUF029
            raise RateLimitedError()

        clock_values = iter([0.0, 9.9])

        async def no_sleep(_seconds):  # noqa: RUF029
            raise AssertionError("must not sleep past the deadline")

        with pytest.raises(RateLimitedError):
            await run_with_retry(
                operation,
                policy=RetryPolicy(max_attempts=5, base_delay=1.0, total_budget=10.0),
                sleep=no_sleep,
                clock=lambda: next(clock_values, 99.0),
            )

    async def test_cancellation_is_not_retried(self):
        async def operation():  # noqa: RUF029
            raise CancellationError()

        async def no_sleep(_seconds):  # noqa: RUF029
            raise AssertionError("cancellation must not be retried")

        with pytest.raises(CancellationError):
            await run_with_retry(operation, sleep=no_sleep)

    async def test_operation_that_outlives_the_budget_is_stopped(self):
        """The deadline must cover the operation, not only the sleep between tries."""
        import asyncio
        import time

        async def hangs():
            await asyncio.sleep(30)

        started = time.monotonic()
        with pytest.raises(DependencyTimeoutError):
            await run_with_retry(
                hangs,
                policy=RetryPolicy(max_attempts=3, total_budget=0.05, base_delay=0.0),
            )
        assert time.monotonic() - started < 2.0

    async def test_overshooting_sleep_surfaces_the_original_failure(self):
        """If a delay overruns the deadline, the real failure is re-raised."""

        async def operation():  # noqa: RUF029
            raise RateLimitedError()

        clock_values = iter([0.0, 0.0, 0.0, 100.0])

        async def overrunning_sleep(_seconds):  # noqa: RUF029
            return None

        with pytest.raises(RateLimitedError):
            await run_with_retry(
                operation,
                policy=RetryPolicy(max_attempts=5, base_delay=1.0, total_budget=10.0),
                sleep=overrunning_sleep,
                clock=lambda: next(clock_values, 100.0),
            )

    async def test_external_cancellation_propagates(self):
        """Cancelling the caller must stop the attempt, not be retried or wrapped."""
        import asyncio

        started = asyncio.Event()

        async def operation():
            started.set()
            await asyncio.sleep(30)

        task = asyncio.create_task(run_with_retry(operation, policy=RetryPolicy(total_budget=10.0)))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
