---
applyTo: "**/*.{py,pyw,pyi}"
---
# Python Coding Standards
- Follow all Ruff linting rules and PEP8 guidelines.
- Use double quotes for strings.
- Prefer list comprehensions over simple for-loops where readable.
- Ensure all functions have type hints.
- Avoid unused imports (Ruff F401).

# Structural Guidelines
- **Prefer Modularity:** Do not allow files to get unwieldly (about 1000 lines). If a file grows too large, suggest a logical split into a sub-package.
- **File Creation:** When asked to implement new features, always suggest a directory structure and separate files for logic, types, and tests.
- **Folder Convention:** Place all core logic in `src/`, tests in `tests/`, and configuration in the root.

Tone: Robotic, clear, concise. No personhood/friendship simulation.
Formatting: Use short answers