# R11 — Extract `_QUIET_YDL_OPTS` Constant in `src/ydl_utils.py`

## Problem

`{"quiet": True, "no_warnings": True}` is constructed inline in two functions in the same module:

**`extract_playlist_info` (line 24):**
```python
opts = {"quiet": True, "no_warnings": True}
if playlistend:
    opts["playlistend"] = playlistend
with ydl_class(opts) as ydl:
    return ydl.extract_info(url, download=False)
```

**`extract_video_entries` (line 49):**
```python
opts = {"quiet": True, "no_warnings": True, "extract_flat": extract_flat}
with ydl_class(opts) as ydl:
    info = ydl.extract_info(url, download=False)
    return info.get("entries", [info])
```

Both inline the same two-key base. If a third option needed to be added to all "quiet" YDL contexts (e.g. `"ignoreerrors": True`), it would need to be added in two places.

---

## Goal

Add a module-level constant `_QUIET_YDL_OPTS` and use it as the base in both functions. The constant communicates intent — these are the standard options for metadata-only queries that should not print to stdout.

---

## Changes to `src/ydl_utils.py`

### Add constant after imports, before any function definitions

```python
_QUIET_YDL_OPTS: dict[str, bool] = {"quiet": True, "no_warnings": True}
```

### Update `extract_playlist_info`

```python
# Before:
opts = {"quiet": True, "no_warnings": True}
if playlistend:
    opts["playlistend"] = playlistend

# After:
opts: dict = {**_QUIET_YDL_OPTS}
if playlistend:
    opts["playlistend"] = playlistend
```

### Update `extract_video_entries`

```python
# Before:
opts = {"quiet": True, "no_warnings": True, "extract_flat": extract_flat}

# After:
opts = {**_QUIET_YDL_OPTS, "extract_flat": extract_flat}
```

The spread syntax keeps the line as a single expression and makes it visually clear that the base options are extended with one additional key.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/ydl_utils.py` | Add 1-line constant; update 2 `opts = {...}` lines |

This is the smallest change in the entire set — 3 line modifications total.

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/ydl_utils.py`
3. Trigger a playlist expansion and confirm no yt-dlp output appears in stdout.

---

## Implementation Notes

**Status:** ✅ DONE (2026-04-18)

- Added `_QUIET_YDL_OPTS: dict[str, bool] = {"quiet": True, "no_warnings": True}` after imports in `src/ydl_utils.py`.
- Updated `extract_playlist_info` to use `opts: dict = {**_QUIET_YDL_OPTS}`.
- Updated `extract_video_entries` to use `opts = {**_QUIET_YDL_OPTS, "extract_flat": extract_flat}`.
- 243 tests pass. Ruff FBT001/FBT002 warnings on `extract_flat` parameter are pre-existing and unrelated to this change.
