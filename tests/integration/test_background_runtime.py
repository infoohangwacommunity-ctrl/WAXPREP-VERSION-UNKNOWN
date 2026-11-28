"""Stage 19 — Taskiq runtime, worker lifecycle and composition integration."""

from __future__ import annotations

import asyncio
import builtins
import multiprocessing
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
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


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _worker_process(port: int, marker: str, stop_mp: Any) -> None:
    from taskiq import ZeroMQBroker

    from waxprep.background.registry import JobHandler, JobRegistry
    from waxprep.background.runtime import WorkerBackgroundRuntime
    from waxprep.background.taskiq import TaskiqBackgroundRuntime
    from waxprep.composition import CompositionRoot
    from waxprep.config import settings
    from waxprep.contracts.models.result import (
        OperationResult,
        OperationStatus,
        OperationSuccess,
    )
    from waxprep.worker import BackgroundWorker

    async def main() -> None:
        async def handle(envelope: MessageEnvelope[OperationSuccess]) -> OperationResult:  # noqa: RUF029
            Path(marker).write_text(envelope.payload.detail or "", encoding="utf-8")
            return OperationResult(OperationSuccess(status=OperationStatus.SUCCESS))

        registry = JobRegistry()
        registry.register(
            JobHandler(
                task_name="waxprep.test.workerjob",
                payload_type=OperationSuccess,
                handler=handle,
            )
        )
        broker = ZeroMQBroker(
            zmq_pub_host=f"tcp://127.0.0.1:{port}",
            zmq_sub_host=f"tcp://127.0.0.1:{port}",
        )
        runtime = TaskiqBackgroundRuntime(registry, broker=broker, worker_process=True)
        root = CompositionRoot(
            settings,
            overrides={WorkerBackgroundRuntime: runtime},
        )
        stop_event = asyncio.Event()

        async def watch() -> None:
            while not stop_mp.is_set():
                await asyncio.sleep(0.02)
            stop_event.set()

        watcher = asyncio.create_task(watch())
        try:
            await BackgroundWorker(composition_root=root, registry=registry).run(stop_event)
        finally:
            watcher.cancel()
            broker.socket.close(linger=0)
            broker.context.term()

    asyncio.run(main())


def envelope(
    task_name: str = "waxprep.test.job", detail: str = "payload"
) -> MessageEnvelope[OperationSuccess]:
    return MessageEnvelope[OperationSuccess](
        message_id=uuid4(),
        message_kind=MessageKind.EVENT,
        message_type=task_name,
        contract_version="1.0.0",
        correlation_id=uuid4(),
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        producer="waxprep.test",
        payload=OperationSuccess(status=OperationStatus.SUCCESS, detail=detail),
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
        with pytest.raises(BackgroundUnavailableError):
            asyncio.run(runtime.consume(asyncio.Event()))
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

    @pytest.mark.skipif(sys.platform == "win32", reason="fork-based cross-process test")
    def test_producer_and_independent_worker_communicate(self, tmp_path: Path):
        port = _free_port()
        marker = tmp_path / "executed.txt"
        context = multiprocessing.get_context("fork")
        stop_mp = context.Event()
        process = context.Process(
            target=_worker_process,
            args=(port, str(marker), stop_mp),
        )
        process.start()
        try:
            asyncio.run(asyncio.sleep(0.4))
            from taskiq import ZeroMQBroker

            from waxprep.background.runtime import WorkerBackgroundRuntime
            from waxprep.background.taskiq import TaskiqBackgroundRuntime
            from waxprep.composition import CompositionRoot

            async def producer() -> None:
                broker = ZeroMQBroker(
                    zmq_pub_host=f"tcp://127.0.0.1:{port}",
                    zmq_sub_host=f"tcp://127.0.0.1:{port}",
                )
                runtime = TaskiqBackgroundRuntime(JobRegistry(), broker=broker)
                root = CompositionRoot(
                    settings,
                    overrides={WorkerBackgroundRuntime: runtime},
                )
                dependencies = root.build_worker(
                    lifecycle=ApplicationLifecycle(),
                    supervisor=BackgroundTaskSupervisor(),
                )
                await dependencies.background.start()
                try:
                    job = envelope(
                        task_name="waxprep.test.workerjob",
                        detail=str(marker),
                    )
                    for _ in range(10):
                        await dependencies.background.submit(job)
                        for _ in range(25):
                            if marker.is_file():
                                return
                            await asyncio.sleep(0.1)
                finally:
                    await dependencies.background.stop()
                    broker.socket.close(linger=0)
                    broker.context.term()

            from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor

            asyncio.run(producer())
            assert marker.is_file(), "independent worker did not execute the submitted job"
        finally:
            stop_mp.set()
            process.join(timeout=10)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    def test_consume_requires_started_runtime(self):
        from waxprep.background.taskiq import TaskiqBackgroundRuntime

        async def scenario():
            runtime = TaskiqBackgroundRuntime(JobRegistry())
            with pytest.raises(BackgroundUnavailableError, match="not started"):
                await runtime.consume(asyncio.Event())

        asyncio.run(scenario())

    def test_consume_uses_taskiq_receiver_for_non_memory_broker(self, monkeypatch):
        from taskiq import receiver as receiver_module

        from waxprep.background.taskiq import TaskiqBackgroundRuntime

        called = []

        class FakeBroker:
            is_worker_process = False

            def task(self, _name):
                return lambda function: function

            async def startup(self):
                return None

            async def shutdown(self):
                return None

        class FakeReceiver:
            def __init__(self, *_args, **_kwargs):
                pass

            async def listen(self, stop_event):
                called.append(stop_event)

        monkeypatch.setattr(receiver_module, "Receiver", FakeReceiver)

        async def scenario():
            stop = asyncio.Event()
            runtime = TaskiqBackgroundRuntime(JobRegistry(), broker=FakeBroker())  # type: ignore[arg-type]
            await runtime.start()
            try:
                await runtime.consume(stop)
            finally:
                await runtime.stop()

        asyncio.run(scenario())
        assert called and called[0] is not None

    def test_in_memory_broker_cannot_run_an_independent_worker(self):
        from waxprep.background.taskiq import TaskiqBackgroundRuntime

        async def scenario():
            runtime = TaskiqBackgroundRuntime(JobRegistry())
            await runtime.start()
            try:
                with pytest.raises(BackgroundUnavailableError, match="InMemoryBroker"):
                    await runtime.consume(asyncio.Event())
            finally:
                await runtime.stop()

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
        from waxprep.background.runtime import WorkerBackgroundRuntime

        class FakeWorkerRuntime:
            active = False

            async def start(self):
                self.active = True

            async def stop(self):
                self.active = False

            async def submit(self, _envelope):
                raise AssertionError("worker does not submit")

            async def consume(self, stop_event):
                await stop_event.wait()

        fake = FakeWorkerRuntime()
        root = CompositionRoot(settings, overrides={WorkerBackgroundRuntime: fake})

        async def handler(_envelope):  # noqa: RUF029
            return OperationResult(OperationSuccess(status=OperationStatus.SUCCESS))

        registry = JobRegistry()
        registry.register(
            JobHandler(
                task_name="waxprep.test.job",
                payload_type=OperationSuccess,
                handler=handler,
            )
        )

        async def scenario():
            stop = asyncio.Event()
            worker = BackgroundWorker(composition_root=root, registry=registry)
            task = asyncio.create_task(worker.run(stop))
            await asyncio.sleep(0.05)
            stop.set()
            await asyncio.wait_for(task, timeout=2)

        asyncio.run(scenario())
        assert fake.active is False

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

    def test_worker_refuses_an_empty_job_registry(self):
        from waxprep.background.errors import JobRegistrationError
        from waxprep.background.runtime import WorkerBackgroundRuntime

        class FakeWorkerRuntime:
            active = False

            async def start(self):
                self.active = True

            async def stop(self):
                self.active = False

            async def submit(self, _envelope):
                return "fake"

            async def consume(self, stop_event):
                await stop_event.wait()

        fake = FakeWorkerRuntime()
        root = CompositionRoot(settings, overrides={WorkerBackgroundRuntime: fake})
        with pytest.raises(JobRegistrationError, match="job contributor"):
            asyncio.run(
                BackgroundWorker(composition_root=root, registry=JobRegistry()).run(asyncio.Event())
            )
        assert fake.active is False

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


class TestBrokerSelectionAndRegistration:
    def test_in_memory_is_not_selected_outside_dev_or_test(self):
        from waxprep.composition import CompositionRoot
        from waxprep.config import Settings

        class Contributor:
            def register_jobs(self, registry):
                registry.register(
                    JobHandler(
                        task_name="waxprep.test.job",
                        payload_type=OperationSuccess,
                        handler=lambda _envelope: None,  # type: ignore[arg-type]
                    )
                )

        for environment in ("staging", "production"):
            configured = Settings(
                _env_file=None,
                environment=environment,
                host="0.0.0.0",
                port=8000,
                log_level="INFO",
            )
            from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor

            dependencies = CompositionRoot(configured, job_contributors=(Contributor(),)).build(
                lifecycle=ApplicationLifecycle(),
                supervisor=BackgroundTaskSupervisor(),
            )
            assert isinstance(dependencies.background, UnavailableBackgroundRuntime)

    def test_production_accepts_an_explicit_broker_factory(self):
        from waxprep.composition import CompositionRoot
        from waxprep.config import Settings
        from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor

        configured = Settings(
            _env_file=None,
            environment="production",
            host="0.0.0.0",
            port=8000,
            log_level="INFO",
        )
        fake = _FakeRuntime()

        dependencies = CompositionRoot(
            configured,
            background_factory=lambda _registry, _worker: fake,  # type: ignore[arg-type,return-value]
        ).build(
            lifecycle=ApplicationLifecycle(),
            supervisor=BackgroundTaskSupervisor(),
        )
        assert dependencies.background is fake

    def test_job_contributors_populate_the_worker_registry(self):
        from waxprep.composition import CompositionRoot
        from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor

        class Contributor:
            def register_jobs(self, registry):
                registry.register(
                    JobHandler(
                        task_name="waxprep.test.job",
                        payload_type=OperationSuccess,
                        handler=lambda _envelope: None,  # type: ignore[arg-type]
                    )
                )

        bundle = CompositionRoot(settings, job_contributors=(Contributor(),)).build_worker(
            lifecycle=ApplicationLifecycle(),
            supervisor=BackgroundTaskSupervisor(),
        )
        assert bundle.job_registry.task_names == ("waxprep.test.job",)

    def test_taskiq_retry_middleware_is_usable_through_composition(self):
        from taskiq import SmartRetryMiddleware

        from waxprep.composition import CompositionRoot
        from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor

        attempts = {"count": 0}
        succeeded = asyncio.Event()

        async def flaky(_envelope):  # noqa: RUF029
            attempts["count"] += 1
            if attempts["count"] == 1:
                raise RuntimeError("transient")
            succeeded.set()
            return OperationResult(OperationSuccess(status=OperationStatus.SUCCESS))

        class Contributor:
            def register_jobs(self, registry):
                registry.register(
                    JobHandler(
                        task_name="waxprep.test.retry",
                        payload_type=OperationSuccess,
                        handler=flaky,
                    )
                )

        retry = SmartRetryMiddleware(
            default_retry_count=2,
            default_retry_label=True,
            default_delay=0,
            use_jitter=False,
            types_of_exceptions=(RuntimeError,),
        )
        dependencies = CompositionRoot(
            settings,
            job_contributors=(Contributor(),),
            background_middlewares=(retry,),
        ).build(
            lifecycle=ApplicationLifecycle(),
            supervisor=BackgroundTaskSupervisor(),
        )

        async def scenario():
            await dependencies.background.start()
            try:
                await dependencies.background.submit(envelope(task_name="waxprep.test.retry"))
                await asyncio.wait_for(succeeded.wait(), timeout=3)
            finally:
                await dependencies.background.stop()

        asyncio.run(scenario())
        assert attempts["count"] >= 2


class _FakeRuntime:
    active = False

    async def start(self):
        self.active = True

    async def stop(self):
        self.active = False

    async def submit(self, _envelope):
        return "fake"

    async def consume(self, stop_event):
        await stop_event.wait()
