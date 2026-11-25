# Justfile — WaxPrep development tasks
# Usage: just <recipe> [args...]
# See https://just.systems/man/en/

# Default recipe
default: check

# ── Static Analysis ──────────────────────────────────────────────────────────

# Run all static analysis tools (blocking tools only — matches CI quality-gate)
check: lint format type import-linter semgrep lockfile-check supply-chain test coverage

# Run ruff linting (expanded rules)
lint:
	uv run ruff check src/ tests/

# Run ruff format check
format:
	uv run ruff format --check src/ tests/

# Run mypy strict type checker
type:
	uv run mypy src/

# Run import linter (architecture contracts)
import-linter:
	uv run import-linter lint

# Run semgrep security scan
semgrep:
	uv run semgrep --config .semgrep --error --exclude src/waxprep/detector src/

# Verify lockfile integrity (uv.lock matches pyproject.toml)
lockfile-check:
	uv lock --check

# Run the Stage 09 dependency + supply-chain gate
supply-chain:
	# pip-audit runs inside this gate. Exceptions are scoped per advisory,
	# package and version in security/dependency-policy/vulnerability-exceptions.toml
	# and expire automatically; no blanket --ignore-vuln is passed.
	uv run python -m waxprep.supplychain.cli check --format summary

# Alias for the Stage 09 dependency gate
pip-audit: supply-chain

# Generate the CycloneDX SBOM for runtime dependencies
sbom:
	uv run python -m waxprep.supplychain.cli sbom

# Generate the Dependency Trust Intelligence report
trust:
	uv run python -m waxprep.supplychain.cli trust --output artifacts/dependency-trust.md

# Run all tests
test:
	uv run pytest

# Run tests with coverage (enforces fail_under=100)
coverage:
	uv run pytest --cov=waxprep --cov-fail-under=100

# Run vulture (advisory — does not affect exit code)
vulture:
	uv run vulture src/waxprep/

# Run pyright (advisory — does not affect exit code)
pyright:
	uv run pyright src/

# ── Testing ─────────────────────────────────────────────────────────────────

# Run unit tests only
unit:
	uv run pytest tests/unit/ -v

# Run integration tests only
integration:
	uv run pytest tests/integration/ -v

# ── Setup ───────────────────────────────────────────────────────────────────

# Install dependencies
install:
	uv sync --extra dev

# ── Help ────────────────────────────────────────────────────────────────────

# Show available recipes
help:
	@just --list
