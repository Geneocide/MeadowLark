# Refactoring Proposals

Generated 2026-04-17. Each item has an ID, priority score (10 = most impactful), effort estimate, and specific file/line references.

Pick items by ID and ask Claude to implement them one at a time.

---

## Priority 10 — Critical Duplicates

### [R01] `make_match_filter()` defined identically in two modules
**Effort:** Low | **Files:** `vid downloader.pyw:761–796`, `src/download_service.py:237–274`

The entire function — including the inner closure, all live/upcoming skip logic, and exception handling — is copy-pasted between the main file and the service. Any bug fix must be applied twice.

**Action:** Extract to `src/match_filter.py` as a standalone factory function; import and call it in both modules.

---

### [R02] Hardcoded paths scattered across 6+ locations
**Effort:** Low | **Files:** `vid downloader.pyw:559,610,1525,1659`, `src/download_service.py:172,205`, `src/ydl_options.py:64,73,85,97,123`

`C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt`, `E:/vid storage/`, and the podcast base dir all appear hardcoded in multiple files. Any path change requires hunting across the codebase.

**Action:** Move all to `src/config.py` as named constants: `ARCHIVE_PATH`, `PODCAST_BASE_DIR`, `VIDEO_STORAGE_DIR`, `AUDIO_OUTPUT_DIR`. Update all references.

---

## Priority 9 — High-Impact Duplication

### [R03] Archive ID reading reimplemented in `download_service.py`
**Effort:** Low | **Files:** `src/download_service.py:207–213`, `src/podcast_filtering.py:65–77`

`download_service.py` re-implements the archive file parsing inline (splitting on whitespace, taking last token). `podcast_filtering.py` already has `load_downloaded_video_ids()` that does the same thing correctly.

**Action:** Replace the inline block in `download_service.py` with a call to `load_downloaded_video_ids()` from `podcast_filtering.py`.

---

### [R04] URL parsing for playlist ID duplicated 3×
**Effort:** Low | **Files:** `src/path_utils.py:86–89`, `src/path_utils.py:125–129`, `src/playlist_utils.py:109–112`

The same `urlparse` + `parse_qs` + `qs.get("list")` pattern appears three times across two modules.

**Action:** Extract `extract_playlist_id(url: str) -> str | None` into `src/url_utils.py`; update all three call sites.

---

### [R05] QHook/QLogger/ydl_opts initialization repeated 6+ times
**Effort:** Medium | **Files:** `vid downloader.pyw:505–506, 557, 861–862, 1379–1380, 1542–1543, 1556–1557`

Every download trigger independently creates `QHook`, `QLogger`, and calls `build_base_ydl_opts()`. Signal connections vary slightly, making them hard to audit.

**Action:** Extract `_create_download_context() -> tuple[QHook, QLogger, dict]` on the main class; call it from all six sites.

---

## Priority 8 — Structural Improvements

### ~~[R06] Live queue load/save/add logic duplicated across two files~~ ✅ DONE
**Effort:** Medium | **Files:** `src/live_queue.py` (new), `vid downloader.pyw`, `src/download_service.py`

Extracted to `src/live_queue.py` as standalone functions with `LiveQueueEntries` type alias. Both classes are now one-line wrappers. Tests added in `tests/test_live_queue.py`.

---

### [R07] `_filter_audio_playlist_urls()` is 203 lines — noqa'd for complexity
**Effort:** High | **File:** `vid downloader.pyw:894–1096`

Suppresses `C901`, `PLR0912`, `PLR0915`. The function does archive checking, title filtering, duration gating, SponsorBlock timestamp logic, and status dict construction all in one loop.

**Action:** Extract four helpers:
- `_check_video_archived(vid_id, existing_ids) -> bool`
- `_skip_update_episode(title) -> bool`
- `_skip_short_duration(entry, min_seconds) -> bool`
- `_evaluate_episode_download_status(entry, ...) -> tuple[bool, str, str | None]`

---

### [R08] `_on_podcast_check_finished()` is 163 lines — noqa'd for complexity
**Effort:** High | **File:** `vid downloader.pyw:1435–1597`

Suppresses `C901`, `PLR0912`, `PLR0913`, `PLR0915`. Signal connections (`qhook.info_changed.connect`, `qlogger.message_changed.connect`) are duplicated at lines 1549 and 1562 inside separate branches.

**Action:** Extract:
- `_process_podcast_statuses(statuses) -> None`
- `_queue_podcast_downloads_grouped(to_download, ydl_opts) -> None`
- `_queue_podcast_downloads_flat(to_download, ydl_opts) -> None`
- `_update_podcast_indicator_from_results(had_error, to_download, pending) -> None`

---

## Priority 7 — Moderate Duplication

### [R09] Two fallback retry methods share identical structure
**Effort:** Medium | **File:** `src/download_executor.py:63–154`

`_try_720_fallback()` (lines 63–110) and `_try_without_sponsorblock()` (lines 112–154) both check a "tried" flag, modify options, execute download, and call `utils.log_exception()` on failure. ~90 lines collapse to ~50.

**Action:** Extract `_try_fallback(flag_attr, options_modifier, urls, options, title, error_str) -> tuple[bool, str]`; delegate both methods to it.

---

### [R10] Cache clearing before download repeated 4×
**Effort:** Low | **File:** `src/download_executor.py:105,106,148,173`

`ydl.cache.remove()` is called immediately before every `ydl.download()` call across three code paths.

**Action:** Extract `_clear_cache_and_download(ydl, urls) -> None` helper; call from all four sites.

---

### [R11] YoutubeDL quiet opts dict repeated twice in `ydl_utils.py`
**Effort:** Low | **File:** `src/ydl_utils.py:24,49`

`{"quiet": True, "no_warnings": True}` is constructed inline in two functions in the same module.

**Action:** Add `_QUIET_YDL_OPTS: dict[str, bool] = {"quiet": True, "no_warnings": True}` as a module constant; reference it in both functions.

---

### [R12] Playlist file loading inconsistent between two modules
**Effort:** Medium | **Files:** `src/playlist_utils.py:99–119`, `src/download_service.py:142–145`

`playlist_utils.py` loads playlist files with comment support; `download_service.py` does a simpler line-by-line read with no comment handling.

**Action:** Unify in `src/playlist_utils.py` as `load_playlist_file(path, include_comments=False) -> dict[str, str] | list[str]`; update `download_service.py` to call it.

---

### [R13] Podcast status dict constructed inline 6+ times
**Effort:** Low | **File:** `vid downloader.pyw:942–945, 1073–1076, 1089–1092, 1682–1685, 1736–1742, 1753–1756`

The same four-key dict (`podcast`, `latest_date`, `status`, `url`) is built from scratch each time with varying default values, making it easy to miss a key when adding new fields.

**Action:** Add `_make_podcast_status_entry(podcast, url, status="(unknown)", latest_date="(unknown)", **kwargs) -> dict` helper method.

---

## Priority 6 — Moderate Long Functions

### [R14] `DownloadExecutor.execute()` mixes three concerns in 99 lines
**Effort:** Medium | **File:** `src/download_executor.py:155–253`

Download execution, post-download folder renaming, and error-based fallback selection are all interleaved.

**Action:** Extract `_extract_base_output_dir(options) -> str | None` and `_rename_na_folder_if_needed(options, urls) -> None`; `execute()` becomes ~40 lines of orchestration.

---

### [R15] `_get_podcast_statuses()` near-duplicates `_filter_audio_playlist_urls()` logic
**Effort:** High | **File:** `vid downloader.pyw:1637–1759`

123 lines of status-determination logic that overlaps heavily with `_filter_audio_playlist_urls()` (lines 894–1096). May be dead code or an older version of the same flow.

**Action:** First, determine whether this method is reachable. If dead, delete it. If live, factor the shared logic into the helpers from R07 and call them from both methods.

---

### [R16] `_open_url_in_browser()` has 3-level nested try/except
**Effort:** Low | **File:** `vid downloader.pyw:1288–1332`

45 lines of nested exception handling for default browser → Brave fallback → manual Brave path registration.

**Action:** Extract `_try_open_in_default_browser(url) -> bool` and `_get_brave_browser_controller() -> BaseBrowser | None`; top-level method becomes a clean 10-line orchestrator.

---

## Priority 5 — Ruff / Type Hint Issues

### [R17] Bare `except Exception` without suppression in `podcast_helpers.py`
**Effort:** Low | **File:** `src/podcast_helpers.py:65`

Unlike other broad exception catches that have `# noqa: BLE001`, this one is undecorated and will be flagged by Ruff.

**Action:** Replace with `except (DownloadError, ExtractorError, OSError) as exc:` (or add `# noqa: BLE001` with a comment explaining why broad catch is needed).

---

### [R18] `_default_postprocessors()` is a function that always returns the same constant
**Effort:** Low | **File:** `src/dict_utils.py:41–53`

The function constructs and returns the same list every time with no parameters.

**Action:** Replace with `DEFAULT_POSTPROCESSORS: list[dict[str, Any]] = [{"key": "SponsorBlock"}, {"key": "ModifyChapters", ...}]` at module level; update call sites.

---

### [R19] `Any` type hints on `logger`/`qhook` params lack protocol or noqa
**Effort:** Medium | **File:** `src/ydl_options.py:21,26`

`build_base_ydl_opts(logger: Any, qhook: Any)` is too broad — Ruff's ANN401 will flag this. These objects have known shapes.

**Action:** Define a minimal `QLogger` / `QHook` Protocol in `src/qt_types.py` (or use the actual class types); replace `Any` with the protocol.

---

### [R20] Unused `# type: ignore` comment in test
**Effort:** Low | **File:** `tests/test_utils.py:25`

```python
assert normalize_version(None) == ()  # type: ignore
```

**Action:** Either add a `@overload` for `normalize_version(None)` returning `tuple[()]`, or remove the comment if the type checker no longer requires it.

---

## Priority 4 — Dead Code

### [R21] Commented-out `is_firefox_running()` and Firefox launch block
**Effort:** Low | **File:** `vid downloader.pyw:1830–1847`

References `psutil` which is not imported — would fail immediately if uncommented. Has clearly been superseded.

**Action:** Delete lines 1830–1847 entirely.

---

### [R22] Commented-out duplicate signal connection
**Effort:** Low | **File:** `vid downloader.pyw:550`

```python
# qlogger.message_changed.connect(self.logEdit.appendPlainText)
```

The active line immediately below does the same thing.

**Action:** Delete line 550.

---

## Priority 3 — Minor Quality Issues

### [R23] Magic numbers in `version_utils.py`
**Effort:** Low | **File:** `src/version_utils.py:50–51`

`timeout=3` and `status_code == 200` are bare literals with no explanation.

**Action:** Add `_PYPI_API_TIMEOUT: int = 3` and use `http.HTTPStatus.OK` (or `200`) with a named constant.

---

### [R24] Broken docstring in `podcast_helpers.py`
**Effort:** Low | **File:** `src/podcast_helpers.py:13–19`

The docstring for `fetch_latest_accessible_entry()` has an orphan `"."` as its summary line.

**Action:** Replace with a real one-line summary.

---

### [R25] `DownloadService.get_options()` mixes five concerns in 37 lines
**Effort:** Medium | **File:** `src/download_service.py:147–184`

Validates skip callback, builds base properties, conditionally adds archive path, registers match filter for YouTube, and strips URL parameters — all in sequence with no helper calls.

**Action:** Extract `_add_archive_if_needed(properties)`, `_prepare_youtube_urls(urls) -> list[str]`, `_add_match_filter_for_youtube(properties, source)`.

---

## Quick Reference Table

| ID  | Priority | Effort | Category               |
|-----|----------|--------|------------------------|
| R01 | 10       | Low    | Critical duplicate     |
| R02 | 10       | Low    | Hardcoded paths        |
| R03 | 9        | Low    | Duplicate logic        |
| R04 | 9        | Low    | Duplicate logic        |
| R05 | 9        | Medium | Repeated init pattern  |
| ~~R06~~ | 8        | Medium | Structural ✅          |
| R07 | 8        | High   | Long function          |
| R08 | 8        | High   | Long function          |
| R09 | 7        | Medium | Duplicate structure    |
| R10 | 7        | Low    | Duplicate pattern      |
| R11 | 7        | Low    | Duplicate literal      |
| R12 | 7        | Medium | Inconsistent loading   |
| R13 | 7        | Low    | Duplicate construction |
| R14 | 6        | Medium | Long function          |
| R15 | 6        | High   | Long / possibly dead   |
| R16 | 6        | Low    | Long function          |
| R17 | 5        | Low    | Ruff violation         |
| R18 | 5        | Low    | Type / style           |
| R19 | 5        | Medium | Type hints             |
| R20 | 5        | Low    | Unused annotation      |
| R21 | 4        | Low    | Dead code              |
| R22 | 4        | Low    | Dead code              |
| R23 | 3        | Low    | Magic numbers          |
| R24 | 3        | Low    | Docstring              |
| R25 | 3        | Medium | Long function          |
