# R01 — Extract `make_match_filter` to `src/match_filter.py`

## Problem

`make_match_filter` is defined as a method in two classes:

| Class | File | Lines |
|---|---|---|
| `MyWindow` | `vid downloader.pyw` | 761–795 |
| `DownloadService` | `src/download_service.py` | 237–273 |

The inner `_mf` closure is nearly identical — same logic, same exception handling — but the two versions differ in how they call back into their host class:

| Line | `MyWindow` | `DownloadService` |
|---|---|---|
| Live queue add | `self.add_to_live_queue(url, source, playlist_id)` | `self.add_to_live_queue_callback(url, source, playlist_id)` |
| Log message | `self.logEdit.appendPlainText(f"...")` | `self.log_edit_append_callback(f"...")` |

Because `DownloadService` already uses callbacks to avoid depending on Qt widgets directly, the correct extraction is a **factory function that accepts those two callbacks as parameters** — not a bare function referencing `self`.

---

## Goal

Create `src/match_filter.py` with a standalone `build_match_filter` factory. Both classes call it and pass their own callback implementations. The `make_match_filter` method on each class becomes a one-line wrapper.

---

## New File: `src/match_filter.py`

```python
from __future__ import annotations

from collections.abc import Callable

import utils


def build_match_filter(
    source: str,
    add_to_queue_fn: Callable[[str, str, str | None], None],
    log_fn: Callable[[str], None],
) -> Callable[[dict, bool], str | None]:
    """
    Build a yt-dlp match_filter that skips live/upcoming videos and queues them for later.

    Args:
        source: Source identifier passed through to add_to_queue_fn.
        add_to_queue_fn: Called with (url, source, playlist_id) when a live video is found.
        log_fn: Called with a human-readable message string.
    """

    def _mf(info: dict, incomplete: bool) -> str | None:  # noqa: ARG001,FBT001
        try:
            is_live = info.get("is_live")
            live_status = info.get("live_status")
            availability = info.get("availability")
            if availability in ("needs_auth", "scheduled"):
                return f"Skipping: {availability}"
            if is_live or live_status in ("is_live", "is_upcoming"):
                url = (
                    info.get("webpage_url")
                    or info.get("original_url")
                    or info.get("url")
                )
                if url:
                    playlist_id = info.get("playlist_id")
                    add_to_queue_fn(url, source, playlist_id)
                    log_fn(f"Queued live for later: {url} [{source}]")
                return "Skipping live; queued for later"
        except (TypeError, AttributeError) as exc:
            utils.log_exception(exc, "Error in match_filter")
            return None
        return None

    return _mf
```

---

## Changes to `vid downloader.pyw`

### Add import (with other `src` imports, around line 73)
```python
from src.match_filter import build_match_filter
```

### Replace `make_match_filter` method (lines 761–795)
```python
def make_match_filter(self, source: str) -> Callable:
    """Build a match_filter that skips live/upcoming videos and queues them."""
    return build_match_filter(
        source,
        add_to_queue_fn=self.add_to_live_queue,
        log_fn=self.logEdit.appendPlainText,
    )
```

No other changes needed — all callers of `self.make_match_filter(source)` keep the same interface.

---

## Changes to `src/download_service.py`

### Add import (with other `src` imports, around line 18)
```python
from src.match_filter import build_match_filter
```

### Replace `make_match_filter` method (lines 237–273)
```python
def make_match_filter(self, source: str) -> Callable:
    """Build a match_filter that skips live/upcoming videos and queues them."""
    return build_match_filter(
        source,
        add_to_queue_fn=self.add_to_live_queue_callback,
        log_fn=self.log_edit_append_callback,
    )
```

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Create** | `src/match_filter.py` | Factory function with full filter logic (~35 lines) |
| **Modify** | `vid downloader.pyw` | Add import; replace 35-line method with 5-line wrapper |
| **Modify** | `src/download_service.py` | Add import; replace 37-line method with 5-line wrapper |

Net: ~65 lines of duplicated logic → ~35 lines in module + ~10 lines of wrappers.

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check src/match_filter.py`
3. Trigger a download that includes a live/upcoming video and confirm the live-queue message still appears in the log and the URL is written to `resources/live_queue.txt`.

---

## Implementation Notes (2026-04-17)

- `Callable` moved to `TYPE_CHECKING` block to satisfy Ruff TC003.
- Module docstring added to satisfy Ruff D100.
- 238 tests pass; `ruff check src/match_filter.py` clean.
