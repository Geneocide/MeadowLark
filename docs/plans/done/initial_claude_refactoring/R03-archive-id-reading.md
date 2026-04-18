# R03 — Use `load_downloaded_video_ids` in `download_service.py`

## Problem

`src/download_service.py` reimplements archive file reading inline inside `skip_downloading` (lines 207–213) instead of calling the existing `load_downloaded_video_ids` function from `src/podcast_filtering.py`:

**Inline reimplementation (`src/download_service.py:207–213`):**
```python
if archive_path.exists():
    with archive_path.open("r", encoding="utf-8") as archive:
        existing_ids = {
            line.strip().split()[-1] for line in archive if line.strip()
        }
else:
    existing_ids = set()
```

**Canonical implementation (`src/podcast_filtering.py:43–79`):**
```python
def load_downloaded_video_ids(archive_path: str | None) -> set[str]:
    """Load set of already-downloaded video IDs from archive file."""
    existing_ids: set[str] = set()
    if not archive_path:
        return existing_ids
    archive_file = Path(archive_path)
    if not archive_file.exists():
        return existing_ids
    try:
        with archive_file.open("r", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                parts = stripped_line.split()
                if parts:
                    existing_ids.add(parts[-1])
    except (OSError, UnicodeDecodeError) as exc:
        utils.log_exception(exc, "Failed to read download archive for podcast filtering")
    return existing_ids
```

Two additional problems in the inline version:
1. It silently crashes if `archive_path` doesn't exist and `.exists()` check passes but the open fails — the canonical version catches `OSError`.
2. It references a hardcoded `archive_path` built from a literal string (R02), not the config constant.

---

## Goal

Replace the 7-line inline block in `skip_downloading` with a single call to `load_downloaded_video_ids`. Also fix the hardcoded path at line 205 using `ARCHIVE_PATH` from `src/config.py` (R02 overlap).

---

## Changes to `src/download_service.py`

### Add to import from `src.podcast_filtering` (wherever that module is currently imported, or add new import)
```python
from src.podcast_filtering import load_downloaded_video_ids
```

### Add to import from `src.config`
```python
from src.config import (
    ...
    ARCHIVE_PATH,    # add
    ...
)
```

### Replace lines 205–213 in `skip_downloading`

```python
# Before:
archive_path = Path("C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt")
# Read existing IDs into a set
if archive_path.exists():
    with archive_path.open("r", encoding="utf-8") as archive:
        existing_ids = {
            line.strip().split()[-1] for line in archive if line.strip()
        }
else:
    existing_ids = set()

# After:
existing_ids = load_downloaded_video_ids(str(ARCHIVE_PATH))
```

The `load_downloaded_video_ids` signature accepts `str | None`, so `str(ARCHIVE_PATH)` is the correct call. After R02 is applied, `ARCHIVE_PATH` is `Final[Path]` from config so `str()` wrapping is the only conversion needed.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/download_service.py` | Add 2 imports; replace 7-line inline block with 1-line call |

This is the smallest change in the entire proposal — two imports and one line replacing seven. The canonical function already has correct error handling, blank-line skipping, and `UnicodeDecodeError` protection that the inline version lacks.

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/download_service.py`
3. Trigger "Skip Downloading" with a playlist that has already-archived entries and confirm the correct IDs are detected and no re-downloads occur.
4. Test with a non-existent archive path and confirm the function returns an empty set without crashing (handled by `load_downloaded_video_ids`).
