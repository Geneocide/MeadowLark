# R02 — Centralize Hardcoded Paths in `src/config.py`

## Problem

Three user-specific paths are hardcoded in 8 locations across 3 source files. Any machine change, drive rename, or OneDrive restructure requires a multi-file search-and-replace:

| Path | Locations |
|---|---|
| `C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt` | `vid downloader.pyw:559,610,1659` · `src/download_service.py:172,205` |
| `C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts` | `vid downloader.pyw:1525` · `src/ydl_options.py:64,73` |
| `E:/vid storage` | `src/ydl_options.py:85,97,123` |

`src/config.py` already defines `LIVE_QUEUE_FILE`, `COOKIES_FILE`, and other paths using a `_resolve_path` helper that supports environment variable overrides. The three paths above just need to be added to the same pattern.

---

## Goal

Add three new constants to `src/config.py` and replace every hardcoded string reference in the three files. No behavior changes — only the source of the string changes.

---

## Changes to `src/config.py`

Add after the existing path constants block (around line 53, after `LIVE_QUEUE_FILE`):

```python
ARCHIVE_PATH: Final[Path] = _resolve_path(
    "VID_DL_ARCHIVE_PATH",
    "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt",
)
PODCAST_MISC_OUTPUT_DIR: Final[Path] = _resolve_path(
    "VID_DL_PODCAST_MISC_OUTPUT_DIR",
    "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/misc",
)
VIDEO_STORAGE_DIR: Final[Path] = _resolve_path(
    "VID_DL_VIDEO_STORAGE_DIR",
    "E:/vid storage",
)
```

Note: `PODCAST_MISC_OUTPUT_DIR` points to the `misc` subfolder because that is the exact directory embedded in `ydl_options.py` outtmpl strings (lines 64, 73). The parent `manual podcasts` dir is not referenced directly anywhere.

---

## Changes to `vid downloader.pyw`

### Add to import from `src.config` (around line 73)
```python
from src.config import (
    ...
    ARCHIVE_PATH,          # add
    ...
)
```

### Line 559 — archive path as `Path`
```python
# Before:
archive_path = Path("C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt")

# After:
archive_path = ARCHIVE_PATH
```

### Line 610 — archive path as string in ydl options
```python
# Before:
properties["download_archive"] = "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt"

# After:
properties["download_archive"] = str(ARCHIVE_PATH)
```

### Line 1525 — podcast base directory
```python
# Before:
base_dir = "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts"

# After:
base_dir = str(PODCAST_MISC_OUTPUT_DIR.parent)
```

### Line 1659 — archive path as string
```python
# Before:
archive_path = "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt"

# After:
archive_path = str(ARCHIVE_PATH)
```

---

## Changes to `src/download_service.py`

### Add to import from `src.config` (around line 18)
```python
from src.config import (
    ...
    ARCHIVE_PATH,          # add
    ...
)
```

### Line 172 — archive path as string in ydl options dict
```python
# Before:
"download_archive": "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt",

# After:
"download_archive": str(ARCHIVE_PATH),
```

### Line 205 — archive path as `Path` in `skip_downloading`
```python
# Before:
archive_path = Path("C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt")

# After:
archive_path = ARCHIVE_PATH
```

The `Path()` wrapper can be dropped entirely since `ARCHIVE_PATH` is already `Final[Path]`.

---

## Changes to `src/ydl_options.py`

### Add to import from `src.config`
```python
from src.config import (
    ...
    PODCAST_MISC_OUTPUT_DIR,   # add
    VIDEO_STORAGE_DIR,         # add
    ...
)
```

### Lines 64 and 73 — audio playlist outtmpl
```python
# Before:
"outtmpl": "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/misc/%(title)s.%(ext)s",

# After:
"outtmpl": (PODCAST_MISC_OUTPUT_DIR / "%(title)s.%(ext)s").as_posix(),
```
(Apply to both line 64 and line 73.)

### Lines 85 and 97 — video storage outtmpl with playlist structure
```python
# Before:
"outtmpl": "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s",

# After:
"outtmpl": (VIDEO_STORAGE_DIR / "%(playlist)s" / "%(playlist_index)s - %(title)s.%(ext)s").as_posix(),
```
(Apply to both line 85 and line 97.)

### Line 123 — video storage outtmpl without playlist
```python
# Before:
"outtmpl": "E:/vid storage/%(title)s.%(ext)s",

# After:
"outtmpl": (VIDEO_STORAGE_DIR / "%(title)s.%(ext)s").as_posix(),
```

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/config.py` | Add 3 constants with env-var override support |
| **Modify** | `vid downloader.pyw` | Update 9 hardcoded strings; add 3 imports |
| **Modify** | `src/download_service.py` | Update 2 hardcoded strings; add 1 import |
| **Modify** | `src/ydl_options.py` | Update 5 hardcoded strings; add 2 imports |
| **Modify** | `tests/test_archive_handling.py` | Patch `ARCHIVE_PATH` directly instead of `Path` constructor |

---

## Implementation Notes

- Used `.as_posix()` instead of `str()` for outtmpl path strings to preserve forward-slash separators (matching original hardcoded strings) and avoid Windows backslash issues with yt-dlp.
- The plan's file summary listed `vid downloader.pyw:559,610,1525,1659` but the file also had a `_get_source_options()` method with 5 additional hardcoded paths (lines ~393,400,411,422,449) that were fixed as well.
- `tests/test_archive_handling.py` patched `src.download_service.Path` to redirect paths; updated to patch `src.download_service.ARCHIVE_PATH` directly since the path is now a module-level constant.

---

## Verification

- 238 tests pass.
- Ruff clean on modified source files (3 pre-existing non-related warnings remain in `download_service.py`).
