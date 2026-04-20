# Plan: Fix CI — `ruff` not found

## What is CI?

**CI (Continuous Integration)** is an automated system that runs every time you push code to GitHub. Think of it as a robot that checks your work: it installs your project on a clean computer, runs all your tests, and checks your code for style/quality issues. If anything fails, GitHub emails you (which is what you got).

Your CI is defined in [.github/workflows/ci.yml](.github/workflows/ci.yml). Here's what it does, step by step:

1. **Checkout** — Downloads your code onto GitHub's server
2. **Setup uv** — Installs `uv`, the package manager (like pip but faster)
3. `uv sync` — Installs your project's dependencies (all the libraries in `pyproject.toml`)
4. `uv run pytest` — Runs all your tests ✅ (369 passed, 1 skipped — this is fine!)
5. `uv run ruff check` — Checks your code style ❌ **THIS FAILED**

## Root Cause

The error in the CI logs was:
```
error: Failed to spawn: `ruff`
  Caused by: program not found
```

`ruff` is the linting tool (style checker). The CI tries to run it with `uv run ruff check`, but `ruff` was never installed — it's not listed anywhere in `pyproject.toml`. So `uv sync` didn't install it, and when CI tried to run it, it simply didn't exist.

On your local machine, ruff works because you have the VS Code extension installed separately. In CI, there's no VS Code — only what's in `pyproject.toml`.

## The Fix

Two small changes:

### 1. Add `ruff` to dev dependencies in `pyproject.toml`

Dev dependencies are tools you use while developing (linters, build tools, test runners) that aren't needed by users of the app.

**File:** [pyproject.toml](pyproject.toml), lines 19-22

```toml
# Before:
[dependency-groups]
dev = [
    "pyinstaller>=6.0",
]

# After:
[dependency-groups]
dev = [
    "pyinstaller>=6.0",
    "ruff>=0.9.0",
]
```

### 2. Tell CI to install dev dependencies too

Right now CI runs `uv sync` which skips dev dependencies. Change it to `uv sync --group dev`.

**File:** [.github/workflows/ci.yml](.github/workflows/ci.yml), line 9

```yaml
# Before:
- run: uv sync

# After:
- run: uv sync --group dev
```

## Files to Change

- [pyproject.toml](pyproject.toml) — add `ruff` to `[dependency-groups] dev`
- [.github/workflows/ci.yml](.github/workflows/ci.yml) — change `uv sync` → `uv sync --group dev`

## Verification

After the fix is committed and pushed to `claude-refactoring`, the CI run should:
1. Install all dev dependencies including `ruff`
2. Pass `pytest` (already passing)
3. Pass `ruff check` (no errors expected, since ruff runs locally via VS Code)
4. Show green ✅ on GitHub instead of red ❌
