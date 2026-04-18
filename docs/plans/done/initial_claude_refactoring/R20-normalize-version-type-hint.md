# R20 — Fix `# type: ignore` on `normalize_version(None)` in Tests ✅ DONE (2026-04-18)

## Implementation Notes

Widened `normalize_version` signature from `version: str` to `version: str | None` in `src/version_utils.py` — the body already handled non-strings via `isinstance`. Removed `# type: ignore` from `tests/test_utils.py:25`. 243 tests pass.

---

## Problem

`tests/test_utils.py:25` passes `None` to `normalize_version`, which is typed as `str`:

```python
def test_normalize_version_invalid(self) -> None:
    assert normalize_version(None) == ()  # type: ignore
    assert normalize_version("") == ()
    assert normalize_version("abc") == ()
```

The `# type: ignore` suppresses the type checker's complaint. Meanwhile, the implementation already handles `None` correctly:

```python
# src/version_utils.py
def normalize_version(version: str) -> tuple[int, ...]:
    if not isinstance(version, str):
        return ()
    parts = re.findall(r"\d+", version)
    return tuple(int(x) for x in parts)
```

The function's behavior for non-string inputs is intentional and documented in its docstring ("Returns empty tuple if not a string"). The type annotation is simply wrong — it claims `str` is required but the implementation deliberately supports `str | None` (and any other non-string type).

---

## Goal

Correct the type annotation on `normalize_version` to match its actual behavior. The `# type: ignore` in the test becomes unnecessary and is removed.

---

## Change to `src/version_utils.py`

### Update the function signature

```python
# Before:
def normalize_version(version: str) -> tuple[int, ...]:

# After:
def normalize_version(version: str | None) -> tuple[int, ...]:
```

The body is unchanged — the `isinstance` guard already handles the `None` case.

---

## Change to `tests/test_utils.py`

### Remove `# type: ignore` on line 25

```python
# Before:
assert normalize_version(None) == ()  # type: ignore

# After:
assert normalize_version(None) == ()
```

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/version_utils.py` | Change `version: str` to `version: str | None` in signature |
| **Modify** | `tests/test_utils.py` | Remove `# type: ignore` comment on line 25 |

Two one-line changes. No behavior change.

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/version_utils.py tests/test_utils.py`
3. Run mypy or pyright if configured — confirm no new type errors introduced and the suppressed error is gone.
