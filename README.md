# WaxPrep Foundation - Stages 01-02 ONLY

**IMPORTANT: This repository contains ONLY Stages 01 and 02.**

## Stage 01: Programming Language
- Python 3.14+ (compatibility proven, not assumed)
- uv for dependency management
- Pydantic v2 for data validation
- Static type checking (mypy/pyright)

## Stage 02: Runtime and Execution Environment
- ASGI application (FastAPI + Uvicorn)
- Empty registries with fake adapters (proves architecture)
- Graceful shutdown (proven by test)
- Health endpoints (liveness ≠ readiness)
- Structured logging with correlation IDs
- Tenant isolation at boundary (proven by test)
- Message acceptance contract (proven by test)

## What is NOT included (later stages):
- ❌ NO WhatsApp handlers
- ❌ NO Telegram handlers  
- ❌ NO database schema
- ❌ NO docker-compose files
- ❌ NO PostgreSQL/Redis configuration
- ❌ NO tutor logic
- ❌ NO intelligence layer
- ❌ NO message router
- ❌ NO student context manager
- ❌ NO model orchestrator
- ❌ NO tool executor
- ❌ NO Prometheus/OpenTelemetry
- ❌ NO production deployment

## NO Hardcoding Rule
- ❌ NO model names hardcoded
- ❌ NO API keys hardcoded
- ❌ NO ports hardcoded
- ❌ NO timeouts hardcoded
- ❌ NO grace periods hardcoded
- ❌ NO channel identifiers hardcoded
- ❌ NO student levels hardcoded
- ❌ NO greetings hardcoded
- ❌ NO keyword routes hardcoded

All configuration lives in environment variables or test fixtures.
