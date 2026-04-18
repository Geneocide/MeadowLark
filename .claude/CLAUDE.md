# Python Coding Standards
- Follow Ruff linting and PEP8.
- Use double quotes for strings.
- Prefer list comprehensions.
- Enforce type hints.
- No unused imports (F401).

# Structural Guidelines
- Modularize files exceeding 1000 lines.
- Zero code duplication; use functions with variables for variations.
- Feature implementation: Suggest directory structure (`src/`, `tests/`).

# Workflow
- After completing any code changes, YOU MUST delegate verification to the specialized QA agent.
- Instruction: "Use the @qa-boundary-tester to review these changes for edge cases and Ruff compliance before asking me to commit."