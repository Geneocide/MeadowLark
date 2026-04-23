# Plan: Settings Dialog for MeadowLark

## Context
The app has always been personal-use only with preferences hardcoded or hidden behind `.env` editing. The app is being shared, so a proper in-app Settings UI is needed. Many preferences are already backed by env vars (in `src/config.py`), but the UI to change them doesn't exist. A few others (drop labels, playlist button labels, podcast auto-check) need new env vars added. The `src/first_run_wizard.py` pattern and `dotenv` (loaded in `QYT.py`) establish how `.env` writing works.

There are also two explicit TODO items in `meadowlark.pyw` (lines 1876, 1879) that this directly resolves.

---

## File Management Recommendation

**Hybrid approach:**
- **Playlist files** (user-authored): On Browse/import, copy to `AppData/Roaming/MeadowLark/playlists/` under fixed filenames (`playlists.txt`, `720playlists.txt`, `audio playlists.txt`). Store the AppData path in `.env`. The copy is the canonical file; user re-browses to update from an external source. This keeps everything self-contained and survives moves/deletions of the original. On fresh install, the `resources/playlists/` defaults remain the fallback.
- **Cookies.txt** (yt-dlp-managed): Reference only — store the path, never copy. This file is auto-updated by yt-dlp and browser extensions; copying would create a stale, broken copy. User just points us at the real file.

---

## UI Layout

Gear button `⚙` placed at **row 0, col 3** in the main `QGridLayout` (existing row 0: col 0 Skip Download, col 1 Ignore Archive, col 2 Update button).

Opens a **non-modal** `QDialog` with a `QTabWidget` (4 tabs). Non-modal so user can keep using the app. Reuses the same instance if already open (raises it to front). Apply button writes changes; Close discards unapplied widget edits.

### Tab Layout
| Tab | Settings |
|-----|----------|
| **Downloads** | Video dir (+ Browse), Audio dir (+ Browse) |
| **Playlists** | Playlists file, 720 Playlists file, Audio Playlists file (all with Browse + copy-to-appdata), Cookies.txt (Browse, reference-only) |
| **Interface** | Drop labels: 1080, 720, audio; Ready text; Playlist button labels: Playlists, 720 Playlists, YT Podcasts |
| **Automation** | Podcast auto-check checkbox + interval spinbox (5–1440 min, disabled when checkbox off) |

Each setting has a small `?` button that shows a `QMessageBox.information()`. All help strings live in `HELP_TEXT` dict at the top of `settings_dialog.py`.

---

## Key Design Decision: DropLabel Source Key

`DropLabel.dropEvent` currently emits `self.originalText` as the routing key to `request_detected()` (e.g., `"1080"`, `"720"`, `"audio"`). If a user renames the display text, routing breaks. **Fix:** add a `source_key: str` attribute to `DropLabel` set at construction; emit `source_key` instead of `originalText`. Display text and routing key become independent.

---

## Runtime Settings Registry

`src/config.py` constants are `Final` — frozen at import. Changes applied from Settings need a mutable in-memory store. A module-level `_runtime: dict[str, object]` dict in `settings_dialog.py` serves this role. Initialized from frozen config at startup (`_init_runtime_settings()`), then updated on Apply. All code paths that need a live value call `get_setting("VID_DL_...")` instead of the frozen constant.

---

## Files to Create/Modify

### NEW: `src/settings_dialog.py`
- `HELP_TEXT: dict[str, str]` — all user-facing help strings, one entry per setting key, at the top of the file (easy to edit)
- `_runtime: dict` — runtime mutable settings store
- `_init_runtime_settings()` — called once from `MyWindow.__init__`, populates `_runtime` from frozen config
- `get_setting(key)` — accessor used by any code that needs a live value
- `_persist_setting(key, value)` — writes to AppData `.env` via `dotenv.set_key()` and updates `_runtime`
- `_import_playlist_file(source_path, dest_name)` — copies to AppData playlists dir, returns new path
- `_make_help_button(key, parent)` — returns `QPushButton("?")` wired to show `HELP_TEXT[key]`
- `_make_dir_row(label, key, parent)` — returns `(QHBoxLayout, QLineEdit)` with Browse button
- `_make_file_row(label, key, parent, filter_str, copy_to_appdata)` — same but for files; handles copy vs reference logic
- `SettingsDialog(QDialog)` — `settings_changed = pyqtSignal(dict)` emitted on Apply with `{env_var: new_value}` for changed keys only

### MODIFY: `src/config.py`
Add in "Display Configuration" section (after `LABEL_READY_TEXT`, line 154):
```python
LABEL_DROP_1080: Final[str] = os.getenv("VID_DL_LABEL_DROP_1080", "1080")
LABEL_DROP_720: Final[str] = os.getenv("VID_DL_LABEL_DROP_720", "720")
LABEL_DROP_AUDIO: Final[str] = os.getenv("VID_DL_LABEL_DROP_AUDIO", "audio")
LABEL_BTN_PLAYLISTS: Final[str] = os.getenv("VID_DL_LABEL_BTN_PLAYLISTS", "Playlists")
LABEL_BTN_720: Final[str] = os.getenv("VID_DL_LABEL_BTN_720", "720 Playlists")
LABEL_BTN_PODCASTS: Final[str] = os.getenv("VID_DL_LABEL_BTN_PODCASTS", "YT Podcasts")
```
Add in "Podcast Configuration" section:
```python
PODCAST_AUTO_CHECK: Final[bool] = os.getenv("VID_DL_PODCAST_AUTO_CHECK", "true").lower() == "true"
PODCAST_CHECK_INTERVAL_MINUTES: Final[int] = int(os.getenv("VID_DL_PODCAST_CHECK_INTERVAL_MINUTES", "60"))
```

### MODIFY: `UIClasses.py`
- `DropLabel.__init__`: add `source_key: str | None = None` parameter; `self.source_key = source_key or text`
- `DropLabel.dropEvent`: emit `self.source_key` instead of `self.originalText`

### MODIFY: `meadowlark.pyw`
- Import new config constants and `_init_runtime_settings`, `get_setting`, `SettingsDialog`
- `__init__`: call `_init_runtime_settings()`, set `self._settings_dialog = None`, set `self._ready_text = LABEL_READY_TEXT`
- `_setup_ui_layout`:
  - Use config constants for all widget labels: `DropLabel(LABEL_DROP_1080, ...)`, `PlaylistButton(LABEL_BTN_PLAYLISTS, ...)` etc.
  - Pass explicit `source_key` to each `DropLabel`: `"1080"`, `"720"`, `"audio"`
  - Add gear button at row 0, col 3: `self.buttonSettings = QPushButton("⚙")`, connect to `self._open_settings`
  - Change `self.labelOutput = QLabel(self._ready_text)`
- Replace hardcoded `"[ Ready ]"` in `handle_queue_empty` and podcast check callbacks with `self._ready_text`
- `_setup_timers`: wrap podcast scheduling in `if PODCAST_AUTO_CHECK:` check
- Add `_open_settings()` — creates/raises `SettingsDialog`, connects `settings_changed`
- Add `reload_settings(changes: dict)` — dispatches live updates:
  - Drop label text: update both `setText()` and `originalText` on the widget
  - Ready text: update `self._ready_text`, refresh `labelOutput` if currently showing ready state
  - Playlist button labels: call `setText()`
  - Playlist file paths: update `self.buttonX.playlist_path`
  - Podcast auto/interval: call `_restart_podcast_timer()`
- Add `_restart_podcast_timer()` — stops existing timer, restarts if `get_setting("VID_DL_PODCAST_AUTO_CHECK")` is true with new interval
- Fix `_get_source_options()`: read video/podcast dirs from `get_setting()` at call time
- Fix hardcoded `r"resources\cookies.txt"` in `check_live_queue()`: use `get_setting("VID_DL_COOKIES_FILE")`

### MODIFY: `src/ydl_options.py`
- `build_base_ydl_opts()`: change `"cookiefile": str(COOKIES_FILE)` to read from `get_setting("VID_DL_COOKIES_FILE") or str(COOKIES_FILE)` at call time

### MODIFY: `src/playlist_utils.py`
- `get_playlist_file_for_source()`: read paths from `get_setting()` at call time, falling back to frozen constants

---

## Additional Settings to Consider (out of scope for now)
- **Window always-on-top** toggle (currently hardcoded `WindowStaysOnTopHint`)
- **Output label font** (env vars `VID_DL_LABEL_OUTPUT_FONT` / `VID_DL_LABEL_OUTPUT_FONT_SIZE` already exist, just need UI)

---

## Verification
1. Launch app — gear button `⚙` appears top-right of row 0
2. Click `⚙` — Settings dialog opens non-modally; app remains usable
3. Click `⚙` again — same dialog raises to front, no duplicate
4. **Downloads tab**: Change video dir → Apply → drag URL to 1080 label → download goes to new dir
5. **Interface tab**: Rename "1080" label → Apply → label text changes immediately, drops still route correctly
6. **Interface tab**: Change Ready text → Apply → status label updates immediately
7. **Automation tab**: Uncheck auto-check → Apply → log shows disabled; re-enable + change interval → log confirms restart
8. **Playlists tab**: Browse to new playlists.txt → Apply → file copied to AppData → right-click Playlists button opens new file
9. **Playlists tab**: Browse to cookies.txt → path stored, no copy made
10. Close and restart — all settings persist (AppData `.env` was updated)
11. All `?` buttons show the correct help text from `HELP_TEXT` dict
