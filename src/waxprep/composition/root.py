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
from waxprep.composition.bundles import AdapterSelection, ApplicationDependencies
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
                ),
                lifetime=Lifetime.APPLICATION,
                name="application-dependencies",
            )
        )
        resolved = graph.build(overrides=self._overrides)
        return cast(ApplicationDependencies, resolved[ApplicationDependencies])

    def _select_adapters(self) -> AdapterSelection:
        return self._adapters or AdapterSelection(
            channel=FakeChannelAdapter(),
            model=FakeModelAdapter(),
            tool=FakeTool(),
        )
