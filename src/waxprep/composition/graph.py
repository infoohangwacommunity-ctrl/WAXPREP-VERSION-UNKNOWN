"""Explicit typed dependency graph (Stage 18).

This is deliberately a small, local resolver owned by the composition root — not
a global service locator. Components never ask it for objects; the composition
root builds them once and passes them explicitly.

The graph provides the parts a manual composition needs to stay reliable:

* typed provider declarations (``provides`` is a Python type);
* dependency order and missing-provider detection;
* cycle detection with a diagnostic path;
* lifetime validation (a longer-lived provider cannot depend on a shorter one);
* duplicate provider/name detection;
* per-build overrides for tests;
* one instance per provider within a build.

Factories are synchronous constructors. Asynchronous resource initialization and
release remain Stage 16's responsibility.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from inspect import Parameter
from typing import Any

from waxprep.composition.errors import (
    CircularDependencyError,
    DuplicateProviderError,
    LifetimeViolationError,
    MissingDependencyError,
    ProviderSignatureError,
    ScopeError,
)
from waxprep.composition.lifetimes import Lifetime, is_compatible


def _validate_factory_signature(provider: ProviderSpec) -> None:
    """Reject a factory that cannot accept the declared dependency count.

    A factory is called positionally with one value per declared dependency.
    Required positional/keyword-only parameters that cannot be supplied, and
    extra declared dependencies that cannot be accepted, fail at registration
    instead of during application startup.
    """
    try:
        signature = inspect.signature(provider.factory)
    except TypeError, ValueError:
        # Some builtins/callables do not expose a signature. Construction still
        # fails loudly if they cannot accept the declared arguments.
        return
    parameters = list(signature.parameters.values())
    required_keyword_only = [
        parameter
        for parameter in parameters
        if parameter.kind is Parameter.KEYWORD_ONLY and parameter.default is Parameter.empty
    ]
    if required_keyword_only:
        names = ", ".join(parameter.name for parameter in required_keyword_only)
        raise ProviderSignatureError(
            "A provider factory requires unsupported keyword-only arguments",
            context={"provider": provider.label, "parameters": names},
        )
    positional = [
        parameter
        for parameter in parameters
        if parameter.kind in (Parameter.POSITIONAL_ONLY, Parameter.POSITIONAL_OR_KEYWORD)
    ]
    has_varargs = any(parameter.kind is Parameter.VAR_POSITIONAL for parameter in parameters)
    required_positional = [
        parameter for parameter in positional if parameter.default is Parameter.empty
    ]
    provided = len(provider.dependencies)
    if provided < len(required_positional):
        raise ProviderSignatureError(
            "A provider factory requires more positional arguments than declared dependencies",
            context={
                "provider": provider.label,
                "required": str(len(required_positional)),
                "declared": str(provided),
            },
        )
    if not has_varargs and provided > len(positional):
        raise ProviderSignatureError(
            "A provider factory accepts fewer positional arguments than declared dependencies",
            context={
                "provider": provider.label,
                "accepted": str(len(positional)),
                "declared": str(provided),
            },
        )


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """One typed dependency provider."""

    provides: type[Any]
    factory: Callable[..., Any]
    dependencies: tuple[type[Any], ...] = ()
    lifetime: Lifetime = Lifetime.APPLICATION
    name: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.provides, type):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("Provider 'provides' must be a type")
        if not callable(self.factory):
            raise TypeError("Provider factory must be callable")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("Provider dependencies must be unique")
        if self.name is not None and not self.name.strip():
            raise ValueError("Provider name must be non-empty when supplied")
        _validate_factory_signature(self)

    @property
    def label(self) -> str:
        return (
            self.name
            if self.name is not None
            else str(getattr(self.provides, "__name__", self.provides))
        )


class DependencyGraph:
    """Typed providers with validation and explicit construction."""

    def __init__(self) -> None:
        self._providers: dict[type[Any], ProviderSpec] = {}
        self._names: set[str] = set()

    @property
    def providers(self) -> tuple[ProviderSpec, ...]:
        return tuple(self._providers.values())

    def register(self, provider: ProviderSpec) -> None:
        if provider.provides in self._providers:
            raise DuplicateProviderError(
                "A provider for this dependency is already registered",
                context={"dependency": provider.provides.__name__},
            )
        if provider.name is not None and provider.name in self._names:
            raise DuplicateProviderError(
                "A provider with this name is already registered",
                context={"provider": provider.name},
            )
        self._providers[provider.provides] = provider
        if provider.name is not None:
            self._names.add(provider.name)

    def topological_order(self) -> tuple[ProviderSpec, ...]:
        """Return providers dependency-first, validating the whole graph."""
        state: dict[type[Any], int] = {}
        order: list[ProviderSpec] = []
        stack: list[type[Any]] = []

        def visit(dependency: type[Any]) -> None:
            provider = self._providers.get(dependency)
            if provider is None:
                parent = stack[-1].__name__ if stack else "<root>"
                raise MissingDependencyError(
                    "A required dependency has no provider",
                    context={"dependency": dependency.__name__, "required_by": parent},
                )
            current = state.get(dependency, 0)
            if current == 1:
                path = " -> ".join(item.__name__ for item in (*stack, dependency))
                raise CircularDependencyError(
                    "The dependency graph contains a cycle",
                    context={"path": path},
                )
            if current == 2:
                return
            state[dependency] = 1
            stack.append(dependency)
            for child in provider.dependencies:
                visit(child)
            stack.pop()
            state[dependency] = 2
            order.append(provider)

        for dependency in self._providers:
            visit(dependency)

        for provider in order:
            for child in provider.dependencies:
                child_provider = self._providers[child]
                if not is_compatible(provider.lifetime, child_provider.lifetime):
                    raise LifetimeViolationError(
                        "A dependency lifetime is shorter than its consumer",
                        context={
                            "provider": provider.label,
                            "provider_lifetime": str(provider.lifetime),
                            "dependency": child_provider.label,
                            "dependency_lifetime": str(child_provider.lifetime),
                        },
                    )
        return tuple(order)

    def build(
        self,
        *,
        scope: Lifetime = Lifetime.APPLICATION,
        overrides: Mapping[type[Any], Any] | None = None,
    ) -> dict[type[Any], Any]:
        """Resolve one instance per provider for the requested scope."""
        override_map = dict(overrides or {})
        unknown = [item.__name__ for item in override_map if item not in self._providers]
        if unknown:
            raise MissingDependencyError(
                "An override was supplied for an unregistered dependency",
                context={"dependencies": ",".join(unknown)},
            )
        for provider in self._providers.values():
            if provider.lifetime.rank > scope.rank:
                raise ScopeError(
                    "A provider is not available in the requested scope",
                    context={"provider": provider.label, "scope": str(scope)},
                )

        resolved: dict[type[Any], Any] = {}
        for provider in self.topological_order():
            if provider.provides in override_map:
                resolved[provider.provides] = override_map[provider.provides]
                continue
            arguments = [resolved[dependency] for dependency in provider.dependencies]
            resolved[provider.provides] = provider.factory(*arguments)
        return resolved
