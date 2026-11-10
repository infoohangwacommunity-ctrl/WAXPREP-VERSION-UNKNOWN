# WaxPrep Foundation - Stages 01-07

## Overview

This repository contains the **WaxPrep Foundation** - the architectural and engineering foundation for the WaxPrep AI learning companion project.

**Current Version**: 0.4.0 (Stages 01-07 Complete)

## What is WaxPrep?

WaxPrep is an **AI-powered learning companion** designed to help students learn, understand, practice, and develop genuine knowledge through everyday messaging platforms (WhatsApp, Telegram).

### Core Philosophy

> "WaxPrep isn't supposed to be an AI that students learn how to use. It's supposed to be an AI that learns how to understand its students."

- **Personalized**: Understands each student's strengths, weaknesses, and learning style
- **Accessible**: Available through familiar messaging platforms
- **Comfortable**: Natural, friendly, approachable communication
- **Interactive**: Encourages active learning through questions, examples, and practice
- **Genuine**: Focuses on understanding, not just providing answers

## Architecture

### Hexagonal Architecture (Ports and Adapters)

```
┌─────────────────────────────────────────────────────────────┐
│                      main.py                              │
│                 (Composition Root)                       │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                           │
│  Pure business logic - NO external imports               │
│  - Models (Result types)                                  │
│  - Value Objects                                          │
│  - Domain Exceptions                                     │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 Application Layer                         │
│  Use case orchestration + Port definitions                │
│  - Ports/Interfaces (ChannelPort, ModelPort, ToolPort)    │
│  - Use case handlers                                      │
└─────────────────────────────────────────────────────────────┘
                           │
            ┌──────────────┴──────────────┬──────────────┐
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
5. **main.py**: May import ANY module (composition root)

### Enforcement

Import rules are enforced using a custom import linter (`scripts/lint_imports.py`) that runs in CI.

## Project Structure

```
waxprep-version-unknown/
├── src/
│   └── waxprep/
│       ├── domain/              # Pure domain models
│       │   └── models/          # Result types
│       │
│       ├── application/         # Application layer
│       │   └── ports/           # Port interfaces (ChannelPort, ModelPort, ToolPort)
│       │
│       ├── adapters/            # Port implementations
│       │   ├── fake_channel.py  # Fake implementations for testing
│       │   ├── fake_model.py
│       │   └── fake_tool.py
│       │
│       ├── infrastructure/      # Runtime concerns
│       │   ├── config.py        # Configuration management
│       │   ├── logging.py       # Structured logging
│       │   ├── lifecycle.py     # Application lifecycle
│       │   └── di.py            # Dependency injection
│       │
│       └── registries/           # Registry pattern
│           ├── base.py
│           ├── channel.py
│           ├── model.py
│           └── tool.py
│
│       └── main.py              # Composition root
│
├── tests/
│   ├── unit/                   # Unit tests for domain logic
│   ├── contract/                # Contract tests for port implementations
│   ├── integration/             # Integration tests for application lifecycle
│   ├── regression/              # Regression tests for known failures
│   └── architecture/            # Architectural fitness tests
│
├── docs/
│   ├── DEFINITION_OF_DONE.md   # Component acceptance criteria
│   └── adr/                    # Architecture Decision Records
│       ├── 0001-hexagonal-architecture.md
│       └── 0002-error-handling-convention.md
│
├── scripts/
│   └── lint_imports.py         # Custom import linter
│
├── .github/
│   └── workflows/
│       └── quality-gate.yml    # CI quality gate
│
├── .pre-commit-config.yaml     # Pre-commit hooks
├── pyproject.toml              # Project configuration
└── README.md
```

## Stages Completed

### Stage 01: Foundation
- ✅ Python 3.14+ environment
- ✅ uv package manager
- ✅ FastAPI + Uvicorn ASGI
- ✅ Pydantic v2 for settings
- ✅ Structured logging with structlog

### Stage 02: Registries & Lifecycle
- ✅ Registry pattern for adapters
- ✅ Graceful shutdown handler
- ✅ Health endpoints (liveness, readiness)
- ✅ No hardcoded values in config
- ✅ Basic test structure

### Stage 03: Hexagonal Architecture
- ✅ Domain models (Result types)
- ✅ Value objects (Timestamp)
- ✅ Result types for functional error handling
- ✅ Domain exceptions hierarchy
- ✅ Port interfaces (ChannelPort, ModelPort, ToolPort)
- ✅ Infrastructure modules (config, logging, lifecycle, DI)
- ✅ Composition root (main.py)
- ✅ Import linter with all contracts
- ✅ Architectural fitness tests

### Stage 04: Engineering Standards
- ✅ Ruff configuration with full rule set (E, F, W, I, N, UP, S, B, A, C4, SIM, TCH, RUF)
- ✅ Pyright strict mode
- ✅ Definition of Done document
- ✅ ADRs for architectural decisions
- ✅ Pre-commit hooks

### Stage 05: Automated Testing Foundation
- ✅ pytest configuration with plugins
- ✅ Test layer structure (unit, contract, integration, regression, architecture)
- ✅ Unit tests for domain models
- ✅ Contract tests for ports
- ✅ Regression tests for known failures
- ✅ Integration tests for lifecycle
- ✅ CI workflow with quality gate
- ✅ Coverage configuration with fail_under threshold

## Running the Application

```bash
# Install dependencies
uv sync

# Run the application
uv run uvicorn waxprep.main:app --reload

# Or use the main module directly
uv run python -m waxprep.main

# The application will be available at http://localhost:8000
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src/waxprep --cov-report=term

# Run tests in random order
pytest tests/ -p pytest_randomly

# Run tests in parallel
pytest tests/ -n auto

# Run specific test layer
pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v
pytest tests/regression/ -v
pytest tests/architecture/ -v
```

## Quality Checks

```bash
# Run import linter
python scripts/lint_imports.py

# Run ruff linter
ruff check src/waxprep tests

# Run ruff formatter
ruff format src/waxprep tests

# Run pyright type checker
pyright src/waxprep
```

## Development Workflow

1. **Before committing**: Run pre-commit hooks
   ```bash
   pre-commit run --all-files
   ```

2. **Before pushing**: Run full quality gate
   ```bash
   python scripts/lint_imports.py --check
   ruff check src/waxprep tests
   ruff format --check src/waxprep tests
   pyright src/waxprep
   pytest tests/ --cov=src/waxprep --cov-report=term
   ```

3. **Code Review**: All PRs must pass CI quality gate

## Key Principles

### Architecture
- **Hexagonal Architecture**: Clear separation between domain, application, adapters, and infrastructure
- **Dependency Inversion**: High-level modules depend on abstractions, not concrete implementations
- **Ports and Adapters**: External integrations implement port interfaces
- **Composition Root**: Only main.py wires all layers together

### Code Quality
- **Type Safety**: Pyright strict mode for all code
- **Linting**: Ruff with comprehensive rule set
- **Formatting**: Consistent code formatting
- **Testing**: All code must have tests
- **Import Rules**: Enforced by import linter

### Error Handling
- **Result Types**: For expected failures (network issues, rate limits, validation)
- **Exceptions**: For programming errors (bugs, invariants)
- **No Silent Failures**: All errors must be handled or logged

### Testing
- **Isolated Tests**: No shared mutable state
- **Order-Independent**: Tests must pass in random order
- **Parallelizable**: Tests must pass with pytest-xdist
- **Layered**: Unit, contract, integration, regression, architecture

## Next Steps

The foundation is now complete through Stage 05. The next steps are:

1. **Stage 06**: Static Analysis and Code Inspection
2. **Stage 07**: Quality Gate Infrastructure
3. **Stage 08**: Implement persistence layer
4. **Stage 09**: Implement message processing pipeline
5. **Stage 10**: Implement personalization engine

Each stage will build on this solid foundation while maintaining the architectural boundaries and engineering standards.

## Resources

- [Hexagonal Architecture](https://alistair.cockburn.us/hexagonal-architecture/) - Architecture pattern
- [Ports and Adapters](https://martinfowler.com/bliki/PortsAndAdapters.html) - Pattern description
- [Ruff](https://github.com/astral-sh/ruff) - Python linter and formatter
- [Pyright](https://github.com/microsoft/pyright) - Static type checker
- [pytest](https://docs.pytest.org/) - Testing framework

## License

MIT License - See LICENSE file for details.
