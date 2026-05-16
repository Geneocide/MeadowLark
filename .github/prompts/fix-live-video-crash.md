# Plan: Fix Silent Crash on Live Video Download

## Context

When a user tries to download a video that is still live streaming, the app should detect it via a `match_filter` callback, add it to a live queue file, log a message, and skip the download. Instead, the app crashes silently with no error log.

**Root cause:** The `match_filter` closure is called by yt-dlp from a background `QThread` (`QYTQueue.run`). The `log_fn` passed into it is `self.logEdit.appendPlainText` — a direct Qt widget call from a non-GUI thread. This is undefined behavior in Qt/PyQt6 and can silently abort the thread, raise a `RuntimeError`, or cause a Qt assertion failure — all of which result in a silent failure with no visible error. When a `RuntimeError` does propagate, it lands in `QYTQueue.run()`'s exception handler but still never shows in the GUI log, since the GUI call itself is what failed.

Two secondary bugs also need fixing:
- `_mf` only catches `TypeError, AttributeError` — `add_to_queue_fn` can raise `OSError` if file write fails, which would propagate uncaught through yt-dlp.
- In `check_live_queue`, `ydl.extract_info()` can return `None`; calling `.get()` on `None` raises `AttributeError` and keeps the URL stuck in the queue forever.

## Changes

### 1. Thread-safe log signal in `MyWindow` — `meadowlark.pyw`

Add a `pyqtSignal(str)` to `MyWindow` to route log messages from background threads safely:

```python
# In class MyWindow(QWidget):
live_queue_log = pyqtSignal(str)
```

In `__init__` (or wherever signals are wired), connect it:
```python
self.live_queue_log.connect(self.handle_log_entry)
```

Change `make_match_filter` (line 778–784) to pass the signal's `emit` instead of the widget method:
```python
def make_match_filter(self, source: str) -> Callable:
    return build_match_filter(
        source,
        add_to_queue_fn=self.add_to_live_queue,
        log_fn=self.live_queue_log.emit,   # thread-safe signal emit
    )
```

Qt uses a `QueuedConnection` automatically when the emitter is in a different thread from the receiver, so this is safe without any extra configuration.

### 2. Broaden exception catch in `_mf` — `src/match_filter.py`

Change the narrow `except (TypeError, AttributeError)` to catch `Exception` so `OSError` and other file I/O errors from `add_to_queue_fn` don't propagate into yt-dlp:

```python
except Exception as exc:
    utils.log_exception(exc, "Error in match_filter")
    return None
```

### 3. Guard against `None` info in `check_live_queue` — `meadowlark.pyw` ~line 844

After `info = ydl.extract_info(url, download=False)`, add:
```python
if info is None:
    remaining[url] = (source, playlist_id)
    continue
```

## Critical Files

- `meadowlark.pyw` — `make_match_filter` (line 778), `check_live_queue` (line 827), `MyWindow` class definition (line 178 area for signal declaration)
- `src/match_filter.py` — `_mf` closure (lines 20–41)

## Verification

1. Run the app and drag in a URL for a currently-live YouTube stream.
2. Confirm the GUI log shows "Queued live for later: <url>" (no crash).
3. Confirm `resources/live_queue.txt` contains the queued URL.
4. Run `pytest` and confirm existing live queue tests still pass.
5. Run `ruff check src/ meadowlark.pyw` and confirm no new violations.
