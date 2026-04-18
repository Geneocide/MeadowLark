# R06 — Extract Live Queue Logic to `src/live_queue.py`

## Problem

Three methods — `load_live_queue`, `save_live_queue`, `add_to_live_queue` — are defined **byte-for-byte identically** in two classes:

| Class | File | Lines |
|---|---|---|
| `MyWindow` | `vid downloader.pyw` | 798–833 |
| `DownloadService` | `src/download_service.py` | 276–306 |

Any change to the file format or queue logic must be applied twice. There is no test coverage of the shared logic because it is buried in class methods.

One additional minor inconsistency: `DownloadService.__init__` wraps `LIVE_QUEUE_FILE` in a redundant `Path()` call (line 86), since `config.py:53` already returns a `Final[Path]`.

---

## Goal

Extract the three functions to a new module `src/live_queue.py` as standalone functions that accept `path: Path` as their first argument. Both classes become thin one-line wrappers that forward to the module. No call sites in either class change signature.

---

## New File: `src/live_queue.py`

```python
from pathlib import Path

LiveQueueEntries = dict[str, tuple[str, str | None]]


def load_live_queue(path: Path) -> LiveQueueEntries:
    """Load live queue entries from file; returns {url: (source, playlist_id)}."""
    entries: LiveQueueEntries = {}
    if not path.exists():
        return entries
    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            # stored as: source|url  or  source|url|playlist_id
            parts = line.split("|", 2)
            if len(parts) >= 2 and parts[1]:  # noqa: PLR2004
                playlist_id = parts[2] if len(parts) == 3 and parts[2] else None  # noqa: PLR2004
                entries[parts[1]] = (parts[0], playlist_id)
    return entries


def save_live_queue(path: Path, entries: LiveQueueEntries) -> None:
    """Write live queue entries to file."""
    with path.open("w", encoding="utf-8") as f:
        for url, (source, playlist_id) in entries.items():
            if playlist_id:
                f.write(f"{source}|{url}|{playlist_id}\n")
            else:
                f.write(f"{source}|{url}\n")


def add_to_live_queue(
    path: Path,
    url: str,
    source: str,
    playlist_id: str | None = None,
) -> None:
    """Add a URL to the live queue, avoiding duplicates."""
    entries = load_live_queue(path)
    entries[url] = (source, playlist_id)
    save_live_queue(path, entries)
```

Key improvements over the current implementations:
- `load_live_queue` returns early if the file doesn't exist (avoids extra indentation level).
- `LiveQueueEntries` type alias makes signatures easier to read and keeps them in sync.

---

## Changes to `vid downloader.pyw`

### Add import (near existing `src` imports, around line 73)
```python
import src.live_queue as live_queue
```

### Replace `load_live_queue` (lines 798–812)
```python
def load_live_queue(self) -> live_queue.LiveQueueEntries:
    """Load live queue entries; returns {url: (source, playlist_id)}."""
    return live_queue.load_live_queue(self.live_queue_path)
```

### Replace `save_live_queue` (lines 814–821)
```python
def save_live_queue(self, entries: live_queue.LiveQueueEntries) -> None:
    """Save the live queue entries to file."""
    live_queue.save_live_queue(self.live_queue_path, entries)
```

### Replace `add_to_live_queue` (lines 823–833)
```python
def add_to_live_queue(
    self,
    url: str,
    source: str,
    playlist_id: str | None = None,
) -> None:
    """Add a URL to the live queue."""
    live_queue.add_to_live_queue(self.live_queue_path, url, source, playlist_id)
```

No other changes needed in this file — all internal call sites use `self.load/save/add_to_live_queue(...)` and the signatures are unchanged.

---

## Changes to `src/download_service.py`

### Add import (near existing `src` imports, around line 18)
```python
import src.live_queue as live_queue
```

### Remove redundant `Path()` wrap in `__init__` (line 86)
```python
# Before:
self.live_queue_path = Path(LIVE_QUEUE_FILE)

# After:
self.live_queue_path = LIVE_QUEUE_FILE
```
`LIVE_QUEUE_FILE` is already `Final[Path]` per `src/config.py:53`.

### Replace `load_live_queue` (lines 276–290)
```python
def load_live_queue(self) -> live_queue.LiveQueueEntries:
    """Load live queue entries; returns {url: (source, playlist_id)}."""
    return live_queue.load_live_queue(self.live_queue_path)
```

### Replace `save_live_queue` (lines 292–299)
```python
def save_live_queue(self, entries: live_queue.LiveQueueEntries) -> None:
    """Save the live queue entries to file."""
    live_queue.save_live_queue(self.live_queue_path, entries)
```

### Replace `add_to_live_queue` (lines 301–306)
```python
def add_to_live_queue(self, url: str, source: str, playlist_id: str | None = None) -> None:
    """Add a URL to the live queue."""
    live_queue.add_to_live_queue(self.live_queue_path, url, source, playlist_id)
```

---

## New Test File: `tests/test_live_queue.py`

The extracted module is now directly testable without any Qt or service setup.

```python
from pathlib import Path
import pytest
from src.live_queue import add_to_live_queue, load_live_queue, save_live_queue


@pytest.fixture
def queue_file(tmp_path: Path) -> Path:
    return tmp_path / "live_queue.txt"


def test_load_missing_file_returns_empty(queue_file: Path) -> None:
    assert load_live_queue(queue_file) == {}


def test_round_trip_without_playlist_id(queue_file: Path) -> None:
    entries = {"https://yt.com/watch?v=abc": ("youtube", None)}
    save_live_queue(queue_file, entries)
    assert load_live_queue(queue_file) == entries


def test_round_trip_with_playlist_id(queue_file: Path) -> None:
    entries = {"https://yt.com/watch?v=abc": ("youtube", "PLxyz")}
    save_live_queue(queue_file, entries)
    assert load_live_queue(queue_file) == entries


def test_add_creates_entry(queue_file: Path) -> None:
    add_to_live_queue(queue_file, "https://yt.com/watch?v=xyz", "youtube")
    result = load_live_queue(queue_file)
    assert "https://yt.com/watch?v=xyz" in result
    assert result["https://yt.com/watch?v=xyz"] == ("youtube", None)


def test_add_deduplicates(queue_file: Path) -> None:
    add_to_live_queue(queue_file, "https://yt.com/watch?v=xyz", "youtube")
    add_to_live_queue(queue_file, "https://yt.com/watch?v=xyz", "youtube", "PLabc")
    result = load_live_queue(queue_file)
    assert len(result) == 1
    assert result["https://yt.com/watch?v=xyz"] == ("youtube", "PLabc")


def test_load_skips_blank_lines(queue_file: Path) -> None:
    queue_file.write_text("\nyoutube|https://yt.com/watch?v=abc\n\n", encoding="utf-8")
    result = load_live_queue(queue_file)
    assert len(result) == 1
```

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Create** | `src/live_queue.py` | New module with 3 functions + type alias |
| **Modify** | `vid downloader.pyw` | Add import; replace 3 methods with 1-line wrappers (~28 lines removed) |
| **Modify** | `src/download_service.py` | Add import; replace 3 methods + fix redundant `Path()` (~28 lines removed) |
| **Create** | `tests/test_live_queue.py` | 6 unit tests covering all functions |

Net change: ~56 lines of duplicated logic removed; replaced by ~40 lines in the module + ~12 lines of wrappers = ~4 lines net reduction, plus full test coverage gained.

---

## Verification

1. Run existing live queue tests: `pytest tests/test_live_queue.py -v`
2. Run all tests: `pytest tests/ -v`
3. Launch the app and trigger a live stream detection to confirm queue writes/reads still work end-to-end.
4. Run Ruff: `ruff check src/live_queue.py src/download_service.py`

---

## Implementation Notes (2026-04-17)

- Used `from src import live_queue` (not `import src.live_queue as live_queue`) per Ruff's import style preference.
- Existing `tests/test_live_queue.py` already contained DownloadService wrapper tests; the 6 new standalone module tests were prepended to that file rather than creating a second file.
- The `test_live_queue.py` file already had an unused `call` import from `unittest.mock` — left as-is to avoid scope creep.
