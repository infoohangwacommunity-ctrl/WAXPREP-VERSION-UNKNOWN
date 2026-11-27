"""Observability: logging, telemetry, and metrics (Stages 13-14).

Infrastructure-facing package. It may import the standard library and the
OpenTelemetry SDK, but it must never be imported by ``core/``.

NOTE: the process-wide singletons are deliberately *not* re-exported here.
Exporting an object named ``metrics``/``telemetry`` from a package that also
contains ``metrics.py``/``telemetry.py`` shadows the submodule, so
``from waxprep.observability import metrics`` would silently return the instance
instead of the module. Import them from their defining module instead:

    from waxprep.observability.metrics import metrics
    from waxprep.observability.telemetry import telemetry
"""

from waxprep.observability.logging import configure_logging, is_configured
from waxprep.observability.metrics import Metrics, null_instrument
from waxprep.observability.telemetry import (
    Telemetry,
    TelemetryConfig,
    TelemetryState,
    normalize_method,
    route_template,
    status_class,
)

__all__ = [
    "Metrics",
    "Telemetry",
    "TelemetryConfig",
    "TelemetryState",
    "configure_logging",
    "is_configured",
    "normalize_method",
    "null_instrument",
    "route_template",
    "status_class",
]
