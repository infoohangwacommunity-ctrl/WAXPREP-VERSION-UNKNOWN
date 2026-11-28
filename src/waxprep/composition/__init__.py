"""Dependency injection and composition (Stage 18).

Explicit typed composition first:

* one authoritative composition root;
* typed providers and dependency graph;
* constructor/factory injection;
* lifetime validation;
* typed application bundles;
* integration with the Stage 16 lifecycle.

No global service locator, third-party IoC container, transport or product
component is introduced.
"""

from waxprep.composition.application import register_application_components
from waxprep.composition.bundles import (
    AdapterSelection,
    ApplicationDependencies,
    WorkerDependencies,
)
from waxprep.composition.errors import (
    CircularDependencyError,
    CompositionError,
    DuplicateProviderError,
    LifetimeViolationError,
    MissingDependencyError,
    ScopeError,
)
from waxprep.composition.graph import DependencyGraph, ProviderSpec
from waxprep.composition.lifetimes import Lifetime, is_compatible
from waxprep.composition.root import CompositionRoot
from waxprep.composition.state import AppState

__all__ = [
    "AdapterSelection",
    "AppState",
    "ApplicationDependencies",
    "WorkerDependencies",
    "CircularDependencyError",
    "CompositionError",
    "CompositionRoot",
    "DependencyGraph",
    "DuplicateProviderError",
    "Lifetime",
    "LifetimeViolationError",
    "MissingDependencyError",
    "ProviderSpec",
    "ScopeError",
    "is_compatible",
    "register_application_components",
]
