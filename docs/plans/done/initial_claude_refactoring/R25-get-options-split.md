# R25 — Split `DownloadService.get_options()` into Focused Helpers

## Problem

`get_options` (`src/download_service.py:151–186`) handles five distinct responsibilities in 36 lines with no internal structure:

```python
def get_options(self, urls: list, source: str) -> dict | None:
    if self.skip_download_callback():           # 1. Skip-mode gate
        self.skip_downloading(urls, source)
        return None

    if not urls:                                # 2. Empty-URL guard
        self.log_edit_append_callback(...)
        return None

    properties = utils.get_source_options(source)   # 3. Base options

    if not self.ignore_archive_callback():      # 4. Archive injection
        properties["download_archive"] = str(ARCHIVE_PATH)

    if "youtube.com" in urls[0]:               # 5a. Match-filter (YouTube)
        properties["match_filter"] = self.make_match_filter(source)

    if "youtube.com/watch" in urls[0] and "&list=" in urls[0]:  # 5b. URL cleanup
        urls[0] = urls[0].split("&list=")[0]

    return properties
```

Concerns 4 and 5 are small but distinct policies. Extracting them gives each a name, makes `get_options` read as a policy checklist, and makes each policy independently testable.

---

## Goal

Extract three private helpers — `_add_archive_if_needed`, `_add_match_filter_if_youtube`, and `_strip_watch_later_list_param` — so `get_options` delegates each mutation to a named method. No behavior changes.

---

## New Methods on `DownloadService`

### `_add_archive_if_needed`

```python
def _add_archive_if_needed(self, properties: dict) -> None:
    """Add the download archive path to properties unless the user opted to ignore it."""
    if not self.ignore_archive_callback():
        properties["download_archive"] = str(ARCHIVE_PATH)
```

### `_add_match_filter_if_youtube`

```python
def _add_match_filter_if_youtube(self, properties: dict, urls: list, source: str) -> None:
    """Attach a custom match_filter for YouTube URLs to skip and queue live videos."""
    if urls and "youtube.com" in urls[0]:
        properties["match_filter"] = self.make_match_filter(source)
```

### `_strip_watch_later_list_param`

```python
def _strip_watch_later_list_param(self, urls: list) -> None:
    """Remove the &list= parameter from a Watch Later URL in place."""
    if urls and "youtube.com/watch" in urls[0] and "&list=" in urls[0]:
        urls[0] = urls[0].split("&list=")[0]
```

Note: this mutates `urls[0]` in place, matching the current behavior exactly. The method name makes the intent explicit — this is a Watch Later edge-case strip, not a general URL normalisation.

---

## Revised `get_options`

```python
def get_options(self, urls: list, source: str) -> dict | None:
    """
    Build yt-dlp options dict based on URLs and source type.

    Returns None if the download should be skipped or there are no URLs.
    """
    if self.skip_download_callback():
        self.skip_downloading(urls, source)
        return None

    if not urls:
        self.log_edit_append_callback(f"No URLs found for source: {source}")
        return None

    properties = utils.get_source_options(source)
    self._add_archive_if_needed(properties)
    self._add_match_filter_if_youtube(properties, urls, source)
    self._strip_watch_later_list_param(urls)
    return properties
```

The body drops from 36 lines to 15, and each policy is now a named call rather than an inline conditional block.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `src/download_service.py` | Add 3 helper methods (~15 lines); `get_options` body shrinks from 36 to 15 lines |

No imports change. No callers change. All existing tests covering `get_options` continue to apply unchanged.

---

## Suggested Tests

The helpers are now independently testable without setting up a full `DownloadService`:

```python
# tests/test_download_service.py (extend existing or add)

def test_add_archive_if_needed_adds_path(service_with_archive_enabled):
    props = {}
    service_with_archive_enabled._add_archive_if_needed(props)
    assert "download_archive" in props
    assert props["download_archive"] == str(ARCHIVE_PATH)


def test_add_archive_if_needed_skips_when_ignored(service_with_archive_ignored):
    props = {}
    service_with_archive_ignored._add_archive_if_needed(props)
    assert "download_archive" not in props


def test_add_match_filter_for_youtube_url(service):
    props = {}
    service._add_match_filter_if_youtube(props, ["https://youtube.com/watch?v=abc"], "1080")
    assert "match_filter" in props


def test_add_match_filter_skipped_for_non_youtube(service):
    props = {}
    service._add_match_filter_if_youtube(props, ["https://twitch.tv/stream"], "1080")
    assert "match_filter" not in props


def test_strip_watch_later_list_param_removes_list(service):
    urls = ["https://youtube.com/watch?v=abc&list=WL&index=3"]
    service._strip_watch_later_list_param(urls)
    assert urls[0] == "https://youtube.com/watch?v=abc"


def test_strip_watch_later_list_param_leaves_playlist_url_alone(service):
    urls = ["https://youtube.com/playlist?list=PLabc"]
    service._strip_watch_later_list_param(urls)
    assert urls[0] == "https://youtube.com/playlist?list=PLabc"
```

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/download_service.py`
3. Trigger a Watch Later URL drop and confirm the `&list=` parameter is still stripped before the download starts.
4. Trigger a YouTube playlist download and confirm the match filter is wired (live videos are skipped and queued).
5. Trigger a download with "Ignore Archive?" unchecked and confirm the archive path appears in the yt-dlp options.
