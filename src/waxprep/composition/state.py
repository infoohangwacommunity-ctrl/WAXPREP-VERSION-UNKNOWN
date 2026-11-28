"""Per-application mutable state (Stage 18).

The immutable dependency bundle is produced by the composition root; this small
state object holds the registries for request-time readiness checks and is reset
at every lifecycle boundary. It belongs to one FastAPI instance via ``app.state``.
"""

from __future__ import annotations

from waxprep.composition.bundles import ApplicationDependencies
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry


class AppState:
    """Application-instance data owned by one ``FastAPI`` instance."""

    def __init__(self) -> None:
        self._shutting_down: bool = False
        self._registries_ready: bool = False
        self._channel_registry: ChannelRegistry | None = None
        self._model_registry: ModelRegistry | None = None
        self._tool_registry: ToolRegistry | None = None
        self._dependencies: ApplicationDependencies | None = None

    @property
    def shutting_down(self) -> bool:
        return self._shutting_down

    @shutting_down.setter
    def shutting_down(self, value: bool) -> None:
        self._shutting_down = value

    @property
    def registries_ready(self) -> bool:
        return self._registries_ready

    @registries_ready.setter
    def registries_ready(self, value: bool) -> None:
        self._registries_ready = value

    @property
    def channel_registry(self) -> ChannelRegistry | None:
        return self._channel_registry

    @channel_registry.setter
    def channel_registry(self, value: ChannelRegistry | None) -> None:
        self._channel_registry = value

    @property
    def model_registry(self) -> ModelRegistry | None:
        return self._model_registry

    @model_registry.setter
    def model_registry(self, value: ModelRegistry | None) -> None:
        self._model_registry = value

    @property
    def tool_registry(self) -> ToolRegistry | None:
        return self._tool_registry

    @tool_registry.setter
    def tool_registry(self, value: ToolRegistry | None) -> None:
        self._tool_registry = value

    @property
    def dependencies(self) -> ApplicationDependencies | None:
        return self._dependencies

    @dependencies.setter
    def dependencies(self, value: ApplicationDependencies | None) -> None:
        self._dependencies = value

    def reset(self) -> None:
        """Drop every reference owned by a finished lifecycle execution."""
        self._shutting_down = False
        self._registries_ready = False
        self._channel_registry = None
        self._model_registry = None
        self._tool_registry = None
        self._dependencies = None
