# Plan: Automatic App Update Check

## Context

MeadowLark currently has all the infrastructure to check for a newer app version via the
GitHub Releases API (`src/version_utils.py` → `is_app_update_available()`), but that check
only runs when the user manually presses **Ctrl+U** or clicks "Check for Updates" in
Settings → About. Users who never discover those entry points will never know a new version
exists. This plan adds a weekly background check that fires silently at startup and notifies
the user only when a newer release is found, with an opt-out setting.

---

## Changes

### 1. `src/config.py` — add setting constant

Add a new boolean constant for the opt-out setting (follows the existing `ALWAYS_ON_TOP`
pattern):

```python
APP_UPDATE_AUTO_CHECK: Final[bool] = (
    os.getenv("VID_DL_APP_UPDATE_AUTO_CHECK", "true").lower() == "true"
)
```

### 2. `src/settings_dialog.py` — wire the setting into the UI

**a. `_init_runtime_settings()`** — add to the `_runtime.update({...})` dict:
```python
"VID_DL_APP_UPDATE_AUTO_CHECK": APP_UPDATE_AUTO_CHECK,
```

**b. Settings dialog (General or a new "Updates" section in the About/General tab)**
— add a `QCheckBox` row following the `VID_DL_ALWAYS_ON_TOP` pattern:
```python
auto_update_check = QCheckBox(self)
auto_update_check.setChecked(bool(get_setting("VID_DL_APP_UPDATE_AUTO_CHECK")))
help_btn = _make_help_button("VID_DL_APP_UPDATE_AUTO_CHECK", self)
row = QHBoxLayout()
row.addWidget(auto_update_check)
row.addWidget(help_btn)
row.addStretch()
self._edits["VID_DL_APP_UPDATE_AUTO_CHECK"] = auto_update_check
form.addRow(QLabel("Auto-check for app updates:"), _wrap(row))
```

No changes needed to `_apply()` — it already handles all `QCheckBox` widgets generically.

### 3. `meadowlark.pyw` — startup check with weekly throttle

**a. `_init_runtime_settings()`** — already handled by step 2a above.

**b. `reload_settings()`** — handle the new key (no runtime action needed beyond persisting
the value; the check only runs at startup, so no live toggle behavior is required).

**c. Startup logic in `MyWindow.__init__()`** — after the existing yt-dlp update check
(~line 223), add:

```python
self._maybe_start_auto_app_update_check()
```

**d. New helper method `_maybe_start_auto_app_update_check()`**:

```python
def _maybe_start_auto_app_update_check(self) -> None:
    """Fire a background app-update check at most once per week if the setting is on."""
    if not get_setting("VID_DL_APP_UPDATE_AUTO_CHECK"):
        return
    last_checked = get_setting("VID_DL_APP_UPDATE_LAST_CHECKED")  # ISO date string or None
    if last_checked:
        try:
            last_dt = datetime.date.fromisoformat(last_checked)
            if (datetime.date.today() - last_dt).days < 7:
                return
        except ValueError:
            pass
    self._start_app_update_check(auto=True)
```

**e. `_start_app_update_check()`** — add an `auto: bool = False` parameter. When
`auto=True`, pass a flag through to `_on_app_update_result` so it can persist the
last-checked date and suppress the "no update available" toast (silent unless update found).

**f. `_on_app_update_result()`** — already shows a dialog when an update is found.
- If `auto=True` and **no** update: do nothing (silent).
- If `auto=True` and **update found**: show the existing update dialog (same UX as manual).
- After any auto check completes (update or not): persist today's date:
  ```python
  _persist_setting("VID_DL_APP_UPDATE_LAST_CHECKED", datetime.date.today().isoformat())
  ```

### 4. `src/config.py` — add last-checked tracking constant

```python
APP_UPDATE_LAST_CHECKED: Final[str] = os.getenv("VID_DL_APP_UPDATE_LAST_CHECKED", "")
```

This piggybacks on the existing `.env` persistence mechanism so the date survives restarts.

---

## Key Files

| File | Change |
|---|---|
| `src/config.py` | Add `APP_UPDATE_AUTO_CHECK` and `APP_UPDATE_LAST_CHECKED` constants |
| `src/settings_dialog.py` | Add checkbox row; register both keys in `_init_runtime_settings()` |
| `meadowlark.pyw` | Add startup trigger, `_maybe_start_auto_app_update_check()`, update `_start_app_update_check(auto)` and `_on_app_update_result()` |

No changes needed to `src/version_utils.py` — `is_app_update_available()` is already correct.

---

## Verification

1. **Happy path**: On first launch after the change, confirm the background thread fires and
   (with a mocked newer version) shows the update dialog.
2. **Throttle**: Launch a second time within 7 days → no check fires (verify with a log
   print or breakpoint).
3. **Opt-out**: Disable the setting in Settings, restart → no check fires.
4. **Manual check still works**: Ctrl+U and the Settings button still trigger the check
   regardless of the auto-check setting or last-checked date.
5. Run `pytest` and `ruff check` — no regressions.
