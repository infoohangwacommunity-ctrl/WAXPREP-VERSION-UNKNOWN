"""Background execution infrastructure (Stage 19).

Responsibilities:

* application-facing submission boundary (``BackgroundRuntime``);
* open-world typed job handler registration and dispatch (``JobRegistry``);
* Taskiq adapter (``waxprep.background.taskiq`` — optional extra);
* independent worker entrypoint (``waxprep.background.worker``);
* typed background failures (``waxprep.background.errors``).

No product jobs, scheduler, custom queue, broker or retry engine is implemented.
"""

from waxprep.background.errors import (
    BackgroundError,
    BackgroundUnavailableError,
    JobExecutionError,
    JobRegistrationError,
    JobSubmissionError,
    JobValidationError,
)
from waxprep.background.registry import JobHandler, JobRegistry
from waxprep.background.runtime import BackgroundRuntime, UnavailableBackgroundRuntime

__all__ = [
    "BackgroundError",
    "BackgroundRuntime",
    "BackgroundUnavailableError",
    "JobExecutionError",
    "JobHandler",
    "JobRegistrationError",
    "JobRegistry",
    "JobSubmissionError",
    "JobValidationError",
    "UnavailableBackgroundRuntime",
]
