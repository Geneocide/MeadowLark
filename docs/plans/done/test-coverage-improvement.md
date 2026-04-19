# Plan: Increase Unit Test Coverage

## Context
Current overall coverage is **89% (782 stmts, 87 missed)**. The goal is to cover the remaining gaps by writing tests — no functionality changes. Refactoring is allowed only when it makes untested code paths injectable/testable without altering behaviour.

Coverage baseline (run: `pytest --cov=src --cov-report=term-missing -q`):

| Module | Cover | Missed lines |
|---|---|---|
| playlist_utils.py | 52% | 51-53, 67-72, 108-133 |
| ydl_utils.py | 53% | 25, 28, 49-54 |
| ydl_options.py | 57% | 101-115, 133, 146 |
| match_filter.py | 78% | 26, 38-41 |
| url_utils.py | 78% | 13-14 |
| exceptions.py | 80% | 38-39 |
| version_utils.py | 84% | 39-42, 56 |
| path_utils.py | 88% | 88, 93-94, 118, 142-148 |
| logging_utils.py | 90% | 33 |
| podcast_filtering.py | 91% | 69, 73-74, 97-98, 129-130, 196 |
| download_service.py | 95% | 110-112, 243, 288-291 |
| dict_utils.py | 95% | 67 |

---

## Plan 1 — Quick Wins: Isolated Exception/Edge Paths ⭐⭐⭐ (Priority 1)

**Effort: Low | Impact: High (covers ~12 lines across 5 files)**

All these are single-branch gaps in already-tested files. Add to or create minimal test files.

### `tests/test_url_utils.py` — lines 13-14
- Add test: `extract_playlist_id(None)` → `None` (triggers `AttributeError`)
- Add test: `extract_playlist_id(123)` → `None` (triggers `TypeError`)

### `tests/test_utils.py` (or new `tests/test_exceptions.py`) — exceptions.py lines 38-39
- Test `PlaylistExtractionError(original_exc=ValueError("x"))` stores `.original_exc`
- Test `PlaylistExtractionError()` uses default MSG

### `tests/test_utils.py` — dict_utils.py line 67
- Test `remove_sponsorblock_postprocessor` when `postprocessors` is not a list (e.g., `None`, `"string"`) → returns copy unchanged

### `tests/test_logging_utils.py` — line 33
- Test `log_exception` when root logger has no handlers → triggers `basicConfig` branch
  - Use `logging.root.handlers.clear()` around the call, restore after

### `tests/test_version_utils.py` — lines 39-42, 56
- Test `get_current_yt_dlp_version()` when `yt_dlp.version` lacks `__version__` attr → falls back to `yt_dlp.__version__`  
  (mock `yt_dlp.version.__version__` to raise `AttributeError`)
- Test `get_latest_yt_dlp_version()` when response status != 200 → returns `None`  
  (mock `requests.get` to return `Mock(status_code=404)`)

---

## Plan 2 — ydl_options.py + ydl_utils.py ⭐⭐⭐ (Priority 1)

**Effort: Low-Medium | Impact: High (covers 18 lines, lifts two modules from ~53-57% to 100%)**

Create `tests/test_ydl_options.py` and `tests/test_ydl_utils.py` (or add to existing `test_utils.py`).

### `src/ydl_options.py` — lines 101-115, 133, 146
The uncovered path is the fallback in `get_source_options()` for unknown/numeric sources:
- Test `get_source_options("480")` → format string contains `height=480` (numeric height path, lines 101-114)
- Test `get_source_options("garbage")` → format is `"bestvideo*+bestaudio/best"` (non-numeric fallback, line 113)
- Test `get_output_template("audio")` → returns expected outtmpl string (line 133)
- Test `get_postprocessors("audio")` → returns audio postprocessors list (line 146)
- Test `get_postprocessors("garbage")` → returns `DEFAULT_POSTPROCESSORS` list (line 146 `.get` fallback)

### `src/ydl_utils.py` — lines 25, 28, 49-54
The uncovered paths are the default `ydl_class` injection and `extract_video_entries`:
- Test `extract_playlist_info(url, ydl_class=MockYDL)` with `playlistend=None` → does NOT set `playlistend` key (line 25/28)
- Test `extract_playlist_info(url, playlistend=5, ydl_class=MockYDL)` → `playlistend` key present
- Test `extract_video_entries(url, ydl_class=MockYDL)` → returns `info["entries"]` (lines 49-54)
- Test `extract_video_entries` when `info` has no `entries` → returns `[info]` fallback

Use a mock class that satisfies the context manager protocol (`__enter__`/`__exit__`) and returns fake info dicts.

---

## Plan 3 — playlist_utils.py ⭐⭐ (Priority 2)

**Effort: Medium | Impact: Medium (covers 29 lines, lifts module from 52% → ~95%+)**

Add tests to `tests/test_playlist_utils.py`.

### Lines 51-53: `is_primitive_technology` exception branch
- Test with `info = None` → `log_exception` called, returns `False`
- Test with `info = {"title": None, "channel": None}` → returns `False`

### Lines 67-72: `get_playlist_file_for_source` mappings
- Test each of `"1080playlists"`, `"720playlists"`, `"audio_playlists"` → returns expected path string
- Test unknown source → returns `None`

### Lines 108-133: `load_playlist_comments_for_source` full logic
- Test with unknown source → `{}` (line 109-110)
- Test with valid source but file missing → `{}` (line 112-113)
- Test with valid source and file with `#Comment` before URL → extracts `{playlist_id: "Comment"}`
- Test URL without `list=` param → no entry added for that URL
- Test URL after non-comment line (no preceding comment) → not added
- Test OSError on `path.open` → returns `{}` (lines 131-132)
  - Requires patching `Path.open` to raise `OSError`

---

## Plan 4 — match_filter.py + path_utils.py + podcast_filtering.py ⭐⭐ (Priority 2)

**Effort: Medium | Impact: Medium (covers ~20 lines across 3 files)**

### `src/match_filter.py` — lines 26, 38-41
Add tests to `tests/test_utils.py` or a new `tests/test_match_filter.py`:
- Test `_mf({"availability": "needs_auth"}, False)` → returns `"Skipping: needs_auth"` (line 26)
- Test `_mf({"availability": "scheduled"}, False)` → returns `"Skipping: scheduled"` (line 26)
- Test `_mf(None, False)` → exception path returns `None`, calls `log_exception` (lines 38-41)
  - Pass `None` as `info` to trigger `AttributeError` on `.get()`

### `src/path_utils.py` — lines 88, 93-94, 118, 142-148
Add tests to `tests/test_path_utils.py`:
- Line 88: `resolve_playlist_label({}, "https://youtube.com/playlist?list=PLxxx")` → label uses `playlist-PLxxx`
- Lines 93-94: `resolve_playlist_label({}, "https://youtube.com/user/SomeChannel")` → label derived from URL path segments
- Line 118: `rename_playlist_folders_from_comments("/nonexistent", [...], {"PLxxx": "Name"})` → returns early (base_path missing)
- Lines 142-148: patch `Path.rename` to raise `OSError` → `log_exception` called, no crash

### `src/podcast_filtering.py` — lines 69, 73-74, 97-98, 129-130, 196
Add tests to `tests/test_podcast_filtering.py`:
- Line 69: archive file with blank lines → blank lines skipped, other IDs parsed correctly
- Lines 73-74: patch `Path.open` to raise `OSError` in `load_downloaded_video_ids` → returns empty set
- Lines 97-98: `format_timestamp_readable` with timestamp that triggers `OSError`/`ValueError` → `"(unknown)"`
- Lines 129-130: patch `Path.open` to raise `OSError` in `append_to_archive_and_mark_skipped` → logs exception, message still appended
- Line 196: `_try_parse_datetime("not-a-date", ("%Y-%m-%d",))` → all formats fail → returns `None`

---

## Plan 5 — download_service.py ⭐ (Priority 3)

**Effort: Medium-High | Impact: Low (covers 7 lines in already 95% covered file)**

Add to `tests/test_download_service.py`.

### Lines 110-112: `request_detected` playlist URL loading from file
- Test `request_detected(source="1080playlists", urls=[])` when `_load_playlist_urls` returns a list → those URLs passed to `get_options`
- Requires patching `_load_playlist_urls` or the underlying `load_playlist_urls` utility

### Lines 243, 288-291: `check_live_queue` edge paths
- Line 243: Test `check_live_queue()` when `load_live_queue()` returns `{}` → returns immediately, `save_live_queue` not called
- Lines 288-291: Test that when `yt_dlp.YoutubeDL` raises a `YDL_EXTRACTION_ERRORS` exception, the URL stays in `remaining` and the error is logged via `log_edit_append_callback`

---

## Verification

After implementing each plan, run:
```bash
pytest --cov=src --cov-report=term-missing -q
```
Target: overall coverage ≥ 97% after all plans are implemented.

Run `ruff check src/ tests/` after each plan to ensure Ruff compliance.

## Files to Create/Modify

| Plan | File | Action |
|---|---|---|
| 1 | tests/test_url_utils.py | add tests |
| 1 | tests/test_utils.py | add tests for dict_utils, exceptions |
| 1 | tests/test_logging_utils.py | add test |
| 1 | tests/test_version_utils.py | add tests |
| 2 | tests/test_ydl_options.py | create new |
| 2 | tests/test_ydl_utils.py | create new |
| 3 | tests/test_playlist_utils.py | add tests |
| 4 | tests/test_match_filter.py | create new (or add to test_utils.py) |
| 4 | tests/test_path_utils.py | add tests |
| 4 | tests/test_podcast_filtering.py | add tests |
| 5 | tests/test_download_service.py | add tests |
