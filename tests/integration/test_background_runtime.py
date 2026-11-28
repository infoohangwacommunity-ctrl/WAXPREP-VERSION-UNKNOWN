"""Stage 19 — Taskiq runtime, worker lifecycle and composition integration."""

from __future__ import annotations

import asyncio
import builtins
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from taskiq import TaskiqMiddleware, TaskiqResult

from waxprep.background import UnavailableBackgroundRuntime
from waxprep.background.errors import BackgroundUnavailableError
from waxprep.background.registry import JobHandler, JobRegistry
from waxprep.composition import CompositionRoot
from waxprep.config import settings
from waxprep.contracts.envelopes import MessageEnvelope, MessageKind
from waxprep.contracts.models.result import OperationResult, OperationStatus, OperationSuccess
from waxprep.worker import BackgroundWorker

pytestmark = pytest.mark.integration


def envelope(task_name: str = "waxprep.test.job") -> MessageEnvelope[OperationSuccess]:
    return MessageEnvelope[OperationSuccess](
        message_id=uuid4(),
        message_kind=MessageKind.EVENT,
        message_type=task_name,
        contract_version="1.0.0",
        correlation_id=uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        producer="waxprep.test",
        payload=OperationSuccess(status=OperationStatus.SUCCESS, detail="payload"),
    )


def registry_with(event: asyncio.Event) -> JobRegistry:
    async def handle(_envelope: MessageEnvelope[OperationSuccess]) -> OperationResult:  # noqa: RUF029
        event.set()
        return OperationResult(OperationSuccess(status=OperationStatus.SUCCESS, detail="done"))

    registry = JobRegistry()
    registry.register(
        JobHandler(
            task_name="waxprep.test.job",
            payload_type=OperationSuccess,
            handler=handle,
        )
    )
    return registry


class TestUnavailableRuntime:
    def test_submit_fails_closed(self):
        runtime = UnavailableBackgroundRuntime()
        assert runtime.active is False
        asyncio.run(runtime.start())
        with pytest.raises(BackgroundUnavailableError):
            asyncio.run(runtime.submit(envelope()))
        asyncio.run(runtime.stop())
        assert runtime.active is False


class TestTaskiqRuntime:
    def test_start_submit_execute_and_stop(self):
        from waxprep.background.taskiq import TaskiqBackgroundRuntime

        async def scenario():
            event = asyncio.Event()
            runtime = TaskiqBackgroundRuntime(registry_with(event))
            assert runtime.active is False
            with pytest.raises(BackgroundUnavailableError):
                await runtime.submit(envelope())
            await runtime.start()
            await runtime.start()  # idempotent
            assert runtime.active is True
            task_id = await runtime.submit(envelope())
            assert isinstance(task_id, str) and task_id
            await asyncio.wait_for(event.wait(), timeout=2)
            await runtime.stop()
            await runtime.stop()  # idempotent
            assert runtime.active is False

        asyncio.run(scenario())

    def test_middleware_extension_point_is_used(self):
        from waxprep.background.taskiq import TaskiqBackgroundRuntime

        seen: list[str] = []

        class RecordingMiddleware(TaskiqMiddleware):
            async def post_execute(self, message, result: TaskiqResult[Any]) -> None:
                seen.append(message.task_name)

        async def scenario():
            event = asyncio.Event()
            runtime = TaskiqBackgroundRuntime(
                registry_with(event),
                middlewares=(RecordingMiddleware(),),
            )
            await runtime.start()
            try:
                await runtime.submit(envelope())
                await asyncio.wait_for(event.wait(), timeout=2)
                await asyncio.sleep(0.02)
            finally:
                await runtime.stop()

        asyncio.run(scenario())
        assert seen

    def test_submission_failure_is_wrapped(self, monkeypatch):
        from waxprep.background import taskiq as taskiq_module

        async def scenario():
            runtime = taskiq_module.TaskiqBackgroundRuntime(JobRegistry())
            await runtime.start()
            try:
                monkeypatch.setattr(
                    taskiq_module,
                    "dump_contract",
                    lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("bad")),
                )
                with pytest.raises(Exception, match="could not be submitted"):
                    await runtime.submit(envelope())
            finally:
                await runtime.stop()

        asyncio.run(scenario())


class TestCompositionBackground:
    def test_application_bundle_owns_a_background_runtime(self):
        from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor

        dependencies = CompositionRoot(settings).build(
            lifecycle=ApplicationLifecycle(),
            supervisor=BackgroundTaskSupervisor(),
        )
        assert dependencies.background.active is False

    def test_taskiq_absent_degrades_to_unavailable(self, monkeypatch):
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "waxprep.background.taskiq":
                raise ImportError("simulated missing taskiq extra")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor

        dependencies = CompositionRoot(settings).build(
            lifecycle=ApplicationLifecycle(),
            supervisor=BackgroundTaskSupervisor(),
        )
        assert isinstance(dependencies.background, UnavailableBackgroundRuntime)
        with pytest.raises(BackgroundUnavailableError):
            asyncio.run(dependencies.background.submit(envelope()))

    def test_app_starts_and_stops_the_background_component(self):
        from waxprep.main import create_app

        app = create_app()
        assert app.state.app_state.dependencies is None
        with TestClient(app):
            dependencies = app.state.app_state.dependencies
            assert dependencies is not None
            assert dependencies.background.active is True
        assert app.state.app_state.dependencies is None


class TestWorker:
    def test_worker_bundle_has_no_fastapi_dependency(self):
        from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor

        bundle = CompositionRoot(settings).build_worker(
            lifecycle=ApplicationLifecycle(),
            supervisor=BackgroundTaskSupervisor(),
        )
        assert bundle.job_registry.task_names == ()
        assert bundle.background.active is False
        assert bundle.settings is settings

    def test_worker_runs_and_stops_with_explicit_signal(self):
        async def scenario():
            stop = asyncio.Event()
            worker = BackgroundWorker(registry=JobRegistry())
            task = asyncio.create_task(worker.run(stop))
            await asyncio.sleep(0.05)
            stop.set()
            await asyncio.wait_for(task, timeout=2)

        asyncio.run(scenario())

    def test_worker_import_does_not_import_fastapi_in_subprocess(self):
        import subprocess
        import sys

        code = (
            "import sys; import waxprep.worker; "
            "print('fastapi' in sys.modules, 'waxprep.main' in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.stdout.strip() == "False False"

    def test_worker_background_start_requires_composition(self):
        import asyncio

        from waxprep.worker import _start_background, _WorkerState

        with pytest.raises(RuntimeError, match="not composed"):
            asyncio.run(_start_background(_WorkerState()))

    def test_signal_entrypoint_adds_handlers_and_returns(self):
        import asyncio

        import waxprep.worker as worker_module

        async def fake_run(_self, stop_event):  # noqa: RUF029
            stop_event.set()

        original = worker_module.BackgroundWorker.run
        try:
            worker_module.BackgroundWorker.run = fake_run  # type: ignore[method-assign]
            asyncio.run(worker_module._run_until_signal())
        finally:
            worker_module.BackgroundWorker.run = original  # type: ignore[method-assign]

    def test_signal_entrypoint_tolerates_unsupported_loop(self, monkeypatch):
        import asyncio

        import waxprep.worker as worker_module

        async def fake_run(_self, stop_event):  # noqa: RUF029
            stop_event.set()

        def unsupported(_self, *_args, **_kwargs):
            raise NotImplementedError

        original = worker_module.BackgroundWorker.run
        try:
            worker_module.BackgroundWorker.run = fake_run  # type: ignore[method-assign]
            monkeypatch.setattr(asyncio.SelectorEventLoop, "add_signal_handler", unsupported)
            asyncio.run(worker_module._run_until_signal())
        finally:
            worker_module.BackgroundWorker.run = original  # type: ignore[method-assign]

    def test_run_worker_entrypoint_is_wired(self, monkeypatch):
        import waxprep.worker as worker_module

        calls: list[Any] = []

        def fake_run(coro):
            calls.append(coro)
            coro.close()

        monkeypatch.setattr("waxprep.worker.asyncio.run", fake_run)
        worker_module.run()
        assert len(calls) == 1

    def test_worker_module_main_guard_is_wired(self, monkeypatch):
        import runpy
        import sys

        calls: list[Any] = []

        def fake_run(coro):
            calls.append(coro)
            coro.close()

        monkeypatch.setattr("asyncio.run", fake_run)
        monkeypatch.delitem(sys.modules, "waxprep.worker", raising=False)
        runpy.run_module("waxprep.worker", run_name="__main__")
        assert len(calls) == 1
