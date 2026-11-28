# Stage 18 Implementation Report — Dependency Injection and Composition

**Base:** `6ef9085` (main).
**Scope:** explicit typed composition, provider graph, lifetimes, typed bundles,
registry implementation selection and Stage 16 integration.
**Not implemented:** product components, transports, infrastructure, IoC framework.

---

## 1. What was implemented

| Area | Result |
|---|---|
| Composition root | `CompositionRoot` is the only production assembly/selection point |
| Typed graph | `ProviderSpec`/`DependencyGraph` with missing/cycle/lifetime checks |
| Injection | Constructor/factory values in declared dependency order |
| Bundles | `AdapterSelection`, immutable `ApplicationDependencies` |
| Lifetimes | PROCESS/APPLICATION/REQUEST/OPERATION policy and compatibility |
| Lifecycle | `configuration -> composition -> registries -> telemetry` via Stage 16 |
| Registries | Production path registers adapters selected by composition |
| Overrides | Explicit per-build values for tests; no global monkey-patching |
| Static enforcement | import-linter, AST boundaries, Semgrep concrete-adapter rule |
| Docs | architecture, testing and this report |

## 2. Decisions and answers

- **Manual composition vs third-party container:** explicit typed composition.
  Dishka/Dependency Injector remain evaluated future options only; no dependency
  is added.
- **What is the composition root?** `waxprep.composition.CompositionRoot`; it
  selects concrete implementations, validates the graph and returns the typed
  bundle. It contains no business logic.
- **How is the graph represented?** Typed `ProviderSpec` nodes keyed by Python
  type, with factories, declared dependencies and lifetimes. Not a string-keyed
  dictionary.
- **Constructor or factory injection?** Both: graph factories construct values;
  components receive dependencies as constructor arguments. Components never
  look up a container.
- **Application vs process lifetime?** Settings are PROCESS; registries,
  selected adapters, lifecycle and supervisor are APPLICATION; request/operation
  are validated future scopes. Longer-lived providers cannot depend on shorter
  ones.
- **Lifecycle ownership?** Stage 16 remains authoritative. Composition runs as a
  mandatory component; registries register selected adapters; telemetry uses the
  assembled settings; release is reverse-order and failure-isolated.
- **Registries and implementation selection?** The composition root selects
  adapters. Registries keep registration/lookup. `register_defaults()` is legacy
  convenience only; production startup is tested to never call it.
- **Test overrides?** `CompositionRoot(..., overrides={Type: value})` and explicit
  `AdapterSelection`; no global container.
- **Cycle detection?** DFS with path diagnostics; missing providers report the
  requiring provider.
- **Static enforcement?** Import-linter contracts 7/8, AST adapter/global checks
  and Semgrep `waxprep-concrete-adapter-import`; each has adversarial tests.
- **FastAPI dependence?** FastAPI remains an HTTP boundary. Docker-independent
  bundles let future workers receive dependencies from the same composition root
  without adopting FastAPI DI.
- **Future workers?** They can call the same composition root and receive a
  purpose-specific typed bundle; no second application architecture is required.

## 3. Added files

```
src/waxprep/composition/__init__.py
src/waxprep/composition/application.py
src/waxprep/composition/bundles.py
src/waxprep/composition/errors.py
src/waxprep/composition/graph.py
src/waxprep/composition/lifetimes.py
src/waxprep/composition/root.py
src/waxprep/composition/state.py
tests/unit/test_composition_graph.py
tests/integration/test_composition_root.py
tests/architecture/test_composition_concrete.py
docs/DEPENDENCY_INJECTION_AND_COMPOSITION.md
docs/COMPOSITION_TESTING.md
docs/STAGE_18_IMPLEMENTATION_REPORT.md
```

**Modified**

```
src/waxprep/main.py                thin entrypoint; delegates assembly to composition
src/waxprep/registries/*.py        legacy default selector documented
.importlinter                      composition isolation contracts 7/8
.semgrep/config.yml                concrete-adapter import rule
tests/architecture/test_boundaries.py  composition boundary rules
tests/integration/test_final_coverage.py  readiness fixture no longer patches register_defaults
tests/lifecycle/test_lifecycle.py  four-component graph expectations
README.md, docs/ARCHITECTURE_BOUNDARIES.md,
docs/ENGINEERING-STANDARDS.md, docs/PR_REVIEW_CHECKLIST.md,
tests/README.md, pyproject.toml
```

## 4. Tests added

- Provider validation: type/factory/duplicate deps/empty name.
- Graph: duplicates, names, missing dependency, self/multi-node cycles,
  lifetime violations, valid lifetimes, dependency order, overrides, unknown
  overrides, scope rejection, factory failure, concurrent builds.
- Composition root: default typed bundle, fresh app-scope instances, explicit
  adapter selection, registry overrides, invalid adapter selection, settings
  property.
- Application: production startup does not call `register_defaults`, composition
  override, two-app isolation, composition failure rollback, state reset,
  four-component registration, missing-dependency error paths.
- Static: concrete adapter imports, global graph/service-locator instances,
  adversarial synthetic cases, import-linter boundaries.

## 5. Local results

| Gate | Result |
|---|---|
| ruff / format | PASS |
| mypy strict | PASS (82 files) |
| import-linter | 7 contracts kept |
| contract drift + compatibility | PASS |
| Semgrep (13 rules) | 0 findings |
| hardcoding detector | 0 blocking |
| supply chain | PASSED |
| workflow audit | PASSED |
| pytest | **1342 passed, 1 skipped, 9 xfailed** |
| coverage | **100.00%** (5,120 statements, 0 missed) |

## 6. Limitations / deferred

- Request/operation lifetimes are policy and validation only; no request-scoped
  product component exists. A real request scope will be added with the first
  such component.
- Factories are synchronous constructors. Asynchronous resource initialization
  remains Stage 16's component lifecycle, avoiding two competing async managers.
- No third-party IoC container; Dishka/Dependency Injector remain future options.
- No dynamic plugin discovery, service locator, transport, database, Redis,
  worker or product component was introduced.
- `register_defaults()` remains as legacy convenience; production code is
  enforced not to call it, but the method is not removed to avoid breaking the
  foundation tests/embedding code in this stage.

## 7. CI evidence

Recorded after the final push (exact commit-bound runs).
