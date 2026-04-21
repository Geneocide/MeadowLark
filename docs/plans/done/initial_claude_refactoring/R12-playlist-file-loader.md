# R12 — Unify Playlist File Reading in `src/playlist_utils.py`

## Problem

Two functions read playlist files but handle them differently:

**`load_playlist_comments_for_source` in `src/playlist_utils.py` (lines 75–114):**
- Returns `dict[str, str]` — maps playlist IDs to their preceding comment
- Skips blank lines, tracks comment state across iterations
- Extracts playlist ID via `extract_playlist_id(line)` (from R04)
- Has `OSError` handling with `log_exception`

**`_load_playlist_urls` in `src/download_service.py` (lines 129–149):**
- Returns `list[str] | None` — raw URL strings, no ID extraction
- Strips comment lines via `not line.startswith("#")` filter
- No error handling — a missing file silently returns `None`

These two functions serve different callers with different needs, so a single function with a polymorphic return type would be awkward. The right fix is narrower: extract the **raw line-reading logic** into a shared helper in `playlist_utils.py`, then use it in both. `_load_playlist_urls` also gains the OSError handling it currently lacks.

---

## Goal

Add `load_playlist_urls(path: Path) -> list[str]` to `src/playlist_utils.py` as a low-level reader that returns non-blank, non-comment URL strings with proper error handling. Update `_load_playlist_urls` in `download_service.py` to call it.

---

## New Function: `load_playlist_urls` in `src/playlist_utils.py`

Add below the existing imports and constants, before `load_playlist_comments_for_source`:

```python
def load_playlist_urls(path: Path) -> list[str]:
    """Return all non-blank, non-comment lines from a playlist file as raw URL strings.

    Returns an empty list if the file does not exist or cannot be read.
    """
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
    except (OSError, UnicodeDecodeError) as exc:
        log_exception(exc, f"Failed to read playlist file: {path}")
        return []
```

---

## Changes to `src/download_service.py`

### Add import
```python
from src.playlist_utils import load_playlist_urls
```

### Replace `_load_playlist_urls` (lines 129–149)

```python
def _load_playlist_urls(self, source: str) -> list[str] | None:
    """Load playlist URLs from the appropriate file based on the source."""
    playlist_files = {
        "1080playlists": PLAYLISTS_FILE,
        "720playlists": PLAYLISTS_720_FILE,
        "audio_playlists": PLAYLISTS_AUDIO_FILE,
    }
    if source not in playlist_files:
        return None
    return load_playlist_urls(Path(playlist_files[source])) or None
```

The `or None` preserves the existing contract: callers that check `if urls is None` to detect "not a playlist source" will still work correctly, since `load_playlist_urls` returns `[]` (falsy) for missing files, which becomes `None` here.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/playlist_utils.py` | Add `load_playlist_urls` function (~12 lines) |
| **Modify** | `src/download_service.py` | Add import; replace `_load_playlist_urls` body (~10 lines → ~4 lines) |
| **Create** | `tests/test_playlist_utils.py` | 22 tests covering boundary matrix |

Benefit gained: `_load_playlist_urls` now logs `OSError`/`UnicodeDecodeError` rather than silently crashing.

---

## Implementation Notes

- QA agent identified that `except OSError` did not catch `UnicodeDecodeError` for non-UTF-8 files. Fixed to `except (OSError, UnicodeDecodeError)`.
- `tests/test_playlist_utils.py` created with 22 tests (6 original + 16 boundary cases from QA). Covers: URL stripping, comment filtering, blank lines, missing file, empty file, no trailing newline, inline `#` anchor preserved, `##` comments, mixed content, non-UTF-8 bytes, permission denied (Unix only, skipped on Windows), directory path, large files (5000 URLs), and all wrapper `None`-vs-`[]` contract cases.
- Pre-existing Ruff issues in `download_service.py` (`PLR0913`, `PERF203`) and `playlist_utils.py` (`D213`) are unchanged.
- 263 tests pass, 1 skipped (chmod test on Windows).

---

## Verification

1. Run all tests: `pytest tests/ -v` → **263 passed, 1 skipped**
2. Run Ruff: `ruff check src/playlist_utils.py src/download_service.py` → no new violations
3. Trigger a playlist download (1080, 720, or audio) and confirm URLs are still loaded and downloads proceed normally.
