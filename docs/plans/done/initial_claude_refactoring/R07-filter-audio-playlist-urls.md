# R07 — Split `_filter_audio_playlist_urls` into Focused Helpers

## Problem

`_filter_audio_playlist_urls` (`vid downloader.pyw:894–1076`) is 183 lines long and carries four Ruff suppressions on its `def` line:

```python
def _filter_audio_playlist_urls(  # noqa: C901,PLR0912,PLR0915
```

The function has a two-level loop (outer: URLs, inner: entries per URL) and evaluates five distinct conditions in sequence inside the inner loop. All that logic — archive checking, title filtering, duration filtering, timestamp comparison, and SponsorBlock gating — lives in a single body with no named boundaries.

**Logical sections and their line ranges:**

| Section | Lines | Responsibility |
|---|---|---|
| Initialization | 919–927 | Set up accumulators; load archive IDs; get `now_ts` |
| Outer loop / fetch | 928–944 | For each URL: fetch latest entry, build `status_entry` |
| Archive check | 955–957 | Skip if `vid` already in `existing_ids` |
| `(Update)` title filter | 958–974 | Skip and archive if title contains `(Update)` |
| Short duration filter | 975–992 | Skip and archive if duration < 3 min |
| Timestamp / SponsorBlock | 993–1038 | Classify episode: Upcoming / Ready / Pending |
| Status caching | 1040–1047 | Cache latest URL; append status entry |
| Exception handler | 1048–1075 | Catch `YDL_EXTRACTION_ERRORS`; parse scheduled time |

**Helpers already called by the function** (not to be re-extracted):
- `fetch_latest_accessible_entry(url)` — `src/podcast_helpers.py`
- `load_downloaded_video_ids(archive_path)` — `src/podcast_filtering.py`
- `append_to_archive_and_mark_skipped(...)` — `src/podcast_filtering.py`
- `check_sponsorblock_for_video_id(vid)` — `src/podcast_filtering.py`
- `parse_video_timestamp(entry)` — `src/podcast_filtering.py`
- `format_timestamp_readable(ts)` — `src/podcast_filtering.py`
- `parse_scheduled_time_from_error(errstr)` — `src/podcast_filtering.py`
- `utils.resolve_playlist_label(info, url)`
- `utils.detect_site_from_urls([webpage])`
- `QYT.HistoryLogger.log_skip(...)`

---

## Goal

Extract the five inner-loop sections into private methods on `MyWindow`. The outer loop in `_filter_audio_playlist_urls` becomes a readable orchestrator that delegates each decision to a named method. The `# noqa` suppressions are removed.

---

## New Private Methods on `MyWindow`

### `_episode_already_archived`
```python
def _episode_already_archived(
    self,
    vid: str,
    existing_ids: set[str],
    status_entry: dict,
) -> bool:
    """Return True and mark status if the episode is already in the archive."""
    if vid in existing_ids:
        status_entry["status"] = "Downloaded"
        return True
    return False
```

### `_skip_if_update_episode`
```python
def _skip_if_update_episode(
    self,
    entry: dict,
    vid: str,
    webpage: str,
    archive_path: str | None,
    existing_ids: set[str],
    messages: list[str],
    status_entry: dict,
) -> bool:
    """Return True and archive the episode if its title contains '(Update)'."""
    title = entry.get("title", "") or ""
    if "(Update)" not in title:
        return False
    append_to_archive_and_mark_skipped(archive_path, vid, existing_ids, title, messages)
    status_entry["status"] = "Skipped (Update)"
    QYT.HistoryLogger.log_skip(
        site=utils.detect_site_from_urls([webpage]),
        dtype="audio_playlists",
        title=title,
        reason="Update exception",
    )
    return True
```

### `_skip_if_short_duration`
```python
def _skip_if_short_duration(
    self,
    entry: dict,
    vid: str,
    webpage: str,
    archive_path: str | None,
    existing_ids: set[str],
    messages: list[str],
    status_entry: dict,
) -> bool:
    """Return True and archive the episode if it is shorter than the minimum duration."""
    duration = entry.get("duration")
    title = entry.get("title", "") or ""
    if duration is None or duration >= PODCAST_MIN_DURATION_SECONDS:
        return False
    append_to_archive_and_mark_skipped(
        archive_path, vid, existing_ids, title, messages, reason="Short duration (<3 min)"
    )
    status_entry["status"] = "Skipped Short"
    QYT.HistoryLogger.log_skip(
        site=utils.detect_site_from_urls([webpage]),
        dtype="audio_playlists",
        title=title,
        reason="Short duration (<3 min)",
    )
    return True
```

### `_classify_episode_by_age`
```python
def _classify_episode_by_age(
    self,
    vid: str,
    webpage: str,
    ts: float | None,
    now_ts: float,
    playlist_label: str,
    bypass_sponsorblock_wait: bool,
    to_download: list,
    pending: list,
    status_entry: dict,
) -> None:
    """
    Append the episode to to_download or pending based on age and SponsorBlock availability.

    Mutates to_download, pending, and status_entry in place.
    """
    obj = {"url": webpage, "playlist": playlist_label}
    if ts is None:
        to_download.append(obj)
        status_entry["status"] = "Ready"
        return

    status_entry["latest_date"] = format_timestamp_readable(ts)

    if ts > now_ts:
        status_entry["status"] = "Upcoming"
        status_entry["recheck_ts"] = ts
        return

    age_seconds = now_ts - ts
    if bypass_sponsorblock_wait or age_seconds >= 24 * 60 * 60:
        to_download.append(obj)
        status_entry["status"] = "Ready"
        return

    # Episode is < 24 h old — check SponsorBlock for YouTube only
    site = utils.detect_site_from_urls([webpage])
    if site != "youtube" or check_sponsorblock_for_video_id(vid):
        to_download.append(obj)
        status_entry["status"] = "Ready"
    else:
        pending.append(obj)
        status_entry["status"] = "Pending SponsorBlock"
```

---

## Revised `_filter_audio_playlist_urls`

```python
def _filter_audio_playlist_urls(
    self,
    urls: list,
    ydl_opts: dict,
    *,
    bypass_sponsorblock_wait: bool = False,
) -> tuple[list, list, bool, list, list]:
    """
    Expand playlist URLs and return enriched objects with per-episode URL and resolved playlist label.

    Returns: (to_download_objs, pending_objs, had_error, messages, statuses)
    where each obj is {"url": <video_url>, "playlist": <playlist_label>}.
    """
    to_download: list[dict] = []
    pending: list[dict] = []
    had_error = False
    messages: list[str] = []
    statuses: list[dict] = []
    archive_path = ydl_opts.get("download_archive")
    existing_ids: set[str] = load_downloaded_video_ids(archive_path)
    now_ts = datetime.now(tz=timezone.utc).timestamp()

    for url in urls:
        try:
            entries, skipped, info = fetch_latest_accessible_entry(url)
            if skipped:
                messages.append(
                    f"Latest episode for podcast {url} is private - using previous accessible video",
                )
            playlist_label = utils.resolve_playlist_label(info, url)
            status_entry: dict = {
                "podcast": playlist_label,
                "latest_date": "(unknown)",
                "status": "(unknown)",
                "url": url,
            }

            for entry in entries:
                vid = entry.get("id") or entry.get("url")
                webpage = entry.get("webpage_url") or entry.get("url")
                if not vid or not webpage:
                    continue
                status_entry["latest_url"] = webpage
                status_entry["latest_ts"] = parse_video_timestamp(entry)

                if self._episode_already_archived(vid, existing_ids, status_entry):
                    break
                if self._skip_if_update_episode(
                    entry, vid, webpage, archive_path, existing_ids, messages, status_entry
                ):
                    break
                if self._skip_if_short_duration(
                    entry, vid, webpage, archive_path, existing_ids, messages, status_entry
                ):
                    break

                ts = parse_video_timestamp(entry)
                self._classify_episode_by_age(
                    vid, webpage, ts, now_ts, playlist_label,
                    bypass_sponsorblock_wait, to_download, pending, status_entry,
                )
                break

            if status_entry.get("latest_url"):
                self._cache_put(
                    url, status_entry["latest_url"], status_entry.get("latest_ts")
                )
            statuses.append(status_entry)

        except YDL_EXTRACTION_ERRORS as e:
            utils.log_exception(e, f"Error expanding playlist/url {url}")
            errstr = str(e)
            scheduled_ts = parse_scheduled_time_from_error(errstr)
            if scheduled_ts:
                statuses.append({
                    "podcast": url,
                    "latest_date": "(scheduled)",
                    "status": "Upcoming",
                    "url": url,
                    "recheck_ts": scheduled_ts,
                })
                messages.append(
                    f"Podcast {url} scheduled; will recheck at "
                    f"{datetime.fromtimestamp(scheduled_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                )
            else:
                had_error = True
                messages.append(f"Error expanding playlist/url {url}: {e}")
                statuses.append({
                    "podcast": url,
                    "latest_date": "(error)",
                    "status": f"Error: {e}",
                    "url": url,
                })

    return to_download, pending, had_error, messages, statuses
```

The `# noqa` suppressions on the `def` line are removed entirely.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `vid downloader.pyw` | Add 4 helper methods (~55 lines); rewrite main function (~80 lines → ~55 lines); remove 4 noqa suppressions |

The four helpers are individually unit-testable with simple dict inputs — no Qt or yt-dlp required. Consider adding them to `tests/test_podcast_filtering.py` or a new `tests/test_episode_classification.py`.

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check "vid downloader.pyw"` — confirm C901/PLR0912/PLR0915 are no longer suppressed.
3. Trigger a full podcast check covering all episode states:
   - Already archived episode → "Downloaded"
   - `(Update)` episode → "Skipped (Update)"
   - Short episode → "Skipped Short"
   - Upcoming scheduled episode → "Upcoming"
   - YouTube episode < 24h without SponsorBlock → "Pending SponsorBlock"
   - YouTube episode < 24h with SponsorBlock → "Ready"
   - Episode > 24h → "Ready"

---

## Implementation Notes (2026-04-18)

**What was done:** Extracted all 4 helpers as `MyWindow` instance methods. The original `# noqa: C901,PLR0912,PLR0915` suppression on `_filter_audio_playlist_urls` is fully removed.

**Deviations from plan:**
- `_classify_episode_by_age` has `bypass_sponsorblock_wait` as a keyword-only argument (after `*`) rather than a positional bool, fixing FBT001. Carries `# noqa: PLR0913` (9 args structurally required).
- `_skip_if_update_episode` and `_skip_if_short_duration` each carry `# noqa: PLR0913` (7 args).
- The `if status_entry.get("latest_url"):` guard before `_cache_put` was removed; instead `_cache_put`'s `latest_url` parameter type was widened to `str | None` (its body already handled falsy values).
- `tests/test_private_video_handling.py`: `DummyWin` mocks updated to borrow the 4 new methods from `vd.MyWindow` directly (class attribute assignment).

**Pre-existing:** `src/podcast_filter_executor.py` already contained equivalent logic with its own test suite (`tests/test_podcast_filter_executor.py`). That class is not yet wired into `_filter_audio_playlist_urls`; R15 is the appropriate ticket to evaluate merging them.

**Results:** 243 tests pass. Ruff introduces no new violations in the edited region.

## ✅ DONE
