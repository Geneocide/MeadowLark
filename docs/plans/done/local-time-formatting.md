# Plan: Display Local Time in Logs and UI

## Context
All user-visible timestamps are currently formatted in UTC. The user doesn't understand UTC, so all timestamps shown in logs and the UI should use the local system timezone. Internal UTC usage for scheduling arithmetic is fine and stays as-is.

Python's `logging.basicConfig` `%(asctime)s` already uses local time — only the explicit `get_utc_timestamp()` calls and two UI format strings need fixing.

---

## Changes

### 1. `src/logging_utils.py` — rename & fix the timestamp function

- Rename `get_utc_timestamp()` → `get_local_timestamp()`
- Change implementation:
  ```python
  # Before
  return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
  # After
  return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
  ```
- Remove unused `timezone` import (keep `datetime`)
- Update docstring

### 2. `QYT.py` — update import and call sites

- Line 13: `from src.logging_utils import get_utc_timestamp` → `get_local_timestamp`
- Lines 182, 197: `get_utc_timestamp()` → `get_local_timestamp()`

### 3. `src/podcast_filtering.py` — update import and call site

- Line 16: `from src.logging_utils import get_utc_timestamp` → `get_local_timestamp`
- Line 135: `get_utc_timestamp()` → `get_local_timestamp()`

### 4. `vid downloader.pyw` — fix two display-facing format calls

**Line 1111** — recheck schedule message shown to user:
```python
# Before
datetime.fromtimestamp(scheduled_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
# After
datetime.fromtimestamp(scheduled_ts).astimezone().strftime('%Y-%m-%d %H:%M:%S')
```

**Line 1680** — hourly check schedule message shown to user (`target` is UTC-aware):
```python
# Before
target.strftime('%Y-%m-%d %H:%M:%S')
# After
target.astimezone().strftime('%Y-%m-%d %H:%M:%S')
```

---

## What does NOT change

- Internal UTC timestamps for scheduling arithmetic (`datetime.now(tz=timezone.utc).timestamp()`) in main file lines 1033, 1482, 1672 and `podcast_filter_executor.py:49`
- `podcast_filtering.py` date parsing — upload dates from yt-dlp are stored as UTC for comparison, not display
- Cache TTL using `time.time()` — Unix epoch, timezone-agnostic
- `logging.basicConfig` `%(asctime)s` — already local time

---

## Verification

1. Run the app and trigger a podcast URL recheck → "will recheck at..." message should show local time
2. Trigger a download → check `history_log.txt`, timestamps should match local clock
3. Trigger an error → `error_log.txt` already uses local time via `%(asctime)s`; confirm consistency
4. Run Ruff: `ruff check src/logging_utils.py QYT.py src/podcast_filtering.py "vid downloader.pyw"`

---

## Implementation Notes (completed 2026-04-18)

- All 5 files updated as planned; zero remaining `get_utc_timestamp` references in the codebase.
- Tests in `tests/test_logging_utils.py` updated: class renamed `TestGetLocalTimestamp`, `test_timestamp_is_recent` now brackets with `datetime.now().astimezone()` to match the implementation under test.
- `target.astimezone()` at line 1680 is safe: `target` is always UTC-aware (derived from `datetime.now(tz=timezone.utc).replace(...)`), so `.astimezone()` correctly converts to local time.
- `fromtimestamp(scheduled_ts)` without `tz=` drops explicit UTC anchoring, but for podcast recheck timestamps (always future) negative epoch values never occur, so this is not a live issue.
- Ruff: zero new violations introduced. Pre-existing violations in `QYT.py`, `vid downloader.pyw`, and test files are unrelated to this change.
- DST fall-back ambiguity (fold=0 assumed by `astimezone()`) is benign for logging timestamps.
