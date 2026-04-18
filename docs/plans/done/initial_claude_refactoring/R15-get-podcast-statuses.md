# R15 — Investigate and Remove `_get_podcast_statuses` (Likely Dead Code) ✅ DONE

## Problem

`_get_podcast_statuses` (`vid downloader.pyw:1591–1713`) is 123 lines long, suppresses `C901`, `PLR0912`, `PLR0915`, and near-duplicates the status-determination logic already in `_filter_audio_playlist_urls`.

**A codebase-wide search for `_get_podcast_statuses` finds zero callers.** Only the definition itself appears. This strongly indicates the method is dead code — likely an earlier version of the podcast-status flow that was superseded by `_filter_audio_playlist_urls` returning statuses as part of its tuple.

---

## How the Two Functions Differ

| Aspect | `_filter_audio_playlist_urls` (lines 894–1076) | `_get_podcast_statuses` (lines 1591–1713) |
|---|---|---|
| Returns | `tuple[list, list, bool, list, list]` — to_download, pending, error, messages, **statuses** | `list[dict]` — statuses only |
| Archive source | From `ydl_opts["download_archive"]` param | Reads `ARCHIVE_PATH` directly |
| Private video handling | `fetch_latest_accessible_entry()` lookahead | Direct `extract_playlist_info(playlistend=1)` |
| Filters | Archive, `(Update)` title, short duration, SponsorBlock | Archive, timestamp, SponsorBlock only |
| Error recovery | Parses scheduled time from error messages | No scheduled time parsing |
| Callers | Called by `_download_podcast_now_action`, `check_live_queue` | **None found** |

The `_filter_audio_playlist_urls` function is the active, more capable version. `_get_podcast_statuses` appears to be a predecessor.

---

## Plan

### Step 1 — Confirm no callers exist

Before deleting, do a thorough search:

```bash
grep -rn "_get_podcast_statuses" "c:/Users/etreq/dev/vid downloader/"
```

Also check:
- All `.py` and `.pyw` files
- Any `.json` config, `.ui` files, or dynamic invocations via `getattr`

If **any** caller is found, skip to the alternative plan below.

### Step 2 — Delete the method

If no callers are found, delete lines 1591–1713 from `vid downloader.pyw` entirely.

### Step 3 — Verify tests still pass

```bash
pytest tests/ -v
```

### Step 4 — Remove the noqa suppressions from the def line

They leave with the function — no action needed.

---

## Alternative Plan (if callers are found)

If `_get_podcast_statuses` turns out to be called (e.g. via a string reference or a UI button not yet found), the right path is:

1. Apply R07 first to extract helpers from `_filter_audio_playlist_urls`.
2. Rewrite `_get_podcast_statuses` to call those helpers instead of duplicating the logic.
3. The method shrinks to a thin wrapper over the shared helpers, with its own archive-path and entry-fetch strategy.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `vid downloader.pyw` | Delete lines 1591–1713 (~123 lines) after confirming zero callers |

This is the only item in the proposal where the first step is investigation, not implementation.

---

## Verification

1. Grep confirms zero callers before deletion.
2. `pytest tests/ -v` passes after deletion.
3. Full UI smoke test: open the app, trigger a podcast check, open the status dialog — confirm nothing references the deleted method.

---

## Implementation Notes (2026-04-18)

Grep of all `.py`/`.pyw` files and dynamic `getattr` patterns confirmed zero callers. Deleted lines 1668–1790 (123 lines) from `vid downloader.pyw`. Zero new Ruff violations introduced. 287 tests pass, 1 skipped (chmod on Windows).
