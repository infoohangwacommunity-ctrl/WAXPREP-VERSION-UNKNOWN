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

from collections.abc import Mapping
from typing import Any, cast

from waxprep.adapters.fake_channel import FakeChannelAdapter
from waxprep.adapters.fake_model import FakeModelAdapter
from waxprep.adapters.fake_tool import FakeTool
from waxprep.background.registry import JobRegistry
from waxprep.background.runtime import BackgroundRuntime, UnavailableBackgroundRuntime
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
    ) -> None:
        self._settings = app_settings
        self._adapters = adapters
        self._overrides = dict(overrides or {})

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
                JobRegistry,
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
        background: BackgroundRuntime | None = None,
    ) -> WorkerDependencies:
        """Assemble a worker bundle without FastAPI or HTTP dependencies."""
        job_registry = registry or JobRegistry()
        graph = DependencyGraph()
        graph.register(ProviderSpec(Settings, lambda: self._settings, lifetime=Lifetime.PROCESS))
        graph.register(ProviderSpec(JobRegistry, lambda: job_registry))
        graph.register(
            ProviderSpec(
                BackgroundRuntime,
                lambda _job_registry: background or self._default_background(job_registry),
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
                    BackgroundRuntime,
                    ApplicationLifecycle,
                    BackgroundTaskSupervisor,
                ),
                name="worker-dependencies",
            )
        )
        resolved = graph.build(overrides=self._overrides)
        return cast(WorkerDependencies, resolved[WorkerDependencies])

    def _select_background(self, registry: JobRegistry) -> BackgroundRuntime:
        return self._default_background(registry)

    @staticmethod
    def _default_background(registry: JobRegistry) -> BackgroundRuntime:
        try:
            from waxprep.background.taskiq import TaskiqBackgroundRuntime
        except ImportError:
            return UnavailableBackgroundRuntime()
        return TaskiqBackgroundRuntime(registry)

    def _select_adapters(self) -> AdapterSelection:
        return self._adapters or AdapterSelection(
            channel=FakeChannelAdapter(),
            model=FakeModelAdapter(),
            tool=FakeTool(),
        )
