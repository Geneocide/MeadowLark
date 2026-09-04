# Python Coding Standards
- Follow Ruff linting and PEP8.
- Use double quotes for strings.
- Prefer list comprehensions.
- Enforce type hints.
- No unused imports (F401).

# Linting & Formatting
- Ruff extension auto-fixes on save (imports, trailing commas, etc.)
- A PostToolUse hook auto-runs `ruff check` on every edited `.py` file (findings fed back automatically); still run a full `uv run ruff check` before commit for cross-file issues.
- Claude focuses on: type correctness, logical errors, security, architecture
- Don't manually fix auto-fixable issues (import order, whitespace)

# Running / Testing
- App: `uv run python meadowlark.pyw`
- Tests: `uv run pytest -q` (never bare `pytest`); single file: `uv run pytest tests/test_x.py -q`
- Lint: `uv run ruff check` (zero findings)
- Shared library: `genekit` (pinned git dependency, see global CLAUDE.md); no in-repo shared package.

# Structural Guidelines
- Feature implementation: Suggest directory structure (`src/`, `tests/`).
