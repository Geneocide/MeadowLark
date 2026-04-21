# History Dialog — Implementation Plan

## Context

The app currently logs every download to `history_log.txt` but has no UI to browse it (there's even a `# TODO: add way of seeing history info in app?` comment at the end of the main file). The user wants a filterable, paginated history view with keyboard access and the ability to open videos in the browser.

---

## Phases (each independently testable and committable)

**Status: All phases complete. Phase 4 implemented and awaiting user test.**

---

### Phase 1 — Capture URL in history log ✓

**Goal:** Store the video URL in `history_log.txt` for future entries so "open in browser" works.

**What changes:**

- **`QYT.py` — `HistoryLogger`**
  - Add optional `url: str | None = None` param to `_write_history_entry()` and `log()`
  - Append `| URL: {url}` to the end of the line when URL is present (keeps old entries parseable)
  - New format: `[dt] Site: {site} | Type: {dtype} | Title: {title} | Result: {result} | URL: {url}`
  - Old format (no URL field) still valid — parser treats missing URL as `None`

- **`QYT.py` — `HistoryHook.__call__()`**
  - Extract `info.get("webpage_url") or info.get("url")` from `info_dict`
  - Pass it to `HistoryLogger.log(..., url=webpage_url)`

- **`QYT.py` — `parse_history_log()` (new function)**
  - Reads `HISTORY_LOG_PATH`, returns `list[dict]` newest-first
  - Each dict: `{dt, site, dtype, title, result, url}` — `url` is `None` for old entries
  - Uses regex to handle both old and new format safely
  - Title can contain ` | ` so regex must match greedily up to ` | Result:`

- **Tests:** Update `test_qyt.py` to assert URL is written and parsed correctly

**Testable:** Run a download after this phase → check `history_log.txt` has a `| URL: ...` field.

**Implementation notes (completed):**
- `parse_history_log()` uses `encoding="utf-8-sig"` (strips BOM), `rstrip("\r\n")` (handles CRLF), and `rsplit(" | URL: ", 1)` (handles pipes in result text) — all three were QA-caught bugs fixed before shipping.
- `log_skip()` intentionally not modified — URL not available at call sites in `podcast_filter_executor.py`.
- 35 tests passing.

---

### Phase 2 — Basic History Dialog ✓

**Goal:** Ctrl+H opens a window showing history records in a table.

**What changes:**

- **New file `src/history_dialog.py`** — `HistoryDialog(QDialog)`
  - Calls `parse_history_log()` on open
  - `QTableWidget` with 5 visible columns: Datetime | Site | Type | Title | Result
  - URL stored in `Qt.ItemDataRole.UserRole` on the Title cell (not a visible column)
  - Non-blocking (`setModal(False)`), same pattern as `_show_podcast_status()`
  - Dialog title: "Download History"
  - Reasonable default size (e.g., 900×500)

- **`vid downloader.pyw` — `MyWindow`**
  - Import `HistoryDialog`
  - Add `_show_history()` method (same reuse-if-visible pattern as podcast dialog)
  - Wire keyboard shortcut: `QShortcut(QKeySequence("Ctrl+H"), self)`

**Testable:** Press Ctrl+H → dialog opens, records display.

**Implementation notes (completed):**
- Reuses the `_podcast_status_dialog` reuse-if-visible pattern exactly (`getattr` guard + `raise_`/`activateWindow`).
- `QShortcut` / `QKeySequence` live in `PyQt6.QtGui` (not `QtWidgets`) in PyQt6 — different from PyQt5.
- `_history_dialog` reference stored on `MyWindow`; cleared via `destroyed` signal to avoid stale C++ object.
- TODO comment removed from bottom of `vid downloader.pyw`.

---

### Phase 3 — Filtering ✓

**Goal:** Filter records by title text, site, type, and result. No pagination — table scrolls natively and load time is negligible for local file reads.

**What changes (all within `src/history_dialog.py`):**

- **Filter bar** (above table):
  - `QLineEdit` — title search (live, case-insensitive, no button needed)
  - `QComboBox` — Site (populated from unique values + "All")
  - `QComboBox` — Type (populated from unique values + "All")
  - `QComboBox` — Result (options: All / SUCCESS / FAIL / SKIPPED)

- **Logic:**
  - All records loaded once into `self._all_records`
  - `_apply_filters()` resets table rows to matching subset; called on every filter change
  - A status label below the table shows "X of Y records" so the user knows how many are visible

**Testable:** Type in search box → table updates live. Change Site/Type/Result dropdowns → table filters accordingly.

**Implementation notes (completed):**
- Used `table.hideRow()` / `table.showRow()` rather than rebuilding rows on each filter change — all rows created once, visibility toggled in O(n).
- `_result_matches()` extracted as a module-level function (not a method) so it's testable without a `QApplication`.
- SKIPPED filter uses `startswith("SKIPPED")` to match any reason text (e.g., "SKIPPED (Short duration (<3 min))").
- Site and Type combos populated from unique values in the loaded records — no hardcoding needed.
- 43 tests passing (8 new in `test_history_dialog.py`).

---

### Phase 4 — Open in Browser ✓

**Goal:** Right-click or button to open the video URL for a row.

**What changes (all within `src/history_dialog.py`):**

- **Context menu** on table (`customContextMenuRequested`):
  - "Open in Browser" action — enabled only when selected row has a non-`None` URL
  - Calls `webbrowser.open_new_tab(url)` (standard library, no Brave logic needed in dialog)

- **Toolbar button** `[Open in Browser]`:
  - Enabled when a row with a URL is selected (`currentItemChanged` signal)
  - Same `webbrowser.open_new_tab(url)` call

- **Rows without URL** (old log entries):
  - "Open in Browser" disabled in context menu and button grayed out
  - Tooltip on button: "URL not available for older log entries"

**Testable:** Right-click a new record → "Open in Browser" opens the video in the default browser. Right-click an old record → option is grayed out.

**Implementation notes (completed):**
- `_get_selected_url()` reads `Qt.ItemDataRole.UserRole` from the Title cell (col 3); returns `None` when no row is selected (`currentRow() == -1`) or URL is absent.
- Button sits at the right end of the filter bar; disabled by default, enabled/disabled via `itemSelectionChanged` → `_on_selection_changed()`.
- Context menu built with `QMenu`; action connected via lambda capture of `url` (safe — `menu.exec()` is synchronous/blocking).
- QA-caught bug: filtering that hides the selected row does not fire `itemSelectionChanged`, leaving the button erroneously enabled. Fixed: `_apply_filters()` calls `self._table.clearSelection()` when the current row is hidden, which triggers the signal and disables the button.
- `webbrowser.open_new_tab(url)` — standard library, no Brave/custom-browser logic needed here.

---

## Files modified / created

| File | Change |
|---|---|
| `QYT.py` | `HistoryLogger`, `HistoryHook`, new `parse_history_log()` |
| `src/history_dialog.py` | New file — `HistoryDialog` class |
| `vid downloader.pyw` | Import + `_show_history()` + `QShortcut(Ctrl+H)` |
| `tests/test_qyt.py` | URL write/parse test coverage |
| `tests/test_history_dialog.py` | New — filter/url-extraction tests |

## Notes

- `log_skip()` (used for short-duration skips) not modified in Phase 1 — call sites in `podcast_filter_executor.py` don't have the URL readily available. URL can be wired in later if desired.
- Existing test isolation already mocks `HistoryLogger.HISTORY_PATH`, so no test data should appear in production history. No additional guard needed.
- Keyboard shortcut Ctrl+H chosen; trivially changed if preferred otherwise.
- `parse_history_log()` placed in `QYT.py` to stay co-located with `HistoryLogger`; could move to `src/` if the file grows.
