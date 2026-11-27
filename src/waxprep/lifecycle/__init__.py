"""Application lifecycle management (Stage 16).

One explicit lifecycle per application instance:

* a single authoritative state machine (``LifecycleState``),
* an ordered, dependency-aware component registry,
* reverse-order cleanup through ``AsyncExitStack``,
* failure-isolated cleanup that preserves the original startup exception,
* cancellation-aware transitions,
* owned background-task supervision, and
* lifecycle-aware readiness.

Nothing in this package starts a task, opens a connection or configures a
provider at import time. All acquisition is explicit in ``ApplicationLifecycle``
``start()``; all release is explicit in ``shutdown()``.
"""

from waxprep.lifecycle.background import (
    BackgroundTaskSupervisor,
    TaskOutcome,
    TaskResult,
    TaskSupervisorError,
)
from waxprep.lifecycle.components import LifecycleComponent
from waxprep.lifecycle.errors import (
    LifecycleError,
    LifecycleTransitionError,
    ResourceOwnershipError,
)
from waxprep.lifecycle.manager import ApplicationLifecycle
from waxprep.lifecycle.report import (
    CleanupStatus,
    ComponentResult,
    LifecycleReport,
    OperationOutcome,
)
from waxprep.lifecycle.states import LifecycleState, LifecycleStateMachine
from waxprep.lifecycle.timeouts import LifecycleTimeouts

__all__ = [
    "ApplicationLifecycle",
    "BackgroundTaskSupervisor",
    "CleanupStatus",
    "ComponentResult",
    "LifecycleComponent",
    "LifecycleError",
    "LifecycleReport",
    "LifecycleState",
    "LifecycleStateMachine",
    "LifecycleTimeouts",
    "LifecycleTransitionError",
    "OperationOutcome",
    "ResourceOwnershipError",
    "TaskOutcome",
    "TaskResult",
    "TaskSupervisorError",
]
