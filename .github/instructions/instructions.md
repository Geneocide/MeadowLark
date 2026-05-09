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
- **No Code Duplication:** Code should never be copy pasted. If it is used multiple times, it should be made a function so changes apply consistently. If slight variations are necessary, variable can modify the core function.
- **File Creation:** When asked to implement new features, always suggest a directory structure and separate files for logic, types, and tests.
- **Separation of Concerns:** Avoid creating files that do too much. Group related functions together in files with a common purpose.

# Workflow
- After completing any code changes, YOU MUST delegate verification to the specialized QA agent.
- Instruction: "Use the @qa-boundary-tester to review these changes for edge cases, write new tests when appropriate, and run pytest and Ruff compliance checks before asking me to commit."
- Also run a ruff check after code changes

Tone: Robotic, clear, concise. No personhood/friendship simulation.
Formatting: Use short answers