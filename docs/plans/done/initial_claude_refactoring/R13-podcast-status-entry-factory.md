# R13 — Add `_make_podcast_status_entry` Factory on `MyWindow`

## Problem

The podcast status dictionary — with keys `podcast`, `latest_date`, `status`, `url` — is built inline in six places across two methods. Each occurrence uses slightly different default values, making it easy to miss a key when the schema changes:

| Occurrence | Method | Lines | Keys set |
|---|---|---|---|
| 1 | `_filter_audio_playlist_urls` | 895–900 | base 4, defaults `"(unknown)"` |
| 2 | `_filter_audio_playlist_urls` | 1025–1032 | base 4 + `recheck_ts`, date `"(scheduled)"` |
| 3 | `_filter_audio_playlist_urls` | 1041–1048 | base 4, date `"(error)"`, status is f-string |
| 4 | `_get_podcast_statuses` | 1634–1641 | base 4, date `"(none)"`, status `"No episodes"` |
| 5 | `_get_podcast_statuses` | 1689–1696 | base 4 + `latest_url`, `latest_ts` |
| 6 | `_get_podcast_statuses` | 1705–1712 | base 4, date `"(error)"`, status is f-string |

Adding a new field (e.g. a `site` key for analytics) would require updating all six sites.

---

## Goal

Add `_make_podcast_status_entry` as a private method on `MyWindow`. It provides the four mandatory keys with sensible defaults and accepts `**kwargs` for optional extensions (`recheck_ts`, `latest_url`, `latest_ts`). Replace all six inline constructions with calls to it.

---

## New Method on `MyWindow`

```python
def _make_podcast_status_entry(
    self,
    podcast: str,
    url: str,
    status: str = "(unknown)",
    latest_date: str = "(unknown)",
    **kwargs: object,
) -> dict:
    """Create a podcast status entry dict with standard keys and optional extensions."""
    return {"podcast": podcast, "latest_date": latest_date, "status": status, "url": url, **kwargs}
```

Place this near the other small helpers on `MyWindow` (e.g. next to `_cache_put`).

---

## Replacement at Each Call Site

### Occurrence 1 — `_filter_audio_playlist_urls` (lines 895–900)
```python
# Before:
status_entry: dict = {
    "podcast": playlist_label,
    "latest_date": "(unknown)",
    "status": "(unknown)",
    "url": url,
}

# After:
status_entry = self._make_podcast_status_entry(playlist_label, url)
```

### Occurrence 2 — `_filter_audio_playlist_urls` error handler, scheduled case (lines 1025–1032)
```python
# Before:
statuses.append({
    "podcast": url,
    "latest_date": "(scheduled)",
    "status": "Upcoming",
    "url": url,
    "recheck_ts": scheduled_ts,
})

# After:
statuses.append(self._make_podcast_status_entry(
    url, url, status="Upcoming", latest_date="(scheduled)", recheck_ts=scheduled_ts
))
```

### Occurrence 3 — `_filter_audio_playlist_urls` error handler, error case (lines 1041–1048)
```python
# Before:
statuses.append({
    "podcast": url,
    "latest_date": "(error)",
    "status": f"Error: {e}",
    "url": url,
})

# After:
statuses.append(self._make_podcast_status_entry(
    url, url, status=f"Error: {e}", latest_date="(error)"
))
```

### Occurrence 4 — `_get_podcast_statuses`, no episodes (lines 1634–1641)
```python
# Before:
statuses.append({
    "podcast": title,
    "latest_date": "(none)",
    "status": "No episodes",
    "url": url,
})

# After:
statuses.append(self._make_podcast_status_entry(
    title, url, status="No episodes", latest_date="(none)"
))
```

### Occurrence 5 — `_get_podcast_statuses`, full entry (lines 1689–1696)
```python
# Before:
entry = {
    "podcast": title,
    "latest_date": latest_date,
    "status": status,
    "url": url,
    "latest_url": webpage,
    "latest_ts": ts,
}

# After:
entry = self._make_podcast_status_entry(
    title, url,
    status=status,
    latest_date=latest_date,
    latest_url=webpage,
    latest_ts=ts,
)
```

### Occurrence 6 — `_get_podcast_statuses`, error case (lines 1705–1712)
```python
# Before:
statuses.append({
    "podcast": url,
    "latest_date": "(error)",
    "status": f"Error: {e}",
    "url": url,
})

# After:
statuses.append(self._make_podcast_status_entry(
    url, url, status=f"Error: {e}", latest_date="(error)"
))
```

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `vid downloader.pyw` | Add `_make_podcast_status_entry` (~6 lines); replace 6 inline dict literals |

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Trigger a podcast check and open the podcast status dialog to confirm all status entries display correctly across all states (Downloaded, Upcoming, Pending, Error, No episodes, Ready).

---

## Implementation Notes

**Status:** ✅ DONE (2026-04-18)

The plan placed `_make_podcast_status_entry` as a method on `MyWindow`, but tests use a `DummyWin` mock that doesn't inherit from `MyWindow`, so tests failed with `AttributeError`. Since the function doesn't use `self` at all, it was implemented as a module-level function in `vid downloader.pyw` (just before `class MyWindow`). All 6 `self.` prefixes were removed from call sites. 243 tests pass.
