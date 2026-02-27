# Feature Plan: Right-Click to Open Latest Video from Podcast Status

---

## Summary
Add a right-click context menu to the Podcast Status dialog’s table that opens the latest episode for the selected podcast in a new browser tab. Default to the system’s default browser via Python’s `webbrowser` module and fall back to Brave if needed.

Additionally, introduce an in-memory (optionally persisted) cache of each podcast’s latest video URL so the context menu can open the latest episode without invoking yt-dlp every time.

---

## Current State Recap (from code)
- The Podcast Status UI is implemented in `vid downloader.pyw` in `MyWindow._show_podcast_status()` and `_refresh_podcast_status_dialog()`.
- Status dialog is a non-modal `QDialog` with a `QTableWidget` (`self._podcast_status_table`) showing columns: Podcast, Latest Episode (date/time), Status.
- The code caches statuses in `self._podcast_last_statuses`, each status item shaped like:
  ```python
  {
      "podcast": <playlist_label or title>,
      "latest_date": <str | "(unknown)">,
      "status": <"Ready" | "Pending SponsorBlock" | "Downloaded" | "Upcoming" | "Error: ...">,
      "url": <playlist_url>,
      # optionally: "recheck_ts": <epoch seconds>
  }
  ```
- For YT Podcasts, `_filter_audio_playlist_urls` resolves the latest entry to decide status, but the status objects cached in `_podcast_last_statuses` store the playlist/feed URL, not the latest video URL.

---

## Scope of Change
- Add a right-click (context) menu to the Podcast Status `QTableWidget`.
- Provide one menu action: "Open Latest Video in Browser".
- Resolve the latest episode URL for the selected podcast row when the action is triggered.
- Open the URL in a new tab in the default browser (via `webbrowser.open_new_tab`). If that returns False or raises, try Brave explicitly.
- Implement a **Latest-URL Cache** used by the context menu to avoid invoking yt-dlp on every right-click.

---

## Design Decisions
1. Context-menu integration approach:
   - Set `setContextMenuPolicy(Qt.CustomContextMenu)` on `self._podcast_status_table`.
   - Connect `customContextMenuRequested` to a handler (e.g., `_on_podcast_status_context_menu`).
   - Determine the row via `table.indexAt(pos)` and only enable the action if the index is valid.

2. How to obtain the latest video URL for a podcast row (non-cached path):
   - Reuse yt-dlp on demand with a lightweight extraction to get only the first/latest entry from the playlist:
     ```python
     with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "playlistend": 1}) as ydl:
         info = ydl.extract_info(playlist_url, download=False)
     entry = (info.get("entries") or [info])[0]
     latest_url = entry.get("webpage_url") or entry.get("url")
     ```
   - Edge cases:
     - If entries are empty: show a non-intrusive message in the log and do nothing.
     - If yt-dlp raises (private/deleted/upcoming): show a message in the log.

3. Browser-opening strategy:
   - Primary: `webbrowser.open_new_tab(latest_url)`.
   - Fallback to Brave if above returns False or raises:
     - Try `webbrowser.get("brave")` or register Brave common Windows paths if needed, e.g.:
       - `C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe` or `C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe`.
     - Call controller’s `open_new_tab(latest_url)`.
   - Log success/failure to `self.logEdit` for transparency.

4. Minimal UI feedback:
   - If no selection or invalid row: no-op.
   - If resolving latest URL fails: append a log line with the podcast label and reason.

---

## Latest-URL Cache: Design & Integration

### Objectives
- Avoid invoking yt-dlp on each right-click by caching the latest video’s URL for each podcast (playlist URL).
- Keep cache coherent with the data already gathered during background checks.
- Provide simple invalidation to prevent stale URLs when a new episode lands.

### Data Model
- Add an attribute to `MyWindow`:
  ```python
  self._podcast_latest_url_cache: dict[str, dict] = {}
  # maps playlist_url -> {"latest_url": str, "latest_ts": int|None, "fetched_at": float}
  ```
- Keys:
  - `latest_url`: The resolved URL of the latest episode’s webpage (YouTube/Nebula/etc.).
  - `latest_ts`: Upload/publish timestamp for the latest episode when known; else `None`.
  - `fetched_at`: `time.time()` (float epoch seconds) when this cache entry was computed.

### Population Points
- In `_filter_audio_playlist_urls(...)` (runs in a worker):
  - When resolving the latest entry for a playlist, attach the `latest_url` and `ts` to the `statuses` item for that podcast, e.g. `status_entry["latest_url"] = webpage` and `status_entry["latest_ts"] = ts`.
  - Return these enriched `statuses` to the main thread.
- In `_on_podcast_check_finished(...)` (main thread):
  - Iterate over `statuses` and update `self._podcast_latest_url_cache[url]` accordingly.
- In `_get_podcast_statuses(...)` (on-demand status build):
  - When resolving the latest entry for a playlist, also compute `latest_url` and `ts` and add those to the returned status dict.
  - Immediately update the cache with this information.

### Read Path (Context Menu)
- Handler should:
  - Map selected row to `status = self._podcast_last_statuses[row]`.
  - If `status.get("latest_url")` is present, use it directly.
  - Else, attempt to look up `self._podcast_latest_url_cache[playlist_url]["latest_url"]`.
  - If still missing or stale, fall back to the lightweight yt-dlp resolve, then populate the cache.

### Invalidation Rules
- Time-based TTL: Consider entries stale after 6 hours (configurable constant), e.g., `CACHE_TTL_SECONDS = 6*60*60`.
- Event-based:
  - If a new `latest_ts` is discovered that is greater than the cached `latest_ts`, overwrite cache immediately.
  - When `status` equals `Downloaded` with a different `latest_ts` than cached, overwrite cache.
  - On explicit scheduled recheck (via `recheck_ts`), overwrite cache during status refresh.

### Optional Persistence (Future)
- Persist the cache to disk (e.g., `resources/podcast_latest_cache.json`) on successful status updates and load on startup.
- Keep persistence optional initially to avoid complexity; in-memory-only cache is sufficient for first iteration.

---

## Step-by-Step Implementation Plan

1. Wire up the context menu on the Podcast Status table
   - In both `_show_podcast_status` and `_refresh_podcast_status_dialog` (where the table is created), after `table` is instantiated:
     - Call `table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)`.
     - Connect `table.customContextMenuRequested.connect(self._on_podcast_status_context_menu)`.
     - Store table reference as `self._podcast_status_table` (already done); ensure it’s set after creating table.

2. Implement the context menu handler `_on_podcast_status_context_menu(self, pos: QPoint)` in `MyWindow`
   - Guard: if `self._podcast_status_table` is None, return.
   - Calculate the index via `index = table.indexAt(pos)` and `row = index.row()`; if invalid, return.
   - Create a `QMenu` and add `QAction("Open Latest Video in Browser")`.
   - On action triggered, call a resolver method with the row’s status object.

3. Introduce Latest-URL Cache
   - Add `self._podcast_latest_url_cache = {}` in `MyWindow.__init__`.
   - Define constants: `CACHE_TTL_SECONDS = 6*60*60`.
   - Utility helpers:
     - `_cache_put(playlist_url, latest_url, latest_ts)` -> writes/updates cache with current `fetched_at`.
     - `_cache_get_fresh(playlist_url)` -> returns cached `latest_url` if present and not stale, else `None`.

4. Enrich existing status generation to carry latest_url/ts
   - In `_filter_audio_playlist_urls`: when computing `status_entry` per podcast, set `status_entry["latest_url"] = webpage` and `status_entry["latest_ts"] = ts` for the latest entry evaluated (when available).
   - In `_get_podcast_statuses`: similarly compute `latest_url` from `latest.get("webpage_url") or latest.get("url")` and set `status_entry["latest_url"]` and `status_entry["latest_ts"] = ts`.

5. Update main-thread completion to sync cache
   - In `_on_podcast_check_finished`, after storing `self._podcast_last_statuses`:
     - For each status `s`, extract `u = s.get("url")`, `lu = s.get("latest_url")`, `lts = s.get("latest_ts")`.
     - If `lu`: `_cache_put(u, lu, lts)`.

6. Update the context-menu opener to use the cache first
   - Resolver logic: try `status.get("latest_url")` -> if falsy, try `_cache_get_fresh(playlist_url)` -> if falsy, do lightweight yt-dlp resolve and then `_cache_put`.

7. Keep threading simple (synchronous call)
   - The extraction should be fast because it only fetches metadata for a single latest entry. If this proves slow, we can later move resolution to a small worker thread.

8. Testing checklist / success criteria
   - Right-click on any row in Podcast Status opens a context menu with the new action.
   - First invocation (no cache yet) performs yt-dlp resolve, opens in the default browser or Brave, and populates the cache.
   - Subsequent invocations (within TTL) skip yt-dlp and open instantly using the cache.
   - On new episode release (later timestamp), the cache is updated when statuses refresh.
   - Errors and non-actionable states are logged in the application’s log area without crashing the UI.
   - No interference with existing podcast check timers or downloads.

---

## Pseudocode / Code Sketches

- Wiring (done where table is created):
```python
# after creating `table` in _show_podcast_status and _refresh_podcast_status_dialog
table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
table.customContextMenuRequested.connect(self._on_podcast_status_context_menu)
self._podcast_status_table = table
```

- Cache helpers:
```python
import time

def _cache_put(self, playlist_url: str, latest_url: str, latest_ts: int | None) -> None:
    if not playlist_url or not latest_url:
        return
    self._podcast_latest_url_cache[playlist_url] = {
        "latest_url": latest_url,
        "latest_ts": latest_ts,
        "fetched_at": time.time(),
    }

CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 hours

def _cache_get_fresh(self, playlist_url: str) -> str | None:
    e = self._podcast_latest_url_cache.get(playlist_url)
    if not e:
        return None
    # Time-based TTL
    if (time.time() - e.get("fetched_at", 0)) > CACHE_TTL_SECONDS:
        return None
    return e.get("latest_url")
```

- Enrich status generation with latest_url/ts (in worker and on-demand):
```python
# in _filter_audio_playlist_urls (for each podcast)
status_entry = {
    "podcast": playlist_label,
    "latest_date": "(unknown)",
    "status": "(unknown)",
    "url": url,
}
# ... after identifying `webpage` and `ts` for the latest entry
status_entry["latest_url"] = webpage  # e.g., https://www.youtube.com/watch?v=...
status_entry["latest_ts"] = ts  # int epoch seconds or None
```

```python
# in _get_podcast_statuses (for each playlist URL)
latest = entries[0]
webpage = latest.get("webpage_url") or latest.get("url")
status_entry = {
    "podcast": title,
    "latest_date": latest_date,
    "status": status,
    "url": url,
    "latest_url": webpage,
    "latest_ts": ts,
}
# Optionally, update cache immediately
if webpage:
    self._cache_put(url, webpage, ts)
```

- Sync cache on check completion:
```python
# in _on_podcast_check_finished
self._podcast_last_statuses = statuses
for s in statuses:
    u = s.get("url")
    lu = s.get("latest_url")
    lts = s.get("latest_ts")
    if u and lu:
        self._cache_put(u, lu, lts)
```

- Handler and opener using cache:
```python
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QMenu

def _on_podcast_status_context_menu(self, pos: QPoint) -> None:
    table = getattr(self, "_podcast_status_table", None)
    if not table:
        return
    index = table.indexAt(pos)
    if not index.isValid():
        return
    row = index.row()
    menu = QMenu(table)
    action_open = menu.addAction("Open Latest Video in Browser")

    def _do_open():
        statuses = getattr(self, "_podcast_last_statuses", [])
        if 0 <= row < len(statuses):
            st = statuses[row]
            playlist_url = st.get("url")
            label = st.get("podcast")
            # Prefer status-provided latest_url
            latest_url = st.get("latest_url")
            if not latest_url and playlist_url:
                latest_url = self._cache_get_fresh(playlist_url)
            if latest_url:
                self._open_url_in_browser(latest_url, label)
            else:
                # Fallback: resolve on-demand and cache
                resolved = self._resolve_latest_via_ytdlp(playlist_url)
                if resolved:
                    self._cache_put(playlist_url, resolved["url"], resolved.get("ts"))
                    self._open_url_in_browser(resolved["url"], label)
                else:
                    self.logEdit.appendPlainText(f"Could not resolve latest for {label or playlist_url}")

    action_open.triggered.connect(_do_open)
    menu.exec(table.viewport().mapToGlobal(pos))


def _resolve_latest_via_ytdlp(self, playlist_url: str) -> dict | None:
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "playlistend": 1}) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
        entries = info.get("entries", [info])
        if not entries:
            return None
        latest = entries[0]
        webpage = latest.get("webpage_url") or latest.get("url")
        ts = latest.get("timestamp")
        return {"url": webpage, "ts": ts}
    except Exception:
        return None


def _open_url_in_browser(self, latest_url: str, label: str | None = None) -> None:
    # Try default browser first
    try:
        if webbrowser.open_new_tab(latest_url):
            self.logEdit.appendPlainText(f"Opened latest for {label or latest_url} in default browser")
            return
    except Exception:
        pass
    # Fallback to Brave
    try:
        try:
            controller = webbrowser.get("brave")
        except Exception:
            brave_paths = [
                r"C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
                r"C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
            ]
            controller = None
            for p in brave_paths:
                if os.path.exists(p):
                    webbrowser.register("windows-brave", None, webbrowser.BackgroundBrowser(p))
                    controller = webbrowser.get("windows-brave")
                    break
        if controller:
            controller.open_new_tab(latest_url)
            self.logEdit.appendPlainText(f"Opened latest for {label or latest_url} in Brave")
            return
    except Exception as e:
        self.logEdit.appendPlainText(f"Failed to open Brave: {e}")
    # If all fails
    self.logEdit.appendPlainText(f"Failed to open latest for {label or latest_url}")
```

---

## Risks and Mitigations
- yt-dlp extraction latency: Generally acceptable for single-latest entry; cache eliminates repeated lookups. If still slow, move to worker thread for on-demand resolve.
- Brave not installed: Handled via detection; logs a clear message if fallback unavailable.
- Invalid/empty playlists: Guarded and logged.
- Staleness: TTL and event-based invalidations minimize stale links.

---

## Implementation Time Estimate
- Wiring context menu and opener: 45–60 minutes.
- Adding latest-URL cache, enrichment, and usage: 45–75 minutes.
- Testing with a few podcast rows: 15–30 minutes.
- Optional persistence: 20–30 minutes.

---

## Done Definition
- Right-click on any row in Podcast Status shows a context menu with "Open Latest Video in Browser".
- Selecting the action opens the latest episode page in the default browser, or Brave if default open fails.
- A cache of latest-URLs is maintained and consulted first; subsequent opens within TTL avoid yt-dlp calls.
- Cache updates automatically when statuses refresh or a newer episode appears.
- Errors and non-actionable states are logged in the application’s log area without crashing the UI.
