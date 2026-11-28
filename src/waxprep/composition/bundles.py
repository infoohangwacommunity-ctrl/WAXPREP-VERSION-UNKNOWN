"""Typed application dependency bundles (Stage 18).

Bundles are small, purpose-specific and use concrete Python types — never a
string-keyed dictionary or one enormous global container. The application bundle
is the set of dependencies the application boundary (HTTP today, a worker later)
receives from the composition root.
"""

from __future__ import annotations

from dataclasses import dataclass

from waxprep.background.registry import JobRegistry
from waxprep.background.runtime import BackgroundRuntime, WorkerBackgroundRuntime
from waxprep.config import Settings
from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor
from waxprep.registries.channel import ChannelAdapter, ChannelRegistry
from waxprep.registries.model import ModelAdapter, ModelRegistry
from waxprep.registries.tool import Tool, ToolRegistry


@dataclass(frozen=True, slots=True)
class AdapterSelection:
    """Concrete adapter implementations selected by the composition root.

    Registries register and look up adapters; they do not decide which concrete
    implementation the application uses.
    """

    channel: ChannelAdapter
    model: ModelAdapter
    tool: Tool

    def __post_init__(self) -> None:
        for label, adapter in (
            ("channel", self.channel),
            ("model", self.model),
            ("tool", self.tool),
        ):
            name = getattr(adapter, "name", None)
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"{label} adapter must expose a non-empty name")


@dataclass(frozen=True, slots=True)
class ApplicationDependencies:
    """Application-scope dependencies assembled once per lifecycle execution.

    Immutability is shallow: frozen prevents replacing a field, but contained
    objects (registries, lifecycle, supervisor, adapters) are application-owned
    and retain their own mutability/lifetime rules. The bundle is a reference
    list, not a deep copy or a second ownership system.
    """

    settings: Settings
    channel_registry: ChannelRegistry
    model_registry: ModelRegistry
    tool_registry: ToolRegistry
    adapters: AdapterSelection
    lifecycle: ApplicationLifecycle
    supervisor: BackgroundTaskSupervisor
    background: BackgroundRuntime


@dataclass(frozen=True, slots=True)
class WorkerDependencies:
    """Worker-scope dependencies assembled by the composition root.

    The worker receives only what it needs; it does not inherit the HTTP
    application, FastAPI, middleware or request handlers.
    """

    settings: Settings
    job_registry: JobRegistry
    background: WorkerBackgroundRuntime
    lifecycle: ApplicationLifecycle
    supervisor: BackgroundTaskSupervisor
