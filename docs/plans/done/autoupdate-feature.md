# Plan: App Auto-Update Feature

## Context

The app already auto-checks for yt-dlp updates on startup, but has no mechanism to check for updates to itself. This adds that feature: pressing **Ctrl+U** triggers a background check against GitHub Releases and, if a newer version exists, prompts the user to open the download page. The scope is narrow — no pre-release filtering yet, that is explicitly deferred.

---

## Approach

### Phase 1 — Version constant + API helper (`src/version_utils.py`)

Add three things to the existing `version_utils` module (same file that handles yt-dlp update checking):

```python
APP_VERSION: str = "0.1.0"   # keep in sync with pyproject.toml on each release
_GITHUB_RELEASES_URL = "https://api.github.com/repos/Geneocide/vid-downloader/releases"
_GITHUB_API_TIMEOUT: int = 5
```

Add two new functions:

**`get_latest_app_release() -> dict | None`**  
`GET /releases` (the list endpoint, not `/latest`) so pre-releases are included.  
Returns `releases[0]` (most recent) or `None` on any error.

**`is_app_update_available() -> tuple[bool, str | None, str | None]`**  
Returns `(update_available, latest_tag_name, download_url)`.  
- Compares `normalize_version(APP_VERSION)` against `normalize_version(release["tag_name"])` using the existing helper.  
- `download_url`: first asset `browser_download_url` whose name ends in `.exe`, falling back to `release["html_url"]`.  
- Returns `(False, None, None)` on any API failure — startup must never block on a network error.

### Phase 2 — Background worker + dialog (`vid downloader.pyw`)

**Inner class `_AppUpdateWorker(QObject)`** (nested in `MyWindow`, mirrors `_PodcastCheckWorker`):
```python
finished = pyqtSignal(bool, str, str)  # (update_available, latest_version, download_url)
```
`run()` calls `is_app_update_available()` and emits `finished`.

**`MyWindow._start_app_update_check()`**  
Creates worker + `QThread`, moves worker to thread, connects `thread.started → worker.run`, `worker.finished → self._on_app_update_result`, and `worker.finished → thread.quit`. Stores refs to avoid GC. Starts the thread.

**`MyWindow._on_app_update_result(update_available, latest_version, download_url)`**  
If `update_available`:
```python
answer = QMessageBox.question(
    self,
    "Update Available",
    f"Version {latest_version} is available. Download now?",
)
if answer == QMessageBox.StandardButton.Yes:
    webbrowser.open(download_url)
```

**Wire into `__init__`** — register a keyboard shortcut alongside the existing `Ctrl+H` shortcut:
```python
QShortcut(QKeySequence("Ctrl+U"), self).activated.connect(self._start_app_update_check)
```

### Phase 3 — Tests (`tests/test_version_utils.py`)

Add tests for the new functions following the existing mock-patch style:
- `get_latest_app_release()` — success returns first release; non-200 returns None; network error returns None; empty list returns None.
- `is_app_update_available()` — update detected; already up-to-date; API failure returns `(False, None, None)`; falls back to `html_url` when no `.exe` asset.

---

## Critical Files

| File | Change |
|---|---|
| `src/version_utils.py` | Add `APP_VERSION`, `_GITHUB_RELEASES_URL`, `_GITHUB_API_TIMEOUT`, `get_latest_app_release()`, `is_app_update_available()` |
| `vid downloader.pyw` | Add `_AppUpdateWorker` inner class; add `_start_app_update_check()` and `_on_app_update_result()` to `MyWindow`; call from `__init__` |
| `tests/test_version_utils.py` | Add tests for the two new functions |

## Existing utilities to reuse

- `normalize_version()` in `src/version_utils.py:12` — version tuple comparison
- `_PodcastCheckWorker` pattern in `vid downloader.pyw:745` — worker/thread lifecycle
- `requests` already a dependency; `webbrowser` already imported in main file

## Future hooks (no code needed now)

- Pre-release filter: change `get_latest_app_release()` to skip releases where `release["prerelease"] is True`

---

## Verification

1. Run `uv run pytest tests/test_version_utils.py` — all new tests pass.
2. Run `uv run ruff check src/version_utils.py "vid downloader.pyw"` — no lint errors.
3. Manually: temporarily set `APP_VERSION = "0.0.0"` and launch the app, press Ctrl+U — update dialog appears; clicking Yes opens browser to the installer page; clicking No dismisses silently.
4. Manually: set `APP_VERSION` to the current latest tag and press Ctrl+U — "already up to date" or no dialog appears.
