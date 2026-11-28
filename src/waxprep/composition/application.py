"""Application lifecycle wiring for the composition root (Stage 18).

The composition root owns assembly; Stage 16 owns initialization and release.
This module connects them without creating a second lifecycle manager:

* ``configuration`` logs the validated non-secret identity;
* ``composition`` builds the typed dependency bundle;
* ``registries`` registers the adapters selected by the composition root;
* optional ``telemetry`` configures observability from the assembled settings;
* final observability cleanup runs after application resources.
"""

from __future__ import annotations

import structlog

from waxprep.composition.bundles import AdapterSelection
from waxprep.composition.errors import CompositionError
from waxprep.composition.root import CompositionRoot
from waxprep.composition.state import AppState
from waxprep.config import Settings
from waxprep.lifecycle import (
    ApplicationLifecycle,
    BackgroundTaskSupervisor,
    LifecycleComponent,
)
from waxprep.observability.metrics import metrics
from waxprep.observability.telemetry import TelemetryConfig, telemetry

logger = structlog.get_logger()


def _initialize_configuration(settings: Settings) -> None:
    logger.info(
        "Configuration loaded",
        environment=settings.environment.value,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.value,
    )


def _compose(
    app_state: AppState,
    lifecycle: ApplicationLifecycle,
    supervisor: BackgroundTaskSupervisor,
    root: CompositionRoot,
) -> None:
    dependencies = root.build(lifecycle=lifecycle, supervisor=supervisor)
    app_state.dependencies = dependencies
    logger.info(
        "composition_assembled",
        channel_adapter=dependencies.adapters.channel.name,
        model_adapter=dependencies.adapters.model.name,
        tool_adapter=dependencies.adapters.tool.name,
    )


def _release_composition(app_state: AppState) -> None:
    app_state.dependencies = None
    logger.info("composition_released")


def _initialize_registries(app_state: AppState) -> None:
    dependencies = app_state.dependencies
    if dependencies is None:
        raise CompositionError("Registries cannot initialize without composed dependencies")
    selection: AdapterSelection = dependencies.adapters
    dependencies.channel_registry.register(selection.channel.name, selection.channel)
    dependencies.model_registry.register(selection.model.name, selection.model)
    dependencies.tool_registry.register(selection.tool.name, selection.tool)
    app_state.channel_registry = dependencies.channel_registry
    app_state.model_registry = dependencies.model_registry
    app_state.tool_registry = dependencies.tool_registry
    app_state.registries_ready = True
    logger.info(
        "registries_initialized",
        channels=app_state.channel_registry.list_all(),
        models=app_state.model_registry.list_all(),
        tools=app_state.tool_registry.list_all(),
    )


def _release_registries(app_state: AppState) -> None:
    app_state.registries_ready = False
    app_state.channel_registry = None
    app_state.model_registry = None
    app_state.tool_registry = None
    logger.info("registries_released")


def _initialize_telemetry(app_state: AppState) -> None:
    dependencies = app_state.dependencies
    if dependencies is None:
        raise CompositionError("Telemetry cannot initialize without composed dependencies")
    settings = dependencies.settings
    metrics.reset()
    telemetry_state = telemetry.configure(
        TelemetryConfig(
            enabled=settings.telemetry_enabled,
            endpoint=settings.telemetry_endpoint,
            metrics_endpoint=settings.telemetry_metrics_endpoint,
            service_version="0.1.0",
            environment=settings.environment.value,
            sample_ratio=settings.telemetry_sample_ratio,
            auth_token=_telemetry_auth_token(settings),
        )
    )
    metrics_active = False
    if telemetry_state.active and telemetry_state.metrics_active:
        metrics_active = metrics.configure(meter_provider=telemetry_state.meter_provider)
    logger.info(
        "telemetry_configured",
        active=telemetry_state.active,
        reason=telemetry_state.reason,
        metrics_active=metrics_active,
        metrics_reason=telemetry_state.metrics_reason,
    )


def _telemetry_auth_token(settings: Settings) -> str | None:
    token = settings.telemetry_auth_token
    return token.get_secret_value() if token is not None else None


async def _shutdown_observability() -> None:  # noqa: RUF029
    telemetry.shutdown()
    metrics.reset()
    logger.info("observability_shutdown_complete")


def register_application_components(
    lifecycle: ApplicationLifecycle,
    app_state: AppState,
    supervisor: BackgroundTaskSupervisor,
    root: CompositionRoot,
) -> None:
    """Register the application component graph with the Stage 16 lifecycle."""
    lifecycle.register(
        LifecycleComponent(
            name="configuration",
            initialize=lambda: _initialize_configuration(root.settings),
            description="Validated settings already loaded; logs non-secret identity",
        )
    )
    lifecycle.register(
        LifecycleComponent(
            name="composition",
            initialize=lambda: _compose(app_state, lifecycle, supervisor, root),
            release=lambda: _release_composition(app_state),
            depends_on=("configuration",),
            description="Builds the typed application dependency bundle",
        )
    )
    lifecycle.register(
        LifecycleComponent(
            name="registries",
            initialize=lambda: _initialize_registries(app_state),
            release=lambda: _release_registries(app_state),
            depends_on=("composition",),
            description="Registers the composition root's selected adapters",
        )
    )
    lifecycle.register(
        LifecycleComponent(
            name="telemetry",
            initialize=lambda: _initialize_telemetry(app_state),
            mandatory=False,
            depends_on=("composition",),
            description="Optional OpenTelemetry export; degradation never blocks startup",
        )
    )
    lifecycle.set_observability_cleanup(_shutdown_observability)
