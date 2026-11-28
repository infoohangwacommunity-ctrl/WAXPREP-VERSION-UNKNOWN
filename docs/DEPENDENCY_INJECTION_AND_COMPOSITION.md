# Dependency Injection and Composition (Stage 18)

**Owner:** application assembly, typed dependency graph, lifetimes, composition
root, constructor/factory injection and lifecycle integration.
**Does not cover:** product components (Tutor, Judge, Notebook, Context
Intelligence), transports, database/Redis infrastructure, or a third-party IoC
container.

---

## 1. The problem

A component must not construct its own infrastructure. If Tutor creates an OpenAI
client, a database pool and Context Intelligence itself, changing a provider or
testing without paid services means editing Tutor. Dependencies must be supplied
from outside.

Five concepts are kept distinct:

| Concept | Responsibility |
|---|---|
| Dependency injection | Supply required dependencies |
| Composition | Assemble components into an application |
| Composition root | The one place assembly happens |
| Factory | Create an object and its dependencies |
| IoC container | A generic manager of construction/resolution |

WaxPrep chooses **explicit, typed composition** for Stage 18. No third-party
container, no global service locator, no plugin discovery. The composition root
is a small local resolver/assembler, not a service locator exposed to components.

## 2. One authoritative composition root

`src/waxprep/composition/root.py` — `CompositionRoot` is the only production
location that selects concrete implementations and builds the application graph.

It:

- receives validated `Settings`;
- selects concrete adapters (`AdapterSelection`);
- registers typed providers;
- validates missing dependencies, cycles and lifetimes;
- builds the application bundle;
- does not process messages, contain business rules, or expose a global lookup.

`main.py` is a thin ASGI entrypoint: it creates the composition root, registers
the application components with Stage 16, attaches routes/handlers and serves.
Assembly is no longer scattered across lifecycle callbacks.

## 3. Typed dependency graph

`src/waxprep/composition/graph.py` — `DependencyGraph` + `ProviderSpec`.

A provider declares:

```python
ProviderSpec(
    provides=ChannelRegistry,
    factory=ChannelRegistry,
    dependencies=(),
    lifetime=Lifetime.APPLICATION,
    name="channel-registry",
)
```

The graph provides:

- duplicate provider/name detection;
- missing-provider detection with the requiring provider;
- cycle detection with the path;
- factory signature validation (declared dependency count vs accepted
  positional/required keyword-only parameters) at registration, so a mismatch
  fails before startup;
- dependency-first topological construction;
- lifetime validation;
- one instance per provider per build;
- explicit per-build overrides for tests;
- a scope check so request/operation providers cannot leak into application
  scope.

It is used only inside `CompositionRoot.build()`. Components never call it; they
receive values through constructors/factories.

## 4. Typed bundles, not dictionaries

`src/waxprep/composition/bundles.py`:

- `AdapterSelection` — the concrete channel/model/tool implementations selected
  by composition.
- `ApplicationDependencies` — immutable application-scope bundle:
  `settings`, channel/model/tool registries, selected adapters, lifecycle,
  background supervisor.

There is no `dict[str, Any]` container and no enormous universal
`ApplicationContainer`. A future HTTP or worker boundary receives a
purpose-specific bundle; request-specific bundles can be added when a real
request component exists.

**Immutability is shallow.** `frozen=True` prevents replacing bundle fields. The
contained registries, lifecycle manager, supervisor and adapters are
application-owned objects with their own mutability/lifetime rules. The bundle
is a reference list, not a deep copy or a second ownership system.

## 5. Lifetimes

`src/waxprep/composition/lifetimes.py`:

| Lifetime | Meaning |
|---|---|
| `PROCESS` | Genuinely process-wide, explicitly documented ownership |
| `APPLICATION` | One independently constructed application instance |
| `REQUEST` | One incoming request/message (policy only today) |
| `OPERATION` | One short operation (policy only today) |

A consumer may depend on the same or a **longer** lifetime, never a shorter one.
An application singleton cannot retain a request-scoped object. Violations are
rejected during graph validation.

Request/operation scopes are validated policy, not implemented product scopes.
No request-scoped component exists yet; inventing one just to demonstrate a
scope would violate the Stage 18 boundary.

**Future extension rule:** use a separate graph or composition entrypoint per
scope. An application graph must not register request/operation providers; the
current graph rejects any provider longer than the requested scope, even if
unrelated. A future request graph may include application-scoped values as
already-built overrides or providers. Extend this graph with explicit scope
entrypoints when the first real request-scoped component arrives; do not add a
second DI mechanism. Regression tests pin this policy now.

## 6. Lifecycle integration (Stage 16 remains authoritative)

`src/waxprep/composition/application.py` connects composition to the existing
lifecycle components:

| Order | Component | Lifetime owner | Responsibility |
|---|---|---|---|
| 1 | `configuration` | application | Log validated non-secret identity |
| 2 | `composition` | application | Build the typed dependency bundle |
| 3 | `registries` | application | Register selected adapters |
| 4 | `telemetry` (optional) | process/application | Configure observability |

Stage 16 still owns:

- ordering and dependency validation;
- startup rollback;
- reverse-order cleanup;
- failure isolation and cancellation;
- background-task supervision;
- application-instance isolation.

Stage 18 does not create a second lifecycle manager. If composition fails, the
lifecycle rollback releases whatever was acquired; no partial graph is exposed.

## 7. Registries no longer select implementations

Production startup no longer calls `ChannelRegistry.register_defaults()` /
`ModelRegistry.register_defaults()` / `ToolRegistry.register_defaults()`.

The composition root selects the concrete adapters and the `registries`
lifecycle component calls `register(name, instance)`. Registries keep their
existing registration/lookup/validation contract.

`register_defaults()` remains as a documented legacy convenience for foundation
tests and older embedding code. It is not the production selection path.

## 8. Constructor and factory injection

- Components receive dependencies through explicit constructor parameters or a
  typed factory; they do not fetch them from a global.
- The graph calls sync factories with dependency values in declared order.
- Asynchronous resource initialization/release is Stage 16's component
  lifecycle, not a second async DI mechanism.
- Test overrides are explicit values passed to `CompositionRoot(...,
  overrides={Type: value})`; no monkey-patched global container.

Example future (not implemented) component:

```python
class TutorService:
    def __init__(self, models: ModelAdapter, context: ContextProvider) -> None: ...
```

Composition constructs `TutorService` with the selected implementations. Tutor
does not import a provider SDK or a container.

## 9. FastAPI boundary

FastAPI's dependency system is used only at the HTTP boundary where appropriate.
It is **not** the universal composition mechanism. The application bundle is
assembled before HTTP concerns and attached to the app instance; future
background workers can receive their own typed bundle from the same composition
root instead of becoming FastAPI-dependent.

## 10. No global service locator

Forbidden by architecture:

- a module-level dependency container used by components;
- string-keyed lookup of services;
- components importing the composition package;
- concrete adapters imported outside composition/legacy registries.

Import-linter contracts 7 and 8, an AST architecture test and Semgrep rule
`waxprep-concrete-adapter-import` enforce the boundary. Synthetic violations are
tested so the checks cannot silently become weak.

## 11. File map

```
src/waxprep/composition/
├── __init__.py        public exports
├── application.py     Stage 16 component wiring
├── bundles.py         AdapterSelection, ApplicationDependencies
├── errors.py          typed composition failures (WAX-6000..6005)
├── graph.py           ProviderSpec, DependencyGraph
├── lifetimes.py       Lifetime policy
├── root.py            CompositionRoot
└── state.py           per-application mutable state
```

## 12. Deliberately excluded

Tutor, Context Intelligence, Judge, Student Notebook, real model providers,
databases, Redis, Telegram/WhatsApp processing, production workers, event
brokers, message pipelines, a global service locator, a second lifecycle manager,
plugin discovery, dynamic loading and a third-party IoC container.
