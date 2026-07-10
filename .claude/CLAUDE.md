# Python Coding Standards
- Follow Ruff linting and PEP8.
- Use double quotes for strings.
- Prefer list comprehensions.
- Enforce type hints.
- No unused imports (F401).

# Linting & Formatting
- Ruff extension auto-fixes on save (imports, trailing commas, etc.)
- Claude focuses on: type correctness, logical errors, security, architecture
- Don't manually fix auto-fixable issues (import order, whitespace)

# Structural Guidelines
- Feature implementation: Suggest directory structure (`src/`, `tests/`).

# Workflow
- Also run a ruff check after code changes