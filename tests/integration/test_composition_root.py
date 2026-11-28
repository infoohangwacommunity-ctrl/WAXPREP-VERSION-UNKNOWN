"""Stage 18 — composition root, application bundle and lifecycle integration."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from waxprep.adapters.fake_channel import FakeChannelAdapter
from waxprep.adapters.fake_model import FakeModelAdapter
from waxprep.adapters.fake_tool import FakeTool
from waxprep.composition import (
    AdapterSelection,
    ApplicationDependencies,
    AppState,
    CompositionRoot,
    register_application_components,
)
from waxprep.composition.application import _initialize_registries, _initialize_telemetry
from waxprep.composition.errors import CompositionError
from waxprep.config import settings
from waxprep.lifecycle import ApplicationLifecycle, BackgroundTaskSupervisor
from waxprep.main import create_app
from waxprep.registries.channel import ChannelRegistry
from waxprep.registries.model import ModelRegistry
from waxprep.registries.tool import ToolRegistry

pytestmark = pytest.mark.integration


def build_dependencies(root: CompositionRoot | None = None) -> ApplicationDependencies:
    lifecycle = ApplicationLifecycle()
    supervisor = BackgroundTaskSupervisor()
    return (root or CompositionRoot(settings)).build(
        lifecycle=lifecycle,
        supervisor=supervisor,
    )


class TestCompositionRoot:
    def test_default_bundle_has_typed_dependencies(self):
        dependencies = build_dependencies()
        assert dependencies.settings is settings
        assert isinstance(dependencies.channel_registry, ChannelRegistry)
        assert isinstance(dependencies.model_registry, ModelRegistry)
        assert isinstance(dependencies.tool_registry, ToolRegistry)
        assert isinstance(dependencies.adapters.channel, FakeChannelAdapter)
        assert isinstance(dependencies.adapters.model, FakeModelAdapter)
        assert isinstance(dependencies.adapters.tool, FakeTool)
        assert isinstance(dependencies.lifecycle, ApplicationLifecycle)
        assert isinstance(dependencies.supervisor, BackgroundTaskSupervisor)
        assert dependencies.channel_registry.list_all() == []

    def test_each_build_creates_new_application_scope_instances(self):
        root = CompositionRoot(settings)
        first = build_dependencies(root)
        second = build_dependencies(root)
        assert first.channel_registry is not second.channel_registry
        assert first.settings is second.settings

    def test_explicit_adapter_selection_is_used(self):
        selection = AdapterSelection(
            channel=FakeChannelAdapter(),
            model=FakeModelAdapter(),
            tool=FakeTool(),
        )
        dependencies = build_dependencies(CompositionRoot(settings, adapters=selection))
        assert dependencies.adapters is selection

    def test_overrides_replace_registries(self):
        registry = ChannelRegistry()
        dependencies = build_dependencies(
            CompositionRoot(settings, overrides={ChannelRegistry: registry})
        )
        assert dependencies.channel_registry is registry

    def test_root_exposes_settings(self):
        assert CompositionRoot(settings).settings is settings

    def test_invalid_adapter_selection_is_rejected(self):
        with pytest.raises(ValueError, match="non-empty name"):
            AdapterSelection(channel=object(), model=FakeModelAdapter(), tool=FakeTool())

    def test_selected_adapters_satisfy_registry_protocols(self):
        from waxprep.registries.channel import ChannelAdapter
        from waxprep.registries.model import ModelAdapter
        from waxprep.registries.tool import Tool

        selection = build_dependencies().adapters
        assert isinstance(selection.channel, ChannelAdapter)
        assert isinstance(selection.model, ModelAdapter)
        assert isinstance(selection.tool, Tool)

    def test_composition_is_deferred_until_lifespan(self):
        app = create_app()
        assert app.state.app_state.dependencies is None
        assert app.state.app_state.registries_ready is False
        with TestClient(app):
            assert app.state.app_state.dependencies is not None
        assert app.state.app_state.dependencies is None
        assert app.state.app_state.registries_ready is False

    def test_registry_initialization_requires_composition(self):
        with pytest.raises(CompositionError, match="without composed"):
            _initialize_registries(AppState())

    def test_telemetry_initialization_requires_composition(self):
        with pytest.raises(CompositionError, match="without composed"):
            _initialize_telemetry(AppState())


class TestApplicationComposition:
    def test_production_startup_does_not_call_registry_register_defaults(self, monkeypatch):
        def forbidden(_self) -> None:
            raise AssertionError("production must select adapters through composition")

        monkeypatch.setattr(ChannelRegistry, "register_defaults", forbidden)
        monkeypatch.setattr(ModelRegistry, "register_defaults", forbidden)
        monkeypatch.setattr(ToolRegistry, "register_defaults", forbidden)

        app = create_app()
        with TestClient(app) as client:
            assert client.get("/health/readiness").status_code == 200
            assert app.state.app_state.dependencies is not None
            assert app.state.app_state.channel_registry.is_registered("fake")
            assert app.state.app_state.model_registry.is_registered("fake")
            assert app.state.app_state.tool_registry.is_registered("fake_tool")

    def test_application_uses_composition_override(self):
        custom = ChannelRegistry()
        app = create_app(CompositionRoot(settings, overrides={ChannelRegistry: custom}))
        with TestClient(app):
            assert app.state.app_state.channel_registry is custom
            assert custom.is_registered("fake")

    def test_application_instances_have_separate_dependencies(self):
        first = create_app()
        second = create_app()
        with TestClient(first) as first_client, TestClient(second) as second_client:
            assert first.state.app_state.dependencies is not second.state.app_state.dependencies
            assert first_client.get("/health/readiness").status_code == 200
            assert second_client.get("/health/readiness").status_code == 200

    def test_composition_failure_rolls_back_startup(self):
        root = CompositionRoot(settings, overrides={ApplicationDependencies: object()})
        app = create_app(root)
        with pytest.raises(AttributeError):
            with TestClient(app):
                pass
        assert app.state.lifecycle.state.value == "failed"
        assert app.state.app_state.dependencies is None

    def test_app_state_reset_clears_dependencies(self):
        state = AppState()
        registry = ChannelRegistry()
        state.channel_registry = registry
        state.registries_ready = True
        state.shutting_down = True
        state.dependencies = build_dependencies()
        state.reset()
        assert state.channel_registry is None
        assert state.model_registry is None
        assert state.tool_registry is None
        assert state.dependencies is None
        assert state.registries_ready is False
        assert state.shutting_down is False

    def test_component_registration_is_one_authoritative_set(self):
        lifecycle = ApplicationLifecycle()
        supervisor = BackgroundTaskSupervisor()
        state = AppState()
        register_application_components(lifecycle, state, supervisor, CompositionRoot(settings))
        assert [component.name for component in lifecycle.components] == [
            "configuration",
            "composition",
            "registries",
            "telemetry",
        ]
