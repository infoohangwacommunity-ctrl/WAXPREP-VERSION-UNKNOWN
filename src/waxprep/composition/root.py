"""The authoritative application composition root (Stage 18).

``CompositionRoot`` is the only production location that selects concrete
infrastructure implementations and builds the application dependency graph. It
returns a typed, immutable ``ApplicationDependencies`` bundle; it does not expose
a service locator, process messages or contain business logic.

Construction is synchronous and in-memory. Asynchronous resource initialization
and release are delegated to the Stage 16 lifecycle, which owns the component
order, rollback and reverse cleanup.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

from waxprep.adapters.fake_channel import FakeChannelAdapter
from waxprep.adapters.fake_model import FakeModelAdapter
from waxprep.adapters.fake_tool import FakeTool
from waxprep.background.registration import JobContributor
from waxprep.background.registry import JobRegistry
from waxprep.background.runtime import (
    BackgroundRuntime,
    UnavailableBackgroundRuntime,
    WorkerBackgroundRuntime,
)
from waxprep.composition.bundles import (
    AdapterSelection,
    ApplicationDependencies,
    WorkerDependencies,
)
from waxprep.composition.graph import DependencyGraph, ProviderSpec
from waxprep.composition.lifetimes import Lifetime
from waxprep.config import Settings
from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry


class CompositionRoot:
    """Assemble one application dependency bundle."""

    def __init__(
        self,
        app_settings: Settings,
        *,
        adapters: AdapterSelection | None = None,
        overrides: Mapping[type[Any], Any] | None = None,
        job_contributors: Sequence[JobContributor] = (),
        background_middlewares: Sequence[Any] = (),
        background_factory: Callable[[JobRegistry, bool], WorkerBackgroundRuntime] | None = None,
    ) -> None:
        self._settings = app_settings
        self._adapters = adapters
        self._overrides = dict(overrides or {})
        self._job_contributors = tuple(job_contributors)
        self._background_middlewares = tuple(background_middlewares)
        self._background_factory = background_factory

    @property
    def settings(self) -> Settings:
        return self._settings

    def build(
        self,
        *,
        lifecycle: ApplicationLifecycle,
        supervisor: BackgroundTaskSupervisor,
    ) -> ApplicationDependencies:
        graph = DependencyGraph()
        graph.register(
            ProviderSpec(
                Settings,
                lambda: self._settings,
                lifetime=Lifetime.PROCESS,
                name="settings",
            )
        )
        for registry_type, name in (
            (ChannelRegistry, "channel-registry"),
            (ModelRegistry, "model-registry"),
            (ToolRegistry, "tool-registry"),
        ):
            graph.register(ProviderSpec(registry_type, registry_type, name=name))
        graph.register(
            ProviderSpec(
                AdapterSelection,
                self._select_adapters,
                lifetime=Lifetime.APPLICATION,
                name="adapter-selection",
            )
        )
        graph.register(
            ProviderSpec(
                JobRegistry,
                self._new_job_registry,
                lifetime=Lifetime.APPLICATION,
                name="job-registry",
            )
        )
        graph.register(
            ProviderSpec(
                BackgroundRuntime,
                self._select_background,
                dependencies=(JobRegistry,),
                lifetime=Lifetime.APPLICATION,
                name="background-runtime",
            )
        )
        graph.register(
            ProviderSpec(
                ApplicationLifecycle,
                lambda: lifecycle,
                lifetime=Lifetime.APPLICATION,
                name="lifecycle",
            )
        )
        graph.register(
            ProviderSpec(
                BackgroundTaskSupervisor,
                lambda: supervisor,
                lifetime=Lifetime.APPLICATION,
                name="background-supervisor",
            )
        )
        graph.register(
            ProviderSpec(
                ApplicationDependencies,
                ApplicationDependencies,
                dependencies=(
                    Settings,
                    ChannelRegistry,
                    ModelRegistry,
                    ToolRegistry,
                    AdapterSelection,
                    ApplicationLifecycle,
                    BackgroundTaskSupervisor,
                    BackgroundRuntime,
                ),
                lifetime=Lifetime.APPLICATION,
                name="application-dependencies",
            )
        )
        resolved = graph.build(overrides=self._overrides)
        return cast(ApplicationDependencies, resolved[ApplicationDependencies])

    def build_worker(
        self,
        *,
        lifecycle: ApplicationLifecycle,
        supervisor: BackgroundTaskSupervisor,
        registry: JobRegistry | None = None,
        background: WorkerBackgroundRuntime | None = None,
    ) -> WorkerDependencies:
        """Assemble a worker bundle without FastAPI or HTTP dependencies."""
        job_registry = registry or self._new_job_registry()
        graph = DependencyGraph()
        graph.register(ProviderSpec(Settings, lambda: self._settings, lifetime=Lifetime.PROCESS))
        graph.register(ProviderSpec(JobRegistry, lambda: job_registry))
        graph.register(
            ProviderSpec(
                WorkerBackgroundRuntime,
                lambda _job_registry: (
                    background or self._default_background(job_registry, worker_process=True)
                ),
                dependencies=(JobRegistry,),
                name="background-runtime",
            )
        )
        graph.register(ProviderSpec(ApplicationLifecycle, lambda: lifecycle, name="lifecycle"))
        graph.register(
            ProviderSpec(
                BackgroundTaskSupervisor,
                lambda: supervisor,
                name="background-supervisor",
            )
        )
        graph.register(
            ProviderSpec(
                WorkerDependencies,
                WorkerDependencies,
                dependencies=(
                    Settings,
                    JobRegistry,
                    WorkerBackgroundRuntime,
                    ApplicationLifecycle,
                    BackgroundTaskSupervisor,
                ),
                name="worker-dependencies",
            )
        )
        resolved = graph.build(overrides=self._overrides)
        return cast(WorkerDependencies, resolved[WorkerDependencies])

    def _select_background(self, registry: JobRegistry) -> BackgroundRuntime:
        return self._default_background(registry, worker_process=False)

    def _default_background(
        self,
        registry: JobRegistry,
        *,
        worker_process: bool,
    ) -> WorkerBackgroundRuntime:
        if self._background_factory is not None:
            return self._background_factory(registry, worker_process)
        if self._settings.environment.value not in {"development", "test"}:
            return UnavailableBackgroundRuntime()
        try:
            from waxprep.background.taskiq import TaskiqBackgroundRuntime
        except ImportError:
            return UnavailableBackgroundRuntime()
        return TaskiqBackgroundRuntime(
            registry,
            middlewares=self._background_middlewares,
            worker_process=worker_process,
        )

    def _new_job_registry(self) -> JobRegistry:
        registry = JobRegistry()
        for contributor in self._job_contributors:
            contributor.register_jobs(registry)
        return registry

    def _select_adapters(self) -> AdapterSelection:
        return self._adapters or AdapterSelection(
            channel=FakeChannelAdapter(),
            model=FakeModelAdapter(),
            tool=FakeTool(),
        )
