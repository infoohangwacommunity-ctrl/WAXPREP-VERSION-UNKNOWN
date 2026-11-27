"""
Retry Policy - Stage 15

A single, bounded, cancellation-aware retry policy.

Design rules enforced here:
- Only errors marked ``RETRYABLE`` are ever retried. Invalid input, invalid
  credentials, permission denial, and programming defects are never retried.
- Every retry has a hard attempt ceiling AND a total deadline. There is no
  unbounded loop.
- Backoff is exponential with jitter, so parallel callers do not synchronise.
- Cancellation always propagates; it is never swallowed or retried.

There is deliberately no ``@retry`` decorator. Retries are a decision about
operation semantics (is this safe to repeat?), so each call site opts in
explicitly instead of every function inheriting the behaviour.
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from waxprep.errors.taxonomy import DependencyTimeoutError, Retryability, WaxPrepError

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_BASE_DELAY = 0.1
DEFAULT_MAX_DELAY = 2.0
DEFAULT_TOTAL_BUDGET = 10.0


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded retry configuration.

    Args:
        max_attempts: Total attempts including the first call. Must be >= 1.
        base_delay: Delay before the first retry, in seconds.
        max_delay: Cap for a single backoff sleep, in seconds.
        total_budget: Wall-clock ceiling for the whole operation, in seconds.
        jitter: Fraction of each delay randomised, in [0, 1].
    """

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    base_delay: float = DEFAULT_BASE_DELAY
    max_delay: float = DEFAULT_MAX_DELAY
    total_budget: float = DEFAULT_TOTAL_BUDGET
    jitter: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0 or self.max_delay < 0:
            raise ValueError("delays must not be negative")
        if self.total_budget <= 0:
            raise ValueError("total_budget must be positive")
        if not 0.0 <= self.jitter <= 1.0:
            raise ValueError("jitter must be between 0 and 1")

    def should_retry(self, error: BaseException, attempt: int) -> bool:
        """Return True when ``error`` may be retried after ``attempt`` tries.

        ``attempt`` is the 1-based count of attempts already made.
        """
        if attempt >= self.max_attempts:
            return False
        if not isinstance(error, WaxPrepError):
            return False
        return error.retryability is Retryability.TRANSIENT

    def delay_for(self, attempt: int, *, rng: random.Random | None = None) -> float:
        """Return the backoff delay in seconds before retry number ``attempt``.

        ``attempt`` is 1-based: the delay after the first failure uses
        ``attempt=1``.
        """
        exponent = max(attempt - 1, 0)
        raw: float = min(self.base_delay * (2**exponent), self.max_delay)
        if self.jitter == 0.0:
            return raw
        source = rng or random
        spread: float = raw * self.jitter
        jittered: float = raw - spread + (source.random() * spread * 2)
        return max(0.0, jittered)


async def run_with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], Awaitable[None]] | None = None,
    clock: Callable[[], float] | None = None,
    rng: random.Random | None = None,
) -> T:
    """Run ``operation`` under ``policy``, retrying only transient failures.

    The final failure is re-raised unchanged so the owning boundary decides how
    to report it. Cancellation is never retried.

    ``sleep``, ``clock`` and ``rng`` are injectable so tests are deterministic
    and never actually wait.
    """
    active = policy or RetryPolicy()
    do_sleep = sleep or asyncio.sleep
    now = clock or asyncio.get_running_loop().time

    deadline = now() + active.total_budget
    attempt = 0
    last_error: BaseException | None = None
    while True:
        # The budget covers the operation itself and every retry delay. A
        # remaining time of zero means the deadline has passed: surface the
        # real failure rather than starting another attempt.
        remaining = deadline - now()
        if remaining <= 0.0:
            assert last_error is not None  # only reached after a failed attempt
            raise last_error

        attempt += 1
        try:
            return await asyncio.wait_for(operation(), timeout=remaining)
        except TimeoutError as error:
            # The operation itself outlived the wall-clock budget. Waiting for
            # it to return, however long it hangs, would violate the contract.
            raise DependencyTimeoutError() from error
        except Exception as error:
            last_error = error
            if not active.should_retry(error, attempt):
                raise
            delay = active.delay_for(attempt, rng=rng)
            if delay >= deadline - now():
                # Budget exhausted: surface the real failure, do not retry.
                raise
            await do_sleep(delay)
