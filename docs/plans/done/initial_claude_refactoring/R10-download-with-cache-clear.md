# R10 — Extract `_download_with_cache_clear` Helper in `DownloadExecutor`

## Problem

`ydl.cache.remove()` is called immediately before every `ydl.download(urls)` call inside a `with YoutubeDL(...) as ydl:` block. This three-line pattern appears in three methods:

| Method | Lines |
|---|---|
| `execute` (main attempt) | 171–173 |
| `_try_720_fallback` | 103–105 |
| `_try_without_sponsorblock` | 146–148 |

Each occurrence is identical:
```python
with YoutubeDL(opts) as ydl:
    ydl.cache.remove()
    ydl.download(urls)
```

After R09 is applied, the two fallback methods delegate to `_try_fallback`, which will also contain this pattern — so the consolidation point becomes `_try_fallback` plus `execute`.

---

## Goal

Extract a `_download_with_cache_clear` method that wraps the three-line pattern. Every call site becomes a single line. The cache-clear behavior is now documented in one place, making it easy to understand why it always happens.

---

## New Method: `_download_with_cache_clear`

Add to `DownloadExecutor` alongside the other private helpers:

```python
def _download_with_cache_clear(self, opts: dict, urls: list) -> None:
    """Run yt-dlp download after clearing cache to avoid stale format data."""
    with YoutubeDL(opts) as ydl:
        ydl.cache.remove()
        ydl.download(urls)
```

The comment on why cache is cleared belongs here and only here.

---

## Updated Call Sites

### If R09 has been applied — update `_try_fallback`

```python
# Before (inside _try_fallback):
try:
    with YoutubeDL(fallback) as ydl:
        ydl.cache.remove()
        ydl.download(urls)
    return True, error_str  # noqa: TRY300

# After:
try:
    self._download_with_cache_clear(fallback, urls)
    return True, error_str  # noqa: TRY300
```

### If R09 has NOT been applied — update both fallback methods individually

**`_try_720_fallback` (lines 103–105):**
```python
# Before:
with YoutubeDL(fallback) as ydl:
    ydl.cache.remove()
    ydl.download(urls)

# After:
self._download_with_cache_clear(fallback, urls)
```

**`_try_without_sponsorblock` (lines 146–148):**
```python
# Before:
with YoutubeDL(fallback) as ydl:
    ydl.cache.remove()
    ydl.download(urls)

# After:
self._download_with_cache_clear(fallback, urls)
```

### `execute` main attempt (lines 171–173)

```python
# Before:
try:
    with YoutubeDL(options) as ydl:
        ydl.cache.remove()
        ydl.download(urls)

# After:
try:
    self._download_with_cache_clear(options, urls)
```

---

## Implementation Order

R10 is independent of R09 but composes cleanly with it:
- **R10 only:** Update three separate call sites.
- **R09 then R10:** Update one call site (`_try_fallback`) plus `execute`.
- **R10 then R09:** The `_try_fallback` introduced by R09 already has the pattern consolidated — easy to update.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/download_executor.py` | Add `_download_with_cache_clear` (~4 lines); collapse 3× three-line blocks to 3× one-liners |

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/download_executor.py`
3. Trigger a standard download and confirm it completes successfully — the cache clear still runs before every download.

---

## Implementation Notes

**Status:** ✅ DONE (2026-04-18)

R09 has not been applied, so updated all three call sites directly:
- Added `_download_with_cache_clear(self, opts, urls)` helper after `_emit_message`.
- Replaced 3-line `with YoutubeDL / cache.remove / download` blocks in `_try_720_fallback`, `_try_without_sponsorblock`, and `execute` with single-line calls.
- Pre-existing Ruff warnings (ARG002, C901, PLR2004, TRY300) are unrelated. 243 tests pass.
