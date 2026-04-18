# R05 — Extract `_create_download_context` Helper on `MyWindow`

## Problem

`MyWindow` in `vid downloader.pyw` constructs a `QHook`, `QLogger`, and base `ydl_opts` in five separate places. Two distinct patterns appear:

**Pattern A — Full construction** (3 occurrences): Creates all three objects fresh.
```python
qhook = QYT.QHook()
qlogger = QYT.QLogger(self.downloadQueue)
ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)
```

| Method | Lines |
|---|---|
| `request_detected` | 505–506, 526 |
| `check_live_queue` | 861–863 |
| `_download_podcast_now_action` | 1379–1381 |

**Pattern B — Partial update** (2 occurrences inside `_on_podcast_check_finished`): Creates fresh hook/logger but manually patches an existing `ydl_opts` dict rather than calling `build_base_ydl_opts`, to preserve the dict's other settings.
```python
qhook = QYT.QHook()
qlogger = QYT.QLogger(self.downloadQueue)
batch_opts = dict(ydl_opts)        # or download_opts = dict(ydl_opts)
batch_opts["logger"] = qlogger
batch_opts["progress_hooks"] = [qhook]
```

| Method | Branch | Lines |
|---|---|---|
| `_on_podcast_check_finished` | object list loop | 1542–1546 |
| `_on_podcast_check_finished` | plain URL else | 1556–1560 |

Additionally, signal connections are wired immediately after the init in four of the five occurrences:
```python
qhook.info_changed.connect(self.handle_info_changed)
qlogger.message_changed.connect(self.handle_log_entry)
```

---

## Goal

Add two private helpers to `MyWindow`:

1. `_create_download_context()` — covers Pattern A (full construction).
2. `_fork_download_context(base_opts)` — covers Pattern B (copy existing opts, swap logger/hook).

Signal wiring stays at call sites since it is sometimes conditional (occurrence 1 inside an if-block, occurrence 3 not wired until later). A third helper `_wire_download_signals(qhook, qlogger)` eliminates the two-line duplication where connections are wired.

---

## New Methods on `MyWindow`

Add these three methods as a group near the existing `load_live_queue` / `save_live_queue` block (around line 798):

```python
def _create_download_context(self) -> tuple[QYT.QHook, QYT.QLogger, dict]:
    """Create a fresh QHook, QLogger, and base ydl_opts dict."""
    qhook = QYT.QHook()
    qlogger = QYT.QLogger(self.downloadQueue)
    ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)
    return qhook, qlogger, ydl_opts

def _fork_download_context(
    self, base_opts: dict
) -> tuple[QYT.QHook, QYT.QLogger, dict]:
    """Create a fresh QHook/QLogger and return a copy of base_opts with them wired in."""
    qhook = QYT.QHook()
    qlogger = QYT.QLogger(self.downloadQueue)
    opts = dict(base_opts)
    opts["logger"] = qlogger
    opts["progress_hooks"] = [qhook]
    return qhook, qlogger, opts

def _wire_download_signals(self, qhook: QYT.QHook, qlogger: QYT.QLogger) -> None:
    """Connect qhook/qlogger signals to the main window handler slots."""
    qhook.info_changed.connect(self.handle_info_changed)
    qlogger.message_changed.connect(self.handle_log_entry)
```

---

## Call-site Updates

### `request_detected` (lines 505–506, 526, 549–551)
```python
# Before:
qhook = QYT.QHook()
qlogger = QYT.QLogger(self.downloadQueue)
# ... intervening code ...
ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)
# ... intervening code ...
qhook.info_changed.connect(self.handle_info_changed)
# qlogger.message_changed.connect(self.logEdit.appendPlainText)  # dead comment — delete
qlogger.message_changed.connect(self.handle_log_entry)

# After:
qhook, qlogger, ydl_opts = self._create_download_context()
# ... intervening code (unchanged) ...
# ... intervening code (unchanged) ...
self._wire_download_signals(qhook, qlogger)
```

Note: delete the commented-out dead line (`# qlogger.message_changed.connect(...)`) at the same time (this is also R22).

### `check_live_queue` (lines 861–863, 883–884)
```python
# Before:
qhook = QYT.QHook()
qlogger = QYT.QLogger(self.downloadQueue)
ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)
# ... intervening code ...
qhook.info_changed.connect(self.handle_info_changed)
qlogger.message_changed.connect(self.handle_log_entry)

# After:
qhook, qlogger, ydl_opts = self._create_download_context()
# ... intervening code (unchanged) ...
self._wire_download_signals(qhook, qlogger)
```

### `_download_podcast_now_action` (lines 1379–1381)
```python
# Before:
qhook = QYT.QHook()
qlogger = QYT.QLogger(self.downloadQueue)
ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)

# After:
qhook, qlogger, ydl_opts = self._create_download_context()
```

No signal wiring here — it happens later in `_on_podcast_check_finished`.

### `_on_podcast_check_finished` — object list branch (lines 1542–1550)
```python
# Before:
qhook = QYT.QHook()
qlogger = QYT.QLogger(self.downloadQueue)
batch_opts = dict(ydl_opts) if isinstance(ydl_opts, dict) else {}
batch_opts["logger"] = qlogger
batch_opts["progress_hooks"] = [qhook]
# ... one line ...
qhook.info_changed.connect(self.handle_info_changed)
qlogger.message_changed.connect(self.handle_log_entry)

# After:
qhook, qlogger, batch_opts = self._fork_download_context(
    ydl_opts if isinstance(ydl_opts, dict) else {}
)
# ... one line (unchanged) ...
self._wire_download_signals(qhook, qlogger)
```

### `_on_podcast_check_finished` — plain URL else branch (lines 1556–1563)
```python
# Before:
qhook = QYT.QHook()
qlogger = QYT.QLogger(self.downloadQueue)
download_opts = dict(ydl_opts) if isinstance(ydl_opts, dict) else {}
download_opts["logger"] = qlogger
download_opts["progress_hooks"] = [qhook]
# ...
qhook.info_changed.connect(self.handle_info_changed)
qlogger.message_changed.connect(self.handle_log_entry)

# After:
qhook, qlogger, download_opts = self._fork_download_context(
    ydl_opts if isinstance(ydl_opts, dict) else {}
)
# ...
self._wire_download_signals(qhook, qlogger)
```

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `vid downloader.pyw` | Add 3 helper methods (~15 lines); update 5 call sites (~30 lines removed) |

Net: ~30 lines removed across call sites, replaced by ~15 lines of helpers + ~10 lines of one-liners at call sites.

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Run Ruff: `ruff check "vid downloader.pyw"`
3. Trigger a regular download, a live-queue re-check, a podcast check, and a "Download Now" podcast action — confirm all produce the expected log output and progress bar updates.

---

## Implementation Notes (2026-04-18)

Done. 243 tests pass. No new Ruff violations introduced.

**Deviations from plan:**
- `request_detected`: `qhook`/`qlogger` were originally created before the `"Update"` early-return guard; moved the guard first, then called `_create_download_context()` after it. The separate `build_base_ydl_opts` call (previously line 562) was removed — `_create_download_context()` covers it.
- `_download_podcast_now_action`: `qhook` and `qlogger` are unused at this call site (they're embedded in `ydl_opts` and the actual wiring happens later in `_on_podcast_check_finished`). Used `_, _, ydl_opts = self._create_download_context()` to suppress Pylance "not accessed" hints.
- `_fork_download_context` parameter list uses a trailing comma per project Ruff/COM812 style.
