# R04 — Extract `extract_playlist_id` to `src/url_utils.py`

## Problem

The same three-line pattern for extracting a YouTube playlist ID from a URL appears in two files:

```python
parsed = urlparse(url)
qs = parse_qs(parsed.query or "")
if qs.get("list"):
    pl_id = qs["list"][0]
```

| Location | Function | Lines |
|---|---|---|
| `src/path_utils.py` | `resolve_playlist_label` | 86–88 |
| `src/path_utils.py` | `rename_playlist_folders_from_comments` | 124–126 |
| `src/playlist_utils.py` | `load_playlist_comments_for_source` | 109–111 |

No `src/url_utils.py` exists yet. Both files already import `urlparse` and `parse_qs` from `urllib.parse`.

---

## Goal

Create `src/url_utils.py` with a single `extract_playlist_id` function. Update all three call sites to use it and remove the now-redundant `urlparse`/`parse_qs` imports from both files (if they're no longer used elsewhere in those modules).

---

## New File: `src/url_utils.py`

```python
"""URL parsing utilities."""

from urllib.parse import parse_qs, urlparse


def extract_playlist_id(url: str) -> str | None:
    """Return the YouTube playlist ID from a URL's `list` query parameter, or None."""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query or "")
        ids = qs.get("list")
        return ids[0] if ids else None
    except (ValueError, AttributeError, TypeError):
        return None
```

Improvements over the inline version:
- Returns `None` explicitly instead of relying on callers to check `if qs.get("list")`.
- Wraps in try/except to match the exception handling already present in `resolve_playlist_label`.
- Single consistent point to extend if other URL parameters need extraction later.

---

## Changes to `src/path_utils.py`

### Add import
```python
from src.url_utils import extract_playlist_id
```

### Remove `urlparse` and `parse_qs` from imports if no longer used elsewhere in this file
```python
# Before:
from urllib.parse import parse_qs, urlparse

# After (if both are unused after this change):
# remove the line entirely
```
Check the full file first — if `urlparse` or `parse_qs` appear in any other function, keep that import.

### `resolve_playlist_label` — replace lines 86–89
```python
# Before:
u = urlparse(url)
qs = parse_qs(u.query or "")
if qs.get("list"):
    label = f"playlist-{qs['list'][0]}"
else:
    segs = [s for s in (u.path or "").split("/") if s]
    label = segs[-1] if segs else url

# After:
pl_id = extract_playlist_id(url)
if pl_id:
    label = f"playlist-{pl_id}"
else:
    try:
        segs = [s for s in (urlparse(url).path or "").split("/") if s]
        label = segs[-1] if segs else url
    except (ValueError, AttributeError, TypeError):
        label = url
```

Note: `urlparse` is still needed for the path fallback, so keep that import if this is the case.

### `rename_playlist_folders_from_comments` — replace lines 124–127
```python
# Before:
parsed = urlparse(url)
qs = parse_qs(parsed.query or "")
if qs.get("list"):
    pl_id = qs["list"][0]
    playlist_ids[pl_id] = pl_id

# After:
pl_id = extract_playlist_id(url)
if pl_id:
    playlist_ids[pl_id] = pl_id
```

---

## Changes to `src/playlist_utils.py`

### Add import
```python
from src.url_utils import extract_playlist_id
```

### Remove `urlparse` and `parse_qs` from imports if no longer used elsewhere
```python
# Before:
from urllib.parse import parse_qs, urlparse

# After (if unused):
# remove the line entirely
```

### `load_playlist_comments_for_source` — replace lines 109–112
```python
# Before:
parsed = urlparse(line)
qs = parse_qs(parsed.query or "")
if qs.get("list"):
    pl_id = qs["list"][0]
    comments[pl_id] = last_comment

# After:
pl_id = extract_playlist_id(line)
if pl_id:
    comments[pl_id] = last_comment
```

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Create** | `src/url_utils.py` | New module with `extract_playlist_id` (~12 lines) |
| **Modify** | `src/path_utils.py` | Add import; replace pattern in 2 functions |
| **Modify** | `src/playlist_utils.py` | Add import; replace pattern in 1 function |

---

## Suggested Test Addition: `tests/test_url_utils.py`

```python
from src.url_utils import extract_playlist_id


def test_extracts_list_param() -> None:
    url = "https://www.youtube.com/playlist?list=PLabc123"
    assert extract_playlist_id(url) == "PLabc123"


def test_returns_none_for_no_list_param() -> None:
    url = "https://www.youtube.com/watch?v=abc123"
    assert extract_playlist_id(url) is None


def test_returns_none_for_empty_string() -> None:
    assert extract_playlist_id("") is None


def test_returns_none_for_malformed_url() -> None:
    assert extract_playlist_id("not a url at all") is None


def test_handles_url_with_multiple_params() -> None:
    url = "https://www.youtube.com/watch?v=abc&list=PLxyz&index=1"
    assert extract_playlist_id(url) == "PLxyz"
```

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/url_utils.py src/path_utils.py src/playlist_utils.py`
3. Trigger a podcast check using a playlist URL and confirm the playlist label resolves correctly.
4. Trigger a folder rename from comments and confirm playlist IDs are still matched correctly.
