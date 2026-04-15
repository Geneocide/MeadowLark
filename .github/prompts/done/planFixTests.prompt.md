## Plan: Fix test failures for podcast helpers and QYT tests

TL;DR: Adjust podcast exception handling and SponsorBlock error handling, fix test fixture/patch-target mismatches, and clear stale pytest cache before re-running the relevant tests.

**Steps**
1. Modify `src/podcast_filtering.py`:
   - Broaden `check_sponsorblock_for_video_id()` exception handling so any SponsorBlock API failure is caught and logged, and the function returns `False`.
   - Keep behavior unchanged for successful API responses.

2. Modify `src/podcast_helpers.py`:
   - Update `fetch_latest_accessible_entry()` so that when all lookahead retries fail due to private-video conditions, it raises `PodcastResolutionError` instead of re-raising the original private-video exception.
   - Preserve existing behavior for non-private errors by continuing to propagate them immediately.

3. Fix tests in `tests/test_private_video_handling.py`:
   - Correct the dummy `YoutubeDL` stub in `test_fetch_latest_accessible_entry_no_accessible` to inspect `playlist_items` instead of `playlistend`, matching the actual implementation.

4. Fix tests in `tests/test_qyt.py`:
   - Change `@patch("HistoryLogger.HISTORY_PATH")` to patch the real symbol used by `QYT`, such as `@patch("QYT.HistoryLogger.HISTORY_PATH")`.
   - Change `@patch("HistoryLogger.log")` to patch `QYT.HistoryLogger.log`.
   - Ensure the tests patch the symbol used by `HistoryHook.__call__`, not only the local test module import.

5. Clean stale pytest cache and rerun tests:
   - Remove `.pytest_cache` or at least `.pytest_cache/v/cache/*` so old missing-file metadata does not confuse the next run.
   - Re-run the targeted test files after the fixes.

**Relevant files**
- `src/podcast_filtering.py`
- `src/podcast_helpers.py`
- `tests/test_private_video_handling.py`
- `tests/test_qyt.py`
- `.pytest_cache` (cleanup)

**Verification**
1. Run `pytest tests/test_podcast_filtering.py tests/test_podcast_helpers.py tests/test_private_video_handling.py tests/test_qyt.py tests/test_ui_classes.py`.
2. Confirm `check_sponsorblock_for_video_id()` returns `False` on generic SponsorBlock failure without raising.
3. Confirm `fetch_latest_accessible_entry()` raises `PodcastResolutionError` when only private entries are encountered and lookahead is exhausted.
4. Confirm `tests/test_qyt.py` history-hook patching works and the related tests pass.
5. If `.pytest_cache` still contains unreachable stale entries, delete the cache and rerun.

**Decisions**
- No user-visible app functionality changes are planned beyond making the app more robust and aligning tests with existing behavior.
- Obsolete tests are not deleted unless they are proven to be stale and actually absent from the repository after cache cleanup.

**Further considerations**
1. If `tests/test_live_queue.py` or `tests/test_podcast_outtmpl_substitution.py` still appear in failure metadata but are absent from the repo, the problem is stale cache rather than code.
2. If any UI test still fails after code fixes, the issue may be test-environment initialization rather than application logic.
