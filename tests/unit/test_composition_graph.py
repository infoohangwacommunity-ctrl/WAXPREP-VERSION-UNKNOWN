"""Stage 18 — typed dependency graph validation and construction."""

from __future__ import annotations

import threading

import pytest

from waxprep.composition.errors import (
    CircularDependencyError,
    DuplicateProviderError,
    LifetimeViolationError,
    MissingDependencyError,
    ScopeError,
)
from waxprep.composition.graph import DependencyGraph, ProviderSpec
from waxprep.composition.lifetimes import Lifetime, is_compatible

pytestmark = pytest.mark.unit


class Settings:
    pass


class Repo:
    pass


class Service:
    def __init__(self, repo: Repo) -> None:
        self.repo = repo


class RequestObject:
    pass


def spec(provides, factory=None, *, dependencies=(), lifetime=Lifetime.APPLICATION, name=None):
    return ProviderSpec(
        provides=provides,
        factory=factory or provides,
        dependencies=dependencies,
        lifetime=lifetime,
        name=name,
    )


class TestProviderSpec:
    @pytest.mark.parametrize(
        "kwargs",
        [
            {"provides": "not-a-type", "factory": Settings},
            {"provides": Settings, "factory": 1},
            {"provides": Settings, "factory": Settings, "dependencies": (Repo, Repo)},
            {"provides": Settings, "factory": Settings, "name": "   "},
        ],
    )
    def test_invalid_provider_is_rejected(self, kwargs):
        with pytest.raises((TypeError, ValueError)):
            ProviderSpec(**kwargs)

    def test_label_uses_name_or_type(self):
        assert spec(Settings, name="settings").label == "settings"
        assert spec(Settings).label == "Settings"


class TestGraphValidation:
    def test_providers_are_exposed(self):
        graph = DependencyGraph()
        graph.register(spec(Settings))
        assert len(graph.providers) == 1

    def test_duplicate_dependency_provider_rejected(self):
        graph = DependencyGraph()
        graph.register(spec(Settings))
        with pytest.raises(DuplicateProviderError, match="already registered"):
            graph.register(spec(Settings))

    def test_duplicate_provider_name_rejected(self):
        graph = DependencyGraph()
        graph.register(spec(Settings, name="shared"))
        with pytest.raises(DuplicateProviderError, match="name"):
            graph.register(spec(Repo, name="shared"))

    def test_missing_dependency_rejected(self):
        graph = DependencyGraph()
        graph.register(spec(Service, dependencies=(Repo,)))
        with pytest.raises(MissingDependencyError, match="no provider"):
            graph.topological_order()

    def test_cycle_rejected_with_path(self):
        graph = DependencyGraph()
        graph.register(spec(Repo, dependencies=(Service,)))
        graph.register(spec(Service, dependencies=(Repo,)))
        with pytest.raises(CircularDependencyError, match="cycle") as raised:
            graph.topological_order()
        assert "Service" in raised.value.context["path"]

    def test_self_cycle_rejected(self):
        graph = DependencyGraph()
        graph.register(spec(Repo, dependencies=(Repo,)))
        with pytest.raises(CircularDependencyError):
            graph.topological_order()

    def test_lifetime_violation_rejected(self):
        graph = DependencyGraph()
        graph.register(spec(RequestObject, lifetime=Lifetime.REQUEST))
        graph.register(spec(Service, dependencies=(RequestObject,), lifetime=Lifetime.APPLICATION))
        with pytest.raises(LifetimeViolationError, match="shorter"):
            graph.topological_order()

    def test_valid_lifetimes(self):
        assert is_compatible(Lifetime.REQUEST, Lifetime.APPLICATION) is True
        assert is_compatible(Lifetime.APPLICATION, Lifetime.REQUEST) is False
        graph = DependencyGraph()
        graph.register(spec(Settings, lifetime=Lifetime.PROCESS))
        graph.register(spec(Service, dependencies=(Settings,)))
        assert [item.provides for item in graph.topological_order()] == [Settings, Service]


class TestGraphBuild:
    def test_builds_dependency_first_and_reuses_instances(self):
        graph = DependencyGraph()
        graph.register(spec(Repo))
        graph.register(spec(Service, dependencies=(Repo,)))
        resolved = graph.build()
        assert isinstance(resolved[Repo], Repo)
        assert isinstance(resolved[Service], Service)
        assert resolved[Service].repo is resolved[Repo]

    def test_overrides_substitute_values(self):
        graph = DependencyGraph()
        graph.register(spec(Repo))
        graph.register(spec(Service, dependencies=(Repo,)))
        fake = Repo()
        resolved = graph.build(overrides={Repo: fake})
        assert resolved[Repo] is fake
        assert resolved[Service].repo is fake

    def test_override_for_unknown_dependency_is_rejected(self):
        graph = DependencyGraph()
        graph.register(spec(Repo))
        with pytest.raises(MissingDependencyError, match="unregistered"):
            graph.build(overrides={Settings: Settings()})

    def test_request_scope_is_not_available_in_application_scope(self):
        graph = DependencyGraph()
        graph.register(spec(RequestObject, lifetime=Lifetime.REQUEST))
        with pytest.raises(ScopeError, match="requested scope"):
            graph.build()

    def test_factory_failure_propagates(self):
        def explode() -> Repo:
            raise RuntimeError("factory failed")

        graph = DependencyGraph()
        graph.register(spec(Repo, explode))
        with pytest.raises(RuntimeError, match="factory failed"):
            graph.build()

    def test_concurrent_builds_do_not_share_instances(self):
        graph = DependencyGraph()
        graph.register(spec(Repo))
        barriers = threading.Barrier(2)
        results: list[dict[type, object]] = []

        def build() -> None:
            barriers.wait()
            results.append(graph.build())

        threads = [threading.Thread(target=build) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert len(results) == 2
        assert results[0][Repo] is not results[1][Repo]
