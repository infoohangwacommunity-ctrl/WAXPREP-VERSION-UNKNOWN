# Justfile — WaxPrep development tasks
# Usage: just <recipe> [args...]
# See https://just.systems/man/en/

# Default recipe
default: check

# ── Static Analysis ──────────────────────────────────────────────────────────

# Run all static analysis tools (blocking tools only)
check: lint format type import-linter semgrep

# Run ruff linting (expanded rules)
lint:
	uv run ruff check src/ tests/

# Run ruff format check
format:
	uv run ruff format --check src/ tests/

# Run both mypy and pyright type checkers
type:
	uv run mypy src/
	uv run pyright src/

# Run import linter
import-linter:
	uv run import-linter lint

# Run semgrep security scan
semgrep:
	uv run semgrep --config auto --error src/

# Run vulture (advisory — does not affect exit code)
# Reads [tool.vulture] from pyproject.toml (single source of truth:
# min_confidence = 80, ignore_names, exclude). vulture.cfg.py is kept as
# documentation only.
vulture:
	uv run vulture src/waxprep/

# ── Testing ─────────────────────────────────────────────────────────────────

# Run all tests
test:
	uv run pytest

# Run unit tests only
unit:
	uv run pytest tests/unit/ -v

# Run integration tests only
integration:
	uv run pytest tests/integration/ -v

# Run tests with coverage
coverage:
	uv run pytest --cov=waxprep --cov-report=term-missing

# ── Setup ───────────────────────────────────────────────────────────────────

# Install dependencies
install:
	uv sync --extra dev

# ── Help ────────────────────────────────────────────────────────────────────

# Show available recipes
help:
	@just --list
