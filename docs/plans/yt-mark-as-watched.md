# Plan: Auto-Mark YouTube Videos as Watched on Download

## Notes for future plans

- **Settings dialog checkbox pattern** (`_build_interface_tab` / `_build_automation_tab`) now has a third example: `VID_DL_APP_UPDATE_AUTO_CHECK`. All bool settings follow the same QCheckBox → `_edits[key]` → generic `_apply()` flow.
- **Date-based throttling via .env** — `VID_DL_APP_UPDATE_LAST_CHECKED` stores an ISO date string in the AppData `.env`. Any future feature needing time-based throttling can piggyback on the same `_persist_setting` / `get_setting` pair; no separate storage is needed.
- **Private `_persist_setting` is importable** in `meadowlark.pyw` — it is now in the import list, so future startup-time writes to the .env can reuse it without adding a new import.

---

## Context

Users who download YouTube videos via MeadowLark may want those videos automatically
marked as watched in their YouTube account, so watch history and recommendations stay
accurate even when viewing happens through the app. yt-dlp natively supports a
`mark_watched` option for YouTube — it uses the authenticated session from the
existing `cookies.txt` to POST the watch event. This means no custom HTTP logic,
no fragile reverse-engineering: it's a one-flag addition to the yt-dlp options dict.

The feature must be off by default and opt-in via Settings. It requires a valid
YouTube session in `cookies.txt`, which the user already configures in the Playlists tab.

---

## Implementation

### Step 1 — Add config constant
**File:** [src/config.py](src/config.py) (after `ALWAYS_ON_TOP` at line 151)

Add a `MARK_WATCHED` constant following the exact same pattern as `ALWAYS_ON_TOP`:

```python
MARK_WATCHED: Final[bool] = (
    os.getenv("VID_DL_MARK_WATCHED", "false").lower() == "true"
)
```

Default is `false` — feature is off unless the user enables it.

---

### Step 2 — Register in runtime settings
**File:** [src/settings_dialog.py](src/settings_dialog.py)

**2a.** Import `MARK_WATCHED` from config (alongside `ALWAYS_ON_TOP` in the existing
import block, lines 29–48).

**2b.** Add help text to `HELP_TEXT` dict (after the `VID_DL_ALWAYS_ON_TOP` entry,
around line 128):

```python
"VID_DL_MARK_WATCHED": (
    "When enabled, downloaded YouTube videos are automatically marked as watched\n"
    "in your YouTube account.\n\n"
    "Requires a cookies.txt file with an active YouTube login session.\n"
    "Configure your cookies.txt path in the Playlists tab."
),
```

**2c.** Seed the runtime value in `_init_runtime_settings()` (line 145), after the
`VID_DL_ALWAYS_ON_TOP` entry:

```python
"VID_DL_MARK_WATCHED": MARK_WATCHED,
```

---

### Step 3 — Add checkbox to Downloads tab
**File:** [src/settings_dialog.py](src/settings_dialog.py) — `_build_downloads_tab()` (line 351)

Add a checkbox row at the bottom of the Downloads tab, following the identical
pattern used for `VID_DL_ALWAYS_ON_TOP` in `_build_interface_tab()` (lines 436–444):

```python
mw_check = QCheckBox(self)
mw_check.setChecked(bool(get_setting("VID_DL_MARK_WATCHED")))
help_mw = _make_help_button("VID_DL_MARK_WATCHED", self)
mw_row = QHBoxLayout()
mw_row.addWidget(mw_check)
mw_row.addWidget(help_mw)
mw_row.addStretch()
self._edits["VID_DL_MARK_WATCHED"] = mw_check
form.addRow(QLabel("Mark watched on YouTube:"), _wrap(mw_row))
```

The `_apply()` method (line 557) already handles `QCheckBox` generically — no
changes needed there.

---

### Step 4 — Pass option to yt-dlp
**File:** [src/ydl_options.py](src/ydl_options.py) — `build_base_ydl_opts()` (line 37)

After the `"js_runtimes"` / `"remote_components"` lines, conditionally inject the
option:

```python
if get_setting("VID_DL_MARK_WATCHED"):
    opts["mark_watched"] = True
```

yt-dlp documents `mark_watched` as YouTube-only and silently ignores it for other
sites, so it is safe to include in the shared base options rather than
per-source options.

**Implementation note:** The return dict is a literal, so refactor slightly to
build `opts` as a variable, append conditionally, then return — or simply add the
conditional key after the literal with `opts = {...}; if ...: opts["mark_watched"] = True; return opts`.

---

## Critical files

| File | Change |
|------|--------|
| [src/config.py](src/config.py) | Add `MARK_WATCHED` constant (line ~151) |
| [src/settings_dialog.py](src/settings_dialog.py) | Import, HELP_TEXT, seed, checkbox UI |
| [src/ydl_options.py](src/ydl_options.py) | Conditionally set `mark_watched` in base opts |

No new files. No new dependencies (`requests` already present; yt-dlp handles the
HTTP request internally).

---

## Verification

1. **Enable the setting:** Open Settings → Downloads tab → check "Mark watched on
   YouTube" → Apply.
2. **Download a YouTube video** by dropping a URL onto the 1080 or 720 target.
3. **Check YouTube history** — the video should appear as watched.
4. **Disable the setting** → Apply, download another video → confirm it is NOT
   marked watched.
5. **Cookie edge case:** Remove or corrupt `cookies.txt`, enable the feature, and
   download — yt-dlp should log a warning but the download should still complete
   (the mark-watched step failing must not block the download).
6. **Non-YouTube URL:** Drop a non-YouTube URL with the setting enabled — download
   should complete normally, no errors from the `mark_watched` option.
7. Run `ruff check src/` to confirm no linting violations.
