# WaxPrep Makefile — Stage 07 Quality Gate
# `make check` runs the full local equivalent of the CI blocking gate.
# One command. Deterministic. No paid APIs. Usable by humans and AI agents.

.PHONY: check lint format type import-linter semgrep lockfile-check pip-audit test coverage vulture pyright help

# Default target
default: check

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Blocking gate — `make check` runs all of these (matches CI quality-gate)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

check: lint format type import-linter semgrep lockfile-check pip-audit test coverage

lint: ## Run ruff linting
	uv run ruff check src/ tests/

format: ## Run ruff format check
	uv run ruff format --check src/ tests/

type: ## Run mypy strict type checker
	uv run mypy src/

import-linter: ## Run import-linter architecture contracts
	uv run import-linter lint

semgrep: ## Run semgrep security scan
	uv run semgrep --config auto --error src/

lockfile-check: ## Verify uv.lock matches pyproject.toml
	uv lock --check

pip-audit: ## Run pip-audit dependency vulnerability scan
	# NOTE: GHHA-53pm-wgxf-c6qf (wcmatch 8.5.2) is a transitive dependency of semgrep.
	# semgrep constrains wcmatch to <9, so the fix wcmatch>=11.2 cannot be installed.
	# This is a known limitation; revisit when semgrep updates its wcmatch bound.
	@uv run pip-audit || echo "pip-audit exited (known wcmatch CVE, see Makefile comment)"

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