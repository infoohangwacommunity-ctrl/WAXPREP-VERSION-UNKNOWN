# ADR 0001: Hexagonal Architecture with Modular Monolith

## Status
Accepted - Stage 03

## Context

As WaxPrep grows from a simple foundation to a full-featured learning companion,
we need an architecture that:

1. **Enforces clear boundaries** between domain logic, application services, and external integrations
2. **Prevents tight coupling** that makes the codebase difficult to maintain and test
3. **Allows easy testing** of components in isolation
4. **Supports multiple adapters** for different channels (WhatsApp, Telegram) and AI providers
5. **Scales** as new features are added

The initial Stages 01-02 implementation used a simple registry pattern but lacked
formal architectural boundaries. Without enforcement, cross-layer imports can
bypass facades, hiding dependency direction and making the codebase fragile.

## Decision

Adopt **Hexagonal Architecture (Ports and Adapters)** in a **modular monolith** deployment model.

### Architecture Layers

```
┌─────────────────────────────────────────────────────────┐
│                      main.py                              │
│                 (Composition Root)                       │
│  Only module that imports across all layers              │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Domain Layer                           │
│  Pure business logic - NO external imports               │
│  - Models (Student, Session, Message, LearningProfile)   │
│  - Value Objects                                          │
│  - Domain Exceptions                                     │
│  - Result types                                          │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                 Application Layer                         │
│  Use case orchestration + Port definitions                │
│  - Ports/Interfaces (ChannelPort, ModelPort, etc.)       │
│  - Use case handlers                                      │
│  - May import domain/                                     │
└─────────────────────────────────────────────────────────┘
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│   Adapters      │ │ Infrastructure  │ │   Registries    │
│  Implement ports│ │ Runtime concerns│ │ Registry pattern │
│  - WhatsApp     │ │ - Config        │ │ - ChannelReg    │
│  - Telegram     │ │ - Lifecycle     │ │ - ModelReg      │
│  - AI Providers │ │ - Logging       │ │ - ToolReg       │
│  - Tools        │ │ - DI            │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### Dependency Rules

1. **Domain Layer**: May only import stdlib and other domain modules
2. **Application Layer**: May import domain/ and application/
3. **Adapters**: May import domain/ and application/ports/
4. **Infrastructure**: May import domain/ and application/
5. **Registries**: May import domain/ and application/
6. **main.py**: May import ANY module (composition root)

### Enforcement

Import rules are enforced using a custom import linter (`scripts/lint_imports.py`) that:

1. **Layers Contract**: Enforces one-directional dependency rule
2. **Domain Purity Contract**: Prevents domain from importing external frameworks
3. **Adapter Isolation Contract**: Prevents adapters from depending on each other
4. **Composition-Root Protection**: Ensures only main.py imports across all layers
5. **No Cycles Contract**: Forbids circular dependencies

## Consequences

### Positive

1. **Clear Boundaries**: Each layer has a single, well-defined responsibility
2. **Testability**: Components can be tested in isolation with mocks
3. **Flexibility**: Adapters can be swapped without changing domain logic
4. **Maintainability**: Import contracts prevent accidental coupling
5. **Scalability**: New features can be added without affecting existing code

### Negative

1. **Learning Curve**: Team members need to understand hexagonal architecture
2. **Boilerplate**: More files and directories than a simple flat structure
3. **Indirection**: Some operations require going through multiple layers
4. **Tooling**: Need to maintain and run import linter in CI

### Trade-offs

- **Single Deployable**: Modular monolith deploys as one artifact (simpler than microservices)
- **Enforced Boundaries**: Import contracts catch violations at build time
- **Flexible Adapters**: Can support WhatsApp, Telegram, and multiple AI providers simultaneously

## Alternatives Considered

### 1. Clean Architecture (Uncle Bob)
**Rejected**: Similar to Hexagonal but with more layers (entities, use cases, interface adapters, framework).
For WaxPrep, Hexagonal's simpler layering is sufficient.

### 2. Layered Architecture (Traditional)
**Rejected**: Layers can be bypassed without tooling enforcement. Import contracts are harder to maintain.

### 3. Microservices
**Rejected**: Overkill for current scale. Adds operational complexity without clear benefit.
Modular monolith provides isolation without distributed system challenges.

### 4. No Formal Architecture
**Rejected**: Without enforced boundaries, the codebase will accumulate coupling debt.
The brief explicitly states: "cross-layer imports bypass __init__.py facades, hiding dependency direction"

## References

- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters Pattern](https://martinfowler.com/bliki/PortsAndAdapters.html)
- [Modular Monolith](https://www.kamilgrzybek.com/design/modular-monolith-architecture-in-asp-net-core/)
- [import-linter](https://github.com/sobolevn/import-linter)
