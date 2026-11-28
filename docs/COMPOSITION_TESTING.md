# Composition Testing (Stage 18)

---

## 1. Required categories

| Category | What it proves |
|---|---|
| Construction | Components receive the correct objects |
| Interface | Selected adapters satisfy their Protocols |
| Isolation | Separate apps do not share application-scope state |
| Override | Tests substitute registries/adapters without globals |
| Lifetime | Longer-lived providers cannot depend on shorter ones |
| Cleanup | Lifecycle releases registries exactly once |
| Circular dependency | Cycles are rejected with a path |
| Missing dependency | Incomplete graphs cannot assemble |
| Concurrency | Concurrent builds do not share app-scope instances |
| Failure injection | Failed composition cannot expose partial state |
| Static architecture | Inner packages cannot import composition/adapters |

## 2. Graph invariants

Tests assert:

- duplicate provider types and names are rejected;
- missing providers are rejected with the requiring provider;
- self-cycles and multi-node cycles are rejected;
- a process provider cannot depend on application/request;
- an application provider cannot depend on request/operation;
- request/operation providers cannot be built in application scope;
- overrides replace values without calling the factory;
- unknown overrides are rejected;
- builds are dependency-first and one instance per provider per build;
- a factory failure propagates and returns no bundle;
- concurrent builds produce distinct application-scope instances.

## 3. Application composition invariants

- Production startup never calls `register_defaults()`.
- The composition root selects channel/model/tool adapters.
- The registries receive the selected adapter instances.
- Two `create_app()` instances own separate dependency bundles and registries.
- Composition failure rolls back startup and leaves no dependencies in state.
- `AppState.reset()` clears registries, readiness and dependencies.
- Component registration is the single four-component application graph:
  configuration → composition → registries → telemetry (optional).

## 4. Static enforcement

- Import-linter contract 7: inner packages cannot import `waxprep.composition`.
- Import-linter contract 8: composition cannot import `waxprep.main`.
- `tests/architecture/test_composition_concrete.py`: concrete adapters may be
  imported only by composition, legacy registries and adapters themselves.
- The same test rejects module-level `DependencyGraph()`/`CompositionRoot()`
  instances (service-locator/global state).
- Semgrep rule `waxprep-concrete-adapter-import` enforces the adapter boundary.
- Each structural check has an adversarial synthetic case proving it fires.

## 5. Running

```bash
# Graph/unit-level composition tests
uv run pytest tests/unit/test_composition_graph.py -v -m unit

# Application composition integration
uv run pytest tests/integration/test_composition_root.py -v -m integration

# Architecture boundaries
uv run pytest tests/architecture -v -m architecture

# Full gate
make check
```

## 6. Coverage is not proof

100% line coverage is required, but the acceptance evidence is the invariants
above: lifetime rejection, cycle/missing detection, isolation, overrides,
failure rollback and structural enforcement. A green suite with a global
container would not satisfy Stage 18.
