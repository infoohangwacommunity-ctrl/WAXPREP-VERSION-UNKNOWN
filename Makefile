# WaxPrep Makefile — Stage 07 Quality Gate
# `make check` runs the full local equivalent of the CI blocking gate.
# One command. Deterministic. No paid APIs. Usable by humans and AI agents.

.PHONY: check lint format type import-linter semgrep lockfile-check supply-chain pip-audit sbom trust ci-audit test coverage vulture pyright help

# Default target
default: check

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Blocking gate — `make check` runs all of these (matches CI quality-gate)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

check: lint format type import-linter semgrep lockfile-check supply-chain ci-audit test coverage

lint: ## Run ruff linting
	uv run ruff check src/ tests/

format: ## Run ruff format check
	uv run ruff format --check src/ tests/

type: ## Run mypy strict type checker
	uv run mypy src/

import-linter: ## Run import-linter architecture contracts
	uv run import-linter lint

semgrep: ## Run semgrep security scan
	uv run semgrep --config .semgrep --error --exclude src/waxprep/detector src/

lockfile-check: ## Verify uv.lock matches pyproject.toml
	uv lock --check

supply-chain: ## Run dependency + supply-chain gate (Stage 09)
	# pip-audit runs inside this gate. Exceptions are scoped per advisory,
	# package and version in security/dependency-policy/vulnerability-exceptions.toml
	# and expire automatically; no blanket --ignore-vuln is passed.
	uv run python -m waxprep.supplychain.cli check --format summary

pip-audit: supply-chain ## Alias for the Stage 09 dependency gate

sbom: ## Generate the CycloneDX SBOM for runtime dependencies
	uv run python -m waxprep.supplychain.cli sbom

trust: ## Generate the Dependency Trust Intelligence report
	uv run python -m waxprep.supplychain.cli trust --output artifacts/dependency-trust.md

ci-audit: ## Audit workflow integrity (Stage 10: pinning, permissions, jobs, matrix, evidence)
	uv run python -m waxprep.ci.cli audit

test: ## Run all tests
	uv run pytest

coverage: ## Run tests with coverage (enforces fail_under=100)
	uv run pytest --cov=waxprep --cov-fail-under=100

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Advisory — run but do not fail the gate
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

vulture: ## Run vulture dead code detection (advisory)
	uv run vulture src/waxprep/

pyright: ## Run pyright type checker (advisory)
	uv run pyright src/

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Help
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'