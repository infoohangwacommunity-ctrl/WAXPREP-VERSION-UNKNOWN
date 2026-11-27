"""Stage 16 — application lifecycle, resource ownership and failure tests.

These tests use the real manager, real asyncio, real AsyncExitStack and the
real ASGI lifespan. Failure injection is done with ordinary callables, not by
mocking the code under test.
"""

from __future__ import annotations

import asyncio
from itertools import product

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from waxprep.lifecycle import (
    ApplicationLifecycle,
    BackgroundTaskSupervisor,
    CleanupStatus,
    ComponentResult,
    LifecycleComponent,
    LifecycleError,
    LifecycleReport,
    LifecycleState,
    LifecycleStateMachine,
    LifecycleTimeouts,
    LifecycleTransitionError,
    OperationOutcome,
    ResourceOwnershipError,
    TaskOutcome,
    TaskResult,
    TaskSupervisorError,
)
from waxprep.lifecycle.states import ALLOWED_TRANSITIONS

pytestmark = pytest.mark.lifecycle


class ComponentError(RuntimeError):
    pass


class ReleaseError(RuntimeError):
    pass


class Recorder:
    """Collects init/release order and can fail or delay chosen components."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.release_counts: dict[str, int] = {}
        self.acquire_counts: dict[str, int] = {}
        self.fail_on: set[str] = set()
        self.release_fail_on: set[str] = set()
        self.init_delay: dict[str, float] = {}
        self.release_delay: dict[str, float] = {}
        self.release_enter: dict[str, asyncio.Event] = {}
        self.block_release: set[str] = set()

    def component(
        self,
        name: str,
        *,
        mandatory: bool = True,
        depends_on: tuple[str, ...] = (),
    ) -> LifecycleComponent:
        async def initialize() -> None:
            self.events.append(f"init:{name}")
            self.acquire_counts[name] = self.acquire_counts.get(name, 0) + 1
            if name in self.init_delay:
                await asyncio.sleep(self.init_delay[name])
            if name in self.fail_on:
                raise ComponentError(name)

        async def release() -> None:
            self.events.append(f"release:{name}")
            self.release_counts[name] = self.release_counts.get(name, 0) + 1
            event = self.release_enter.get(name)
            if event is not None:
                event.set()
            if name in self.block_release:
                await asyncio.Event().wait()
            if name in self.release_delay:
                await asyncio.sleep(self.release_delay[name])
            if name in self.release_fail_on:
                raise ReleaseError(name)

        return LifecycleComponent(
            name=name,
            initialize=initialize,
            release=release,
            mandatory=mandatory,
            depends_on=depends_on,
        )


def run(coro):
    return asyncio.run(coro)


# ── State machine ───────────────────────────────────────────────────────────


class TestStateMachine:
    def test_transition_contract_is_exact(self):
        for source, target in product(LifecycleState, repeat=2):
            machine = LifecycleStateMachine(source)
            if target in ALLOWED_TRANSITIONS[source]:
                assert machine.can_transition_to(target) is True
                assert machine.transition_to(target) is target
                assert machine.state is target
            else:
                assert machine.can_transition_to(target) is False
                with pytest.raises(LifecycleTransitionError):
                    machine.transition_to(target)
                assert machine.state is source

    def test_default_initial_state_is_new(self):
        assert LifecycleStateMachine().state is LifecycleState.NEW


# ── Timeouts ────────────────────────────────────────────────────────────────


class TestTimeouts:
    def test_defaults_are_positive(self):
        timeouts = LifecycleTimeouts()
        assert timeouts.startup_seconds > 0
        assert timeouts.component_seconds > 0
        assert timeouts.background_stop_seconds > 0
        assert timeouts.observability_seconds > 0

    @pytest.mark.parametrize(
        "field",
        [
            "startup_seconds",
            "component_seconds",
            "background_stop_seconds",
            "observability_seconds",
        ],
    )
    @pytest.mark.parametrize("value", [0.0, -1.0, float("inf"), float("nan")])
    def test_invalid_timeouts_are_rejected(self, field, value):
        with pytest.raises(ValueError, match=field):
            LifecycleTimeouts(**{field: value})


# ── Components ──────────────────────────────────────────────────────────────


class TestComponents:
    def test_component_is_declarative(self):
        component = LifecycleComponent(name="db", depends_on=("config",))
        assert component.name == "db"
        assert component.mandatory is True

    @pytest.mark.parametrize("name", ["", "   "])
    def test_component_name_must_be_non_empty(self, name):
        with pytest.raises(ValueError, match="non-empty"):
            LifecycleComponent(name=name)

    def test_duplicate_dependencies_rejected(self):
        with pytest.raises(ValueError, match="duplicate"):
            LifecycleComponent(name="db", depends_on=("config", "config"))

    def test_self_dependency_rejected(self):
        with pytest.raises(ValueError, match="itself"):
            LifecycleComponent(name="db", depends_on=("db",))


# ── Report ──────────────────────────────────────────────────────────────────


class TestReport:
    @pytest.mark.parametrize(
        ("outcome", "succeeded", "failed"),
        [
            (OperationOutcome.COMPLETED, True, False),
            (OperationOutcome.FAILED, False, True),
            (OperationOutcome.TIMED_OUT, False, True),
            (OperationOutcome.CANCELLED, False, True),
        ],
    )
    def test_component_result_flags(self, outcome, succeeded, failed):
        result = ComponentResult(name="x", outcome=outcome, duration_ms=1.0)
        assert result.succeeded is succeeded
        assert result.failed is failed

    def test_cleanup_status_success(self):
        report = LifecycleReport(
            cleanup=[
                ComponentResult("a", OperationOutcome.COMPLETED, 1.0),
                ComponentResult("b", OperationOutcome.COMPLETED, 1.0),
            ]
        )
        assert report.cleanup_status is CleanupStatus.SUCCESS
        assert report.cleanup_failures == ()

    def test_cleanup_status_empty_is_success(self):
        assert LifecycleReport().cleanup_status is CleanupStatus.SUCCESS

    def test_cleanup_status_partial(self):
        report = LifecycleReport(
            cleanup=[
                ComponentResult("a", OperationOutcome.COMPLETED, 1.0),
                ComponentResult("b", OperationOutcome.FAILED, 1.0),
            ]
        )
        assert report.cleanup_status is CleanupStatus.PARTIAL
        assert len(report.cleanup_failures) == 1

    def test_cleanup_status_failed(self):
        report = LifecycleReport(cleanup=[ComponentResult("a", OperationOutcome.FAILED, 1.0)])
        assert report.cleanup_status is CleanupStatus.FAILED

    def test_cleanup_status_interrupted_wins(self):
        report = LifecycleReport(
            cleanup=[ComponentResult("a", OperationOutcome.COMPLETED, 1.0)],
            cleanup_cancelled=True,
        )
        assert report.cleanup_status is CleanupStatus.INTERRUPTED

    @pytest.mark.parametrize(
        ("state", "error_type", "startup_succeeded", "successful"),
        [
            (LifecycleState.READY, None, True, False),
            (LifecycleState.STOPPED, None, True, True),
            (LifecycleState.STOPPED, "ValueError", False, False),
            (LifecycleState.FAILED, None, False, False),
        ],
    )
    def test_report_flags(self, state, error_type, startup_succeeded, successful):
        report = LifecycleReport(final_state=state, startup_error_type=error_type)
        assert report.startup_succeeded is startup_succeeded
        assert report.successful is successful


# ── Background supervisor ───────────────────────────────────────────────────


class TestBackgroundSupervisor:
    def test_task_result_failed_flag(self):
        assert TaskResult("x", TaskOutcome.FAILED).failed is True
        assert TaskResult("x", TaskOutcome.TIMED_OUT).failed is True
        assert TaskResult("x", TaskOutcome.COMPLETED).failed is False

    def test_task_completes_and_is_untracked(self):
        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            task = supervisor.start("work", asyncio.sleep(0, result="done"))
            assert await task == "done"
            await asyncio.sleep(0)
            assert supervisor.active_tasks == ()

        run(scenario())

    def test_duplicate_name_rejected(self):
        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            supervisor.start("work", asyncio.sleep(0))
            coro = asyncio.sleep(0)
            with pytest.raises(TaskSupervisorError, match="already running"):
                supervisor.start("work", coro)
            assert coro.cr_frame is None  # closed, not leaked
            await supervisor.stop(0.1)

        run(scenario())

    def test_empty_name_rejected(self):
        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            coro = asyncio.sleep(0)
            with pytest.raises(TaskSupervisorError, match="non-empty"):
                supervisor.start("", coro)
            assert coro.cr_frame is None
            await asyncio.sleep(0)

        run(scenario())

    def test_start_after_stop_rejected(self):
        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            assert await supervisor.stop(0.1) == ()
            coro = asyncio.sleep(0)
            with pytest.raises(TaskSupervisorError, match="stopping"):
                supervisor.start("late", coro)
            assert coro.cr_frame is None

        run(scenario())

    def test_cancellation_is_recorded_and_waited(self):
        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            supervisor.start("long", asyncio.sleep(30))
            results = await supervisor.stop(0.5)
            assert results == (TaskResult("long", TaskOutcome.CANCELLED),)
            assert supervisor.active_tasks == ()

        run(scenario())

    def test_failure_is_recorded_and_reported(self):
        reported: list[tuple[str, BaseException]] = []

        async def failing():
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                raise RuntimeError("worker died") from None

        async def scenario():
            supervisor = BackgroundTaskSupervisor(
                on_error=lambda name, error: reported.append((name, error))
            )
            supervisor.start("worker", failing())
            await asyncio.sleep(0)
            results = await supervisor.stop(0.5)
            assert results == (TaskResult("worker", TaskOutcome.FAILED, error_type="RuntimeError"),)

        run(scenario())
        assert len(reported) == 1
        assert reported[0][0] == "worker"
        assert isinstance(reported[0][1], RuntimeError)

    def test_error_reporter_failure_is_swallowed(self):
        async def boom():
            await asyncio.sleep(0)
            raise RuntimeError("boom")

        def explode(_name: str, _error: BaseException) -> None:
            raise RuntimeError("reporter broke")

        async def scenario():
            supervisor = BackgroundTaskSupervisor(on_error=explode)
            task = supervisor.start("boom", boom())
            with pytest.raises(RuntimeError, match="boom"):
                await task
            await asyncio.sleep(0)
            assert supervisor.active_tasks == ()

        run(scenario())

    def test_timeout_is_reported_and_leak_stays_visible(self):
        release = asyncio.Event()

        async def stubborn():
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                await release.wait()

        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            task = supervisor.start("stubborn", stubborn())
            await asyncio.sleep(0)
            results = await supervisor.stop(0.01)
            assert results == (TaskResult("stubborn", TaskOutcome.TIMED_OUT),)
            assert supervisor.active_tasks == ("stubborn",)
            release.set()
            await task
            await asyncio.sleep(0)
            assert supervisor.active_tasks == ()

        run(scenario())

    def test_cooperative_cancellation_can_complete_normally(self):
        async def finishes() -> None:
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                return

        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            supervisor.start("finishes", finishes())
            await asyncio.sleep(0)
            results = await supervisor.stop(0.5)
            assert results == (TaskResult("finishes", TaskOutcome.COMPLETED),)

        run(scenario())

    def test_stop_is_idempotent(self):
        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            supervisor.start("work", asyncio.sleep(30))
            first = await supervisor.stop(0.1)
            second = await supervisor.stop(0.1)
            assert first == second

        run(scenario())

    def test_reset_requires_no_active_tasks(self):
        async def scenario():
            supervisor = BackgroundTaskSupervisor()
            supervisor.start("work", asyncio.sleep(30))
            with pytest.raises(TaskSupervisorError, match="active tasks"):
                supervisor.reset()
            await supervisor.stop(0.1)
            supervisor.reset()
            assert supervisor.stopped is False
            supervisor.start("again", asyncio.sleep(0))
            await supervisor.stop(0.1)

        run(scenario())


# ── Manager: startup and cleanup ────────────────────────────────────────────


class TestLifecycleStartup:
    def test_success_reaches_ready_then_stopped(self):
        recorder = Recorder()
        lifecycle = ApplicationLifecycle()
        for name in ("a", "b", "c"):
            lifecycle.register(recorder.component(name))

        async def scenario():
            report = await lifecycle.start()
            assert lifecycle.is_ready is True
            assert report.final_state is LifecycleState.READY
            assert [result.name for result in report.startup] == ["a", "b", "c"]
            await lifecycle.shutdown()
            assert lifecycle.state is LifecycleState.STOPPED
            assert report.cleanup_status is CleanupStatus.SUCCESS
            assert report.successful is True

        run(scenario())
        assert recorder.events == [
            "init:a",
            "init:b",
            "init:c",
            "release:c",
            "release:b",
            "release:a",
        ]

    def test_optional_failure_degrades_without_aborting(self):
        recorder = Recorder()
        recorder.fail_on.add("optional")
        lifecycle = ApplicationLifecycle()
        lifecycle.register(recorder.component("required"))
        lifecycle.register(recorder.component("optional", mandatory=False))

        async def scenario():
            report = await lifecycle.start()
            assert lifecycle.state is LifecycleState.READY
            assert report.degraded == ("optional",)
            await lifecycle.shutdown()

        run(scenario())

    def test_optional_timeout_degrades_without_aborting(self):
        recorder = Recorder()
        recorder.init_delay["optional"] = 1.0
        lifecycle = ApplicationLifecycle(
            timeouts=LifecycleTimeouts(component_seconds=0.01, startup_seconds=1.0)
        )
        lifecycle.register(recorder.component("required"))
        lifecycle.register(recorder.component("optional", mandatory=False))

        async def scenario():
            report = await lifecycle.start()
            assert lifecycle.state is LifecycleState.READY
            assert report.degraded == ("optional",)
            await lifecycle.shutdown()

        run(scenario())

    @pytest.mark.parametrize("fail_at", [0, 1, 2])
    def test_rollback_at_every_boundary(self, fail_at):
        names = ("a", "b", "c")
        recorder = Recorder()
        recorder.fail_on.add(names[fail_at])
        lifecycle = ApplicationLifecycle()
        for name in names:
            lifecycle.register(recorder.component(name))

        async def scenario():
            with pytest.raises(ComponentError):
                await lifecycle.start()
            assert lifecycle.state is LifecycleState.FAILED
            assert lifecycle.report.startup_error_type == "ComponentError"
            assert lifecycle.report.cleanup_status is CleanupStatus.SUCCESS

        run(scenario())
        acquired = names[:fail_at]
        expected_release = [f"release:{name}" for name in reversed(acquired)]
        assert (
            recorder.events == [f"init:{name}" for name in names[: fail_at + 1]] + expected_release
        )

    def test_original_failure_survives_cleanup_failure(self):
        recorder = Recorder()
        recorder.fail_on.add("b")
        recorder.release_fail_on.add("a")
        lifecycle = ApplicationLifecycle()
        lifecycle.register(recorder.component("a"))
        lifecycle.register(recorder.component("b"))

        async def scenario():
            with pytest.raises(ComponentError, match="b"):
                await lifecycle.start()
            assert lifecycle.state is LifecycleState.FAILED
            assert lifecycle.report.cleanup_status is CleanupStatus.FAILED
            assert lifecycle.report.cleanup_failures[0].name == "a"

        run(scenario())

    def test_cleanup_failure_does_not_stop_other_releases(self):
        recorder = Recorder()
        recorder.release_fail_on.add("c")
        lifecycle = ApplicationLifecycle()
        for name in ("a", "b", "c"):
            lifecycle.register(recorder.component(name))

        async def scenario():
            await lifecycle.start()
            report = await lifecycle.shutdown()
            assert lifecycle.state is LifecycleState.FAILED
            assert report.cleanup_status is CleanupStatus.PARTIAL

        run(scenario())
        assert recorder.events[-3:] == ["release:c", "release:b", "release:a"]

    def test_component_timeout_rolls_back(self):
        recorder = Recorder()
        recorder.init_delay["slow"] = 1.0
        lifecycle = ApplicationLifecycle(
            timeouts=LifecycleTimeouts(component_seconds=0.01, startup_seconds=1.0)
        )
        lifecycle.register(recorder.component("fast"))
        lifecycle.register(recorder.component("slow"))

        async def scenario():
            with pytest.raises(TimeoutError):
                await lifecycle.start()
            assert lifecycle.state is LifecycleState.FAILED
            assert lifecycle.report.startup[-1].outcome is OperationOutcome.TIMED_OUT

        run(scenario())
        assert "release:fast" in recorder.events

    def test_component_raised_timeout_is_a_failure_not_a_deadline(self):
        async def raises_timeout():
            await asyncio.sleep(0)
            raise TimeoutError("component's own timeout")

        lifecycle = ApplicationLifecycle()
        lifecycle.register(LifecycleComponent(name="self-timeout", initialize=raises_timeout))

        async def scenario():
            with pytest.raises(TimeoutError):
                await lifecycle.start()
            assert lifecycle.report.startup[-1].outcome is OperationOutcome.FAILED

        run(scenario())

    def test_total_startup_timeout_is_reported(self):
        recorder = Recorder()
        recorder.init_delay["slow"] = 1.0
        lifecycle = ApplicationLifecycle(
            timeouts=LifecycleTimeouts(startup_seconds=0.01, component_seconds=1.0)
        )
        lifecycle.register(recorder.component("slow"))

        async def scenario():
            with pytest.raises(TimeoutError):
                await lifecycle.start()
            assert lifecycle.state is LifecycleState.FAILED

        run(scenario())

    def test_cleanup_timeout_is_isolated(self):
        recorder = Recorder()
        recorder.release_delay["slow"] = 1.0
        lifecycle = ApplicationLifecycle(timeouts=LifecycleTimeouts(component_seconds=0.01))
        lifecycle.register(recorder.component("slow"))

        async def scenario():
            await lifecycle.start()
            report = await lifecycle.shutdown()
            assert lifecycle.state is LifecycleState.FAILED
            assert report.cleanup[-1].outcome is OperationOutcome.TIMED_OUT

        run(scenario())

    def test_cleanup_raised_timeout_is_a_failure(self):
        async def release_timeout():
            await asyncio.sleep(0)
            raise TimeoutError("release's own timeout")

        lifecycle = ApplicationLifecycle()
        lifecycle.register(
            LifecycleComponent(name="x", initialize=lambda: None, release=release_timeout)
        )

        async def scenario():
            await lifecycle.start()
            report = await lifecycle.shutdown()
            assert report.cleanup[-1].outcome is OperationOutcome.FAILED

        run(scenario())

    def test_observability_cleanup_runs_last_and_is_isolated(self):
        recorder = Recorder()
        lifecycle = ApplicationLifecycle()
        lifecycle.register(recorder.component("resource"))
        seen: list[str] = []

        async def observability() -> None:
            await asyncio.sleep(0)
            seen.append("observability")
            recorder.events.append("observability")

        lifecycle.set_observability_cleanup(observability)

        async def scenario():
            await lifecycle.start()
            report = await lifecycle.shutdown()
            assert report.cleanup[-1].name == "observability"

        run(scenario())
        assert seen == ["observability"]
        assert recorder.events[-2:] == ["release:resource", "observability"]

    def test_observability_cleanup_failure_marks_failed(self):
        lifecycle = ApplicationLifecycle()

        async def broken() -> None:
            await asyncio.sleep(0)
            raise RuntimeError("flush failed")

        lifecycle.set_observability_cleanup(broken)

        async def scenario():
            await lifecycle.start()
            report = await lifecycle.shutdown()
            assert lifecycle.state is LifecycleState.FAILED
            assert report.cleanup_failures[0].name == "observability"

        run(scenario())

    def test_new_application_shutdown_is_clean(self):
        lifecycle = ApplicationLifecycle()
        called = []

        async def observability() -> None:
            await asyncio.sleep(0)
            called.append(1)

        lifecycle.set_observability_cleanup(observability)

        async def scenario():
            report = await lifecycle.shutdown()
            assert report.final_state is LifecycleState.STOPPED
            assert report.cleanup_status is CleanupStatus.SUCCESS

        run(scenario())
        assert called == [1]

    def test_repeated_shutdown_does_not_release_twice(self):
        recorder = Recorder()
        lifecycle = ApplicationLifecycle()
        lifecycle.register(recorder.component("a"))

        async def scenario():
            await lifecycle.start()
            first = await lifecycle.shutdown()
            second = await lifecycle.shutdown()
            assert first is second
            assert await lifecycle._cleanup() is False  # noqa: SLF001

        run(scenario())
        assert recorder.release_counts == {"a": 1}

    def test_restart_after_stop_reinitializes(self):
        recorder = Recorder()
        lifecycle = ApplicationLifecycle()
        lifecycle.register(recorder.component("a"))

        async def scenario():
            await lifecycle.start()
            await lifecycle.shutdown()
            assert lifecycle.state is LifecycleState.STOPPED
            await lifecycle.start()
            assert lifecycle.state is LifecycleState.READY
            await lifecycle.shutdown()

        run(scenario())
        assert recorder.acquire_counts == {"a": 2}
        assert recorder.release_counts == {"a": 2}

    def test_retry_after_failure(self):
        attempts = {"count": 0}

        async def initialize() -> None:
            await asyncio.sleep(0)
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise ComponentError("not yet")

        lifecycle = ApplicationLifecycle()
        lifecycle.register(LifecycleComponent(name="flaky", initialize=initialize))

        async def scenario():
            with pytest.raises(ComponentError):
                await lifecycle.start()
            assert lifecycle.state is LifecycleState.FAILED
            await lifecycle.start()
            assert lifecycle.state is LifecycleState.READY
            await lifecycle.shutdown()

        run(scenario())


# ── Registration and transitions ────────────────────────────────────────────


class TestLifecycleContract:
    def test_registration_rejects_duplicates_unknown_dependencies_and_late_reentry(self):
        lifecycle = ApplicationLifecycle()
        lifecycle.register(LifecycleComponent(name="a"))

        with pytest.raises(ResourceOwnershipError):
            lifecycle.register(LifecycleComponent(name="a"))
        with pytest.raises(ResourceOwnershipError, match="registered before"):
            lifecycle.register(LifecycleComponent(name="b", depends_on=("missing",)))

        async def scenario():
            await lifecycle.start()
            with pytest.raises(LifecycleError, match="before startup"):
                lifecycle.register(LifecycleComponent(name="late"))
            with pytest.raises(LifecycleTransitionError):
                await lifecycle.start()
            await lifecycle.shutdown()

        run(scenario())

    def test_shutdown_rejects_starting_state(self):
        lifecycle = ApplicationLifecycle()
        lifecycle._state_machine.transition_to(LifecycleState.STARTING)  # noqa: SLF001
        with pytest.raises(LifecycleTransitionError):
            run(lifecycle.shutdown())

    def test_components_are_exposed_read_only(self):
        lifecycle = ApplicationLifecycle()
        lifecycle.register(LifecycleComponent(name="a"))
        assert [component.name for component in lifecycle.components] == ["a"]


# ── Cancellation ────────────────────────────────────────────────────────────


class TestCancellation:
    def test_cancellation_during_startup_rolls_back(self):
        recorder = Recorder()
        entered = asyncio.Event()

        async def blocking() -> None:
            entered.set()
            await asyncio.Event().wait()

        lifecycle = ApplicationLifecycle()
        lifecycle.register(recorder.component("acquired"))
        lifecycle.register(LifecycleComponent(name="blocking", initialize=blocking))

        async def scenario():
            task = asyncio.create_task(lifecycle.start())
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert lifecycle.state is LifecycleState.FAILED
            assert "release:acquired" in recorder.events

        run(scenario())

    def test_cancellation_during_cleanup_continues_then_propagates(self):
        recorder = Recorder()
        release_started = asyncio.Event()
        recorder.release_enter["b"] = release_started
        recorder.block_release.add("b")
        lifecycle = ApplicationLifecycle()
        lifecycle.register(recorder.component("a"))
        lifecycle.register(recorder.component("b"))

        async def scenario():
            await lifecycle.start()
            task = asyncio.create_task(lifecycle.shutdown())
            await release_started.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert lifecycle.state is LifecycleState.FAILED
            assert lifecycle.report.cleanup_cancelled is True
            assert lifecycle.report.cleanup_status is CleanupStatus.INTERRUPTED

        run(scenario())
        assert "release:b" in recorder.events
        assert "release:a" in recorder.events

    def test_cancellation_during_background_stop_still_releases_resources(self):
        recorder = Recorder()
        lifecycle = ApplicationLifecycle()

        class CancellingSupervisor:
            def reset(self) -> None:
                return None

            async def stop(self, _timeout: float):
                raise asyncio.CancelledError

        lifecycle.attach_background(CancellingSupervisor())  # type: ignore[arg-type]
        lifecycle.register(recorder.component("a"))

        async def scenario():
            await lifecycle.start()
            with pytest.raises(asyncio.CancelledError):
                await lifecycle.shutdown()
            assert lifecycle.report.cleanup_cancelled is True

        run(scenario())
        assert "release:a" in recorder.events


# ── Concurrency ─────────────────────────────────────────────────────────────


class TestConcurrency:
    def test_concurrent_start_only_one_wins(self):
        lifecycle = ApplicationLifecycle()

        async def scenario():
            first, second = await asyncio.gather(
                lifecycle.start(), lifecycle.start(), return_exceptions=True
            )
            assert isinstance(first, LifecycleReport)
            assert isinstance(second, LifecycleTransitionError)
            await lifecycle.shutdown()

        run(scenario())

    def test_concurrent_shutdown_runs_cleanup_once(self):
        recorder = Recorder()
        lifecycle = ApplicationLifecycle()
        lifecycle.register(recorder.component("a"))

        async def scenario():
            await lifecycle.start()
            results = await asyncio.gather(lifecycle.shutdown(), lifecycle.shutdown())
            assert results[0] is results[1]

        run(scenario())
        assert recorder.release_counts == {"a": 1}

    def test_shutdown_waits_for_start_then_terminates(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        async def slow_initialize() -> None:
            entered.set()
            await release.wait()

        lifecycle = ApplicationLifecycle()
        lifecycle.register(LifecycleComponent(name="slow", initialize=slow_initialize))

        async def scenario():
            start_task = asyncio.create_task(lifecycle.start())
            await entered.wait()
            shutdown_task = asyncio.create_task(lifecycle.shutdown())
            await asyncio.sleep(0)
            assert shutdown_task.done() is False
            release.set()
            await start_task
            await shutdown_task
            assert lifecycle.state is LifecycleState.STOPPED

        run(scenario())


# ── Background integration in the manager ───────────────────────────────────


class TestManagerBackground:
    def test_background_results_are_recorded(self):
        lifecycle = ApplicationLifecycle()

        class FakeSupervisor:
            def reset(self) -> None:
                return None

            async def stop(self, _timeout: float):
                return (TaskResult("worker", TaskOutcome.COMPLETED),)

        lifecycle.attach_background(FakeSupervisor())  # type: ignore[arg-type]

        async def scenario():
            await lifecycle.start()
            report = await lifecycle.shutdown()
            assert report.background == (TaskResult("worker", TaskOutcome.COMPLETED),)

        run(scenario())


# ── Adversarial sequences ───────────────────────────────────────────────────


@settings(max_examples=40, deadline=None)
@given(
    fail_at=st.integers(min_value=0, max_value=3),
    failing_cleanups=st.sets(st.integers(min_value=0, max_value=2)),
    repeat_shutdown=st.booleans(),
)
def test_rollback_invariants_across_failure_points(
    fail_at: int, failing_cleanups: set[int], repeat_shutdown: bool
):
    names = ("a", "b", "c")
    recorder = Recorder()
    recorder.release_fail_on.update(names[index] for index in failing_cleanups)
    if fail_at < len(names):
        recorder.fail_on.add(names[fail_at])

    lifecycle = ApplicationLifecycle()
    for name in names:
        lifecycle.register(recorder.component(name))

    async def scenario():
        if fail_at < len(names):
            with pytest.raises(ComponentError):
                await lifecycle.start()
            assert lifecycle.state is LifecycleState.FAILED
            acquired = names[:fail_at]
        else:
            await lifecycle.start()
            assert lifecycle.state is LifecycleState.READY
            acquired = names
            await lifecycle.shutdown()

        if repeat_shutdown:
            await lifecycle.shutdown()

        for name in names:
            assert recorder.release_counts.get(name, 0) <= recorder.acquire_counts.get(name, 0)
        for name in acquired:
            assert recorder.release_counts.get(name, 0) == 1
        assert recorder.release_counts.get(names[-1], 0) == (1 if names[-1] in acquired else 0)

    run(scenario())


@settings(max_examples=30, deadline=None)
@given(st.lists(st.sampled_from(["start", "shutdown"]), min_size=1, max_size=8))
def test_operation_sequences_never_release_more_than_acquired(operations: list[str]):
    recorder = Recorder()
    lifecycle = ApplicationLifecycle()
    for name in ("a", "b"):
        lifecycle.register(recorder.component(name))

    async def scenario():
        for operation in operations:
            try:
                if operation == "start":
                    await lifecycle.start()
                else:
                    await lifecycle.shutdown()
            except LifecycleError, LifecycleTransitionError:
                pass
        if lifecycle.state not in {LifecycleState.STOPPED, LifecycleState.FAILED}:
            await lifecycle.shutdown()
        for name in ("a", "b"):
            assert recorder.release_counts.get(name, 0) <= recorder.acquire_counts.get(name, 0)

    run(scenario())


# ── ASGI integration, state isolation, readiness ────────────────────────────


class TestApplicationIntegration:
    def test_create_app_starts_new_and_lifespan_owns_state(self):
        from waxprep.main import create_app

        app = create_app()
        assert app.state.lifecycle.state is LifecycleState.NEW
        app_state = app.state.app_state

        with TestClient(app) as client:
            assert app.state.lifecycle.state is LifecycleState.READY
            assert app_state.registries_ready is True
            assert client.get("/health/readiness").status_code == 200

        assert app.state.lifecycle.state is LifecycleState.STOPPED
        assert app_state.channel_registry is None
        assert app.state.supervisor.active_tasks == ()

    def test_two_apps_have_independent_state(self):
        from waxprep.main import create_app

        first = create_app()
        second = create_app()
        assert first.state.app_state is not second.state.app_state
        assert first.state.lifecycle is not second.state.lifecycle

        with TestClient(first) as first_client, TestClient(second) as second_client:
            first.state.app_state.registries_ready = False
            assert first_client.get("/health/readiness").status_code == 503
            assert second_client.get("/health/readiness").status_code == 200

    def test_readiness_reflects_lifecycle_draining(self):
        from starlette.requests import Request

        from waxprep.main import AppState, readiness

        app = FastAPI()
        lifecycle = ApplicationLifecycle()
        lifecycle._state_machine.transition_to(LifecycleState.STARTING)  # noqa: SLF001
        lifecycle._state_machine.transition_to(LifecycleState.READY)  # noqa: SLF001
        lifecycle._state_machine.transition_to(LifecycleState.DRAINING)  # noqa: SLF001
        app.state.app_state = AppState()
        app.state.lifecycle = lifecycle
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/health/readiness",
            "headers": [],
            "app": app,
        })
        response = run(readiness(request))
        assert response.status_code == 503
        assert b"lifecycle_not_ready" in response.body

    def test_readiness_helper_without_app_state_or_lifecycle(self):
        from waxprep.main import AppState, _readiness_failure_reason

        lifecycle = ApplicationLifecycle()

        async def scenario():
            await lifecycle.start()
            return lifecycle

        lifecycle = run(scenario())
        assert _readiness_failure_reason(None, lifecycle) == "registries_not_initialized"
        assert _readiness_failure_reason(AppState(), None) == "lifecycle_not_ready"

    def test_manual_fastapi_gets_per_instance_resources(self):
        from starlette.requests import Request

        from waxprep.main import AppState, lifespan, readiness

        app = FastAPI(lifespan=lifespan)
        with TestClient(app):
            assert isinstance(app.state.app_state, AppState)
            assert app.state.lifecycle.state is LifecycleState.READY
            assert app.state.app_state.shutting_down is False
        assert app.state.lifecycle.state is LifecycleState.STOPPED

        bare = FastAPI()
        bare.state.app_state = AppState()
        bare.state.lifecycle = ApplicationLifecycle()
        request = Request({
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "app": bare,
        })
        assert run(readiness(request)).status_code == 503

    def test_repeated_lifespan_on_same_app(self):
        from waxprep.main import create_app

        app = create_app()
        for _ in range(2):
            with TestClient(app) as client:
                assert app.state.lifecycle.state is LifecycleState.READY
                assert client.get("/health/readiness").status_code == 200
            assert app.state.lifecycle.state is LifecycleState.STOPPED

    def test_startup_failure_propagates_from_asgi_lifespan(self):
        from waxprep.main import AppState, lifespan

        async def fail() -> None:
            await asyncio.sleep(0)
            raise ComponentError("startup exploded")

        app = FastAPI(lifespan=lifespan)
        app.state.app_state = AppState()
        lifecycle = ApplicationLifecycle()
        lifecycle.register(LifecycleComponent(name="broken", initialize=fail))
        app.state.lifecycle = lifecycle
        app.state.supervisor = BackgroundTaskSupervisor()

        with pytest.raises(ComponentError):
            with TestClient(app):
                pass
        assert lifecycle.state is LifecycleState.FAILED

    def test_default_components_have_explicit_order_and_dependencies(self):
        from waxprep.main import create_app

        lifecycle = create_app().state.lifecycle
        assert [component.name for component in lifecycle.components] == [
            "configuration",
            "registries",
            "telemetry",
        ]
        assert lifecycle.components[1].depends_on == ("configuration",)
        assert lifecycle.components[2].mandatory is False

    def test_import_and_factory_do_not_start_resources(self):
        import waxprep.lifecycle as lifecycle_package
        from waxprep.main import create_app

        assert not any(
            isinstance(value, ApplicationLifecycle) for value in vars(lifecycle_package).values()
        )
        app = create_app()
        assert app.state.lifecycle.state is LifecycleState.NEW
        assert app.state.supervisor.active_tasks == ()
