# R18 — Convert `_default_postprocessors()` to a Module Constant

## Problem

`_default_postprocessors()` in `src/dict_utils.py` (lines 41–53) is a zero-argument function that always returns the same list:

```python
def _default_postprocessors() -> list[dict[str, Any]]:
    """Return default postprocessor configuration for yt-dlp."""
    return [
        {"key": "SponsorBlock"},
        {
            "key": "ModifyChapters",
            "remove_sponsor_segments": ["sponsor", "selfpromo"],
        },
    ]
```

It is called in three places in `src/ydl_options.py` (lines 43, 118, 145) and exported through `utils.py` (imported at line 12, listed in `__all__` at line 50).

A function that takes no arguments and always returns the same value with no side effects is a constant. Calling it as a function is misleading — it implies the return value might vary.

---

## Goal

Replace `_default_postprocessors()` with a module-level constant `DEFAULT_POSTPROCESSORS`. Update all call sites and the `utils.py` export. The name change from private (`_default_postprocessors`) to public (`DEFAULT_POSTPROCESSORS`) reflects that it is already exported and used externally.

---

## Changes to `src/dict_utils.py`

### Replace the function with a constant

```python
# Before:
def _default_postprocessors() -> list[dict[str, Any]]:
    """Return default postprocessor configuration for yt-dlp."""
    return [
        {"key": "SponsorBlock"},
        {
            "key": "ModifyChapters",
            "remove_sponsor_segments": ["sponsor", "selfpromo"],
        },
    ]

# After:
DEFAULT_POSTPROCESSORS: list[dict[str, Any]] = [
    {"key": "SponsorBlock"},
    {
        "key": "ModifyChapters",
        "remove_sponsor_segments": ["sponsor", "selfpromo"],
    },
]
```

---

## Changes to `src/ydl_options.py`

### Update import
```python
# Before (wherever dict_utils is imported):
from .dict_utils import _default_postprocessors

# After:
from .dict_utils import DEFAULT_POSTPROCESSORS
```

### Replace all three call sites

**Line 43** — in `build_base_ydl_opts`:
```python
# Before:
"postprocessors": _default_postprocessors(),

# After:
"postprocessors": list(DEFAULT_POSTPROCESSORS),
```

**Line 118** — in `get_source_options`:
```python
# Before:
"postprocessors": _default_postprocessors(),

# After:
"postprocessors": list(DEFAULT_POSTPROCESSORS),
```

**Line 145** — in `get_postprocessors` fallback:
```python
# Before:
return get_source_options(source).get("postprocessors", _default_postprocessors())

# After:
return get_source_options(source).get("postprocessors", list(DEFAULT_POSTPROCESSORS))
```

`list(DEFAULT_POSTPROCESSORS)` creates a shallow copy each time, so callers that mutate the postprocessors list cannot accidentally mutate the module constant. This matches the behavior of the old function (which returned a new list on every call).

---

## Changes to `utils.py`

### Update import
```python
# Before:
from src.dict_utils import (
    _default_postprocessors,
    ...
)

# After:
from src.dict_utils import (
    DEFAULT_POSTPROCESSORS,
    ...
)
```

### Update `__all__`
```python
# Before:
"_default_postprocessors",

# After:
"DEFAULT_POSTPROCESSORS",
```

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/dict_utils.py` | Replace function definition with module constant |
| **Modify** | `src/ydl_options.py` | Update import; replace 3 call sites with `list(DEFAULT_POSTPROCESSORS)` |
| **Modify** | `utils.py` | Update import and `__all__` entry |

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/dict_utils.py src/ydl_options.py utils.py`
3. Trigger a download and confirm SponsorBlock and ModifyChapters postprocessors still run (sponsor segments are removed from the downloaded file).

---

## Implementation Notes

**Status:** ✅ DONE (2026-04-18)

- Replaced `_default_postprocessors()` function with `DEFAULT_POSTPROCESSORS: list[dict[str, Any]]` constant in `src/dict_utils.py`.
- Updated import and all 3 call sites in `src/ydl_options.py` to use `list(DEFAULT_POSTPROCESSORS)` (shallow copy preserves immutability of constant).
- Updated import and `__all__` in `utils.py`; also sorted `__all__` to fix a `RUF022` that surfaced with the rename.
- COM812 on `merge_dicts_recursive` signature is pre-existing and unrelated. 243 tests pass.
