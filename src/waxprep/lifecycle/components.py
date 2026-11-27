"""Lifecycle component contract (Stage 16).

A component answers the four ownership questions explicitly:

* **Who creates it?** The component's ``initialize`` callable, invoked once per
  lifecycle execution by the application composition root.
* **Who owns it?** The named component (the owner identity).
* **Who uses it?** Application code that receives the initialized value; the
  manager does not expose resources to unrelated components implicitly.
* **Who releases it?** The component's ``release`` callable, registered with the
  lifecycle manager immediately after successful initialization. Cleanup runs in
  reverse acquisition order.

Components that are pure and own nothing may omit ``release``. Components that
need several resources should either return one owned bundle and release it in
``release``, or register them as separate components with explicit dependencies.
A component that fails during ``initialize`` must release any resources it
acquired before failing; the manager only registers cleanup after success.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class LifecycleComponent:
    """Declarative description of one initialization unit.

    Args:
        name: Unique, bounded owner identity (used in logs and the report).
        initialize: Sync or async callable that acquires the component.
        release: Sync or async callable that releases everything acquired.
        mandatory: ``True`` means a failure aborts startup and rolls back.
            ``False`` means the failure is recorded and startup continues.
        depends_on: Components that must be registered (and therefore earlier in
            the explicit initialization order) before this one.
        description: Human-readable purpose; never contains secrets.
    """

    name: str
    initialize: Callable[[], Any] | None = None
    release: Callable[[], Any] | None = None
    mandatory: bool = True
    depends_on: tuple[str, ...] = ()
    description: str = field(default="")

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("component name must be non-empty")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError(f"component {self.name!r} declares duplicate dependencies")
        if self.name in self.depends_on:
            raise ValueError(f"component {self.name!r} cannot depend on itself")
