# Refactoring Proposals

Generated 2026-04-17. Each item has an ID, priority score (10 = most impactful), effort estimate, and specific file/line references.

Pick items by ID and ask Claude to implement them one at a time.

---

## Priority 10 — Critical Duplicates

### ~~[R01] `make_match_filter()` defined identically in two modules~~ ✅ DONE
**Effort:** Low | **Files:** `src/match_filter.py` (new), `vid downloader.pyw`, `src/download_service.py`

Extracted to `src/match_filter.py` as `build_match_filter()` factory accepting `add_to_queue_fn` and `log_fn` callbacks. Both classes are now 5-line wrappers. 238 tests pass.

---

### ~~[R02] Hardcoded paths scattered across 6+ locations~~ ✅ DONE
**Effort:** Low | **Files:** `vid downloader.pyw:559,610,1525,1659`, `src/download_service.py:172,205`, `src/ydl_options.py:64,73,85,97,123`

Added `ARCHIVE_PATH`, `PODCAST_MISC_OUTPUT_DIR`, and `VIDEO_STORAGE_DIR` to `src/config.py` with env-var override support (`VID_DL_ARCHIVE_PATH`, `VID_DL_PODCAST_MISC_OUTPUT_DIR`, `VID_DL_VIDEO_STORAGE_DIR`). All 14 hardcoded path strings replaced. Used `.as_posix()` for outtmpl strings to preserve forward-slash separators. 238 tests pass.

---

## Priority 9 — High-Impact Duplication

### ~~[R03] Archive ID reading reimplemented in `download_service.py`~~ ✅ DONE
**Effort:** Low | **Files:** `src/download_service.py:207–213`, `src/podcast_filtering.py:65–77`

Replaced 7-line inline archive-reading block in `skip_downloading` with a single call to `load_downloaded_video_ids(str(ARCHIVE_PATH))`. Added import from `src.podcast_filtering`. The canonical function already handles `OSError`, `UnicodeDecodeError`, and missing files. 17 tests pass.

---

### ~~[R04] URL parsing for playlist ID duplicated 3×~~ ✅ DONE
**Effort:** Low | **Files:** `src/path_utils.py:86–89`, `src/path_utils.py:125–129`, `src/playlist_utils.py:109–112`

Created `src/url_utils.py` with `extract_playlist_id(url: str) -> str | None`. Updated all three call sites in `path_utils.py` (`resolve_playlist_label`, `rename_playlist_folders_from_comments`) and `playlist_utils.py` (`load_playlist_comments_for_source`). Removed `parse_qs` import from both files; `urlparse` retained in `path_utils.py` for path-segment fallback. Added `tests/test_url_utils.py` with 5 tests. 17 tests pass.

---

### ~~[R05] QHook/QLogger/ydl_opts initialization repeated 6+ times~~ ✅ DONE
**Effort:** Medium | **Files:** `vid downloader.pyw:505–506, 557, 861–862, 1379–1380, 1542–1543, 1556–1557`

Added `_create_download_context()`, `_fork_download_context(base_opts)`, and `_wire_download_signals(qhook, qlogger)` to `MyWindow` near the live-queue helpers. Updated all five call sites: `request_detected`, `check_live_queue`, `_download_podcast_now_action`, and both branches of `_on_podcast_check_finished`. 243 tests pass.

---

## Priority 8 — Structural Improvements

### ~~[R06] Live queue load/save/add logic duplicated across two files~~ ✅ DONE
**Effort:** Medium | **Files:** `src/live_queue.py` (new), `vid downloader.pyw`, `src/download_service.py`

Extracted to `src/live_queue.py` as standalone functions with `LiveQueueEntries` type alias. Both classes are now one-line wrappers. Tests added in `tests/test_live_queue.py`.

---

### ~~[R07] `_filter_audio_playlist_urls()` is 203 lines — noqa'd for complexity~~ ✅ DONE
**Effort:** High | **File:** `vid downloader.pyw:894–1096`

Extracted 4 helpers on `MyWindow`: `_episode_already_archived`, `_skip_if_update_episode` (noqa PLR0913), `_skip_if_short_duration` (noqa PLR0913), `_classify_episode_by_age` (keyword-only bool, noqa PLR0913). Removed `# noqa: C901,PLR0912,PLR0915` from `_filter_audio_playlist_urls`. `_cache_put` signature widened to `str | None`. Updated `DummyWin` in `tests/test_private_video_handling.py` to borrow new methods from `MyWindow`. 243 tests pass.

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

### ~~[R10] Cache clearing before download repeated 4×~~ ✅ DONE
**Effort:** Low | **File:** `src/download_executor.py:105,106,148,173`

Added `_download_with_cache_clear(opts, urls)` to `DownloadExecutor`; collapsed the 3-line `with YoutubeDL / cache.remove / download` pattern in `_try_720_fallback`, `_try_without_sponsorblock`, and `execute` to single-line calls. 243 tests pass.

---

### ~~[R11] YoutubeDL quiet opts dict repeated twice in `ydl_utils.py`~~ ✅ DONE
**Effort:** Low | **File:** `src/ydl_utils.py:24,49`

Added `_QUIET_YDL_OPTS: dict[str, bool] = {"quiet": True, "no_warnings": True}` as a module constant; updated both `extract_playlist_info` and `extract_video_entries` to spread it. 243 tests pass.

---

### [R12] Playlist file loading inconsistent between two modules
**Effort:** Medium | **Files:** `src/playlist_utils.py:99–119`, `src/download_service.py:142–145`

`playlist_utils.py` loads playlist files with comment support; `download_service.py` does a simpler line-by-line read with no comment handling.

**Action:** Unify in `src/playlist_utils.py` as `load_playlist_file(path, include_comments=False) -> dict[str, str] | list[str]`; update `download_service.py` to call it.

---

### ~~[R13] Podcast status dict constructed inline 6+ times~~ ✅ DONE
**Effort:** Low | **File:** `vid downloader.pyw:942–945, 1073–1076, 1089–1092, 1682–1685, 1736–1742, 1753–1756`

Added `_make_podcast_status_entry(podcast, url, status, latest_date, **kwargs)` as a module-level function (not a method — tests use `DummyWin` mocks that don't inherit `MyWindow`). All 6 inline dict literals replaced. 243 tests pass.

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

### ~~[R16] `_open_url_in_browser()` has 3-level nested try/except~~ ✅ DONE
**Effort:** Low | **File:** `vid downloader.pyw:1288–1332`

Extracted `_try_open_default_browser(url, label) -> bool` and `_get_brave_controller() -> BaseBrowser | None`. Added `_BRAVE_PATHS: ClassVar[list[str]]` class constant; added `ClassVar` import. `_open_url_in_browser` reduced from 45 lines / 3 nesting levels to 12 lines / 1 level. 243 tests pass.

---

## Priority 5 — Ruff / Type Hint Issues

### ~~[R17] Bare `except Exception` without suppression in `podcast_helpers.py`~~ ✅ DONE
**Effort:** Low | **File:** `src/podcast_helpers.py:65`

No change needed: Ruff's BLE001 does not fire because the except block unconditionally re-raises non-private-video errors — the exception is never swallowed. Adding a noqa produced RUF100 (unused). File is Ruff-clean. 243 tests pass.

---

### ~~[R18] `_default_postprocessors()` is a function that always returns the same constant~~ ✅ DONE
**Effort:** Low | **File:** `src/dict_utils.py:41–53`

Replaced function with `DEFAULT_POSTPROCESSORS: list[dict[str, Any]]` constant. Updated import and 3 call sites in `src/ydl_options.py` to use `list(DEFAULT_POSTPROCESSORS)`; updated `utils.py` import and `__all__`. Also sorted `__all__` to fix a surfaced RUF022. 243 tests pass.

---

### [R19] `Any` type hints on `logger`/`qhook` params lack protocol or noqa
**Effort:** Medium | **File:** `src/ydl_options.py:21,26`

`build_base_ydl_opts(logger: Any, qhook: Any)` is too broad — Ruff's ANN401 will flag this. These objects have known shapes.

**Action:** Define a minimal `QLogger` / `QHook` Protocol in `src/qt_types.py` (or use the actual class types); replace `Any` with the protocol.

---

### ~~[R20] Unused `# type: ignore` comment in test~~ ✅ DONE
**Effort:** Low | **File:** `tests/test_utils.py:25`

Widened `normalize_version` signature to `str | None` in `src/version_utils.py` (body already handled non-strings). Removed `# type: ignore` from the test. 243 tests pass.

---

## Priority 4 — Dead Code

### ~~[R21] Commented-out `is_firefox_running()` and Firefox launch block~~ ✅ DONE
**Effort:** Low | **File:** `vid downloader.pyw:1830–1847`

Deleted the commented-out `is_firefox_running()` function definition and Firefox `subprocess.Popen` launch block. 243 tests pass.

---

### ~~[R22] Commented-out duplicate signal connection~~ ✅ DONE
**Effort:** Low | **File:** `vid downloader.pyw:550`

Deleted the commented-out duplicate `qlogger.message_changed.connect(self.logEdit.appendPlainText)` line. 243 tests pass.

---

## Priority 3 — Minor Quality Issues

### ~~[R23] Magic numbers in `version_utils.py`~~ ✅ DONE
**Effort:** Low | **File:** `src/version_utils.py:50–51`

Added `_PYPI_API_TIMEOUT: int = 3` constant and replaced `timeout=3` / `status_code == 200` with `timeout=_PYPI_API_TIMEOUT` / `http.HTTPStatus.OK`. Also removed pre-existing `# noqa: PLR2004` that was suppressing the magic-number warning. 243 tests pass.

---

### ~~[R24] Broken docstring in `podcast_helpers.py`~~ ✅ DONE
**Effort:** Low | **File:** `src/podcast_helpers.py:13–19`

Replaced orphan `"."` summary line with `"Fetch the latest accessible (non-private) entry from a playlist URL."` Done alongside R17. 243 tests pass.

---

### [R25] `DownloadService.get_options()` mixes five concerns in 37 lines
**Effort:** Medium | **File:** `src/download_service.py:147–184`

Validates skip callback, builds base properties, conditionally adds archive path, registers match filter for YouTube, and strips URL parameters — all in sequence with no helper calls.

**Action:** Extract `_add_archive_if_needed(properties)`, `_prepare_youtube_urls(urls) -> list[str]`, `_add_match_filter_for_youtube(properties, source)`.

---

## Quick Reference Table

| ID  | Priority | Effort | Category               |
|-----|----------|--------|------------------------|
| ~~R01~~ | 10       | Low    | Critical duplicate ✅  |
| ~~R02~~ | 10       | Low    | Hardcoded paths ✅     |
| ~~R03~~ | 9        | Low    | Duplicate logic ✅     |
| ~~R04~~ | 9        | Low    | Duplicate logic ✅     |
| ~~R05~~ | 9        | Medium | Repeated init pattern ✅ |
| ~~R06~~ | 8        | Medium | Structural ✅          |
| ~~R07~~ | 8        | High   | Long function ✅       |
| R08 | 8        | High   | Long function          |
| R09 | 7        | Medium | Duplicate structure    |
| ~~R10~~ | 7        | Low    | Duplicate pattern ✅   |
| ~~R11~~ | 7        | Low    | Duplicate literal ✅   |
| R12 | 7        | Medium | Inconsistent loading   |
| ~~R13~~ | 7        | Low    | Duplicate construction ✅ |
| R14 | 6        | Medium | Long function          |
| R15 | 6        | High   | Long / possibly dead   |
| ~~R16~~ | 6        | Low    | Long function ✅       |
| ~~R17~~ | 5        | Low    | Ruff violation ✅      |
| ~~R18~~ | 5        | Low    | Type / style ✅        |
| R19 | 5        | Medium | Type hints             |
| ~~R20~~ | 5        | Low    | Unused annotation ✅   |
| ~~R21~~ | 4        | Low    | Dead code ✅           |
| ~~R22~~ | 4        | Low    | Dead code ✅           |
| ~~R23~~ | 3        | Low    | Magic numbers ✅       |
| ~~R24~~ | 3        | Low    | Docstring ✅           |
| R25 | 3        | Medium | Long function          |
