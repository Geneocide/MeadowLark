# R16 — Split `_open_url_in_browser` into Focused Helpers

## Problem

`_open_url_in_browser` (`vid downloader.pyw:1242–1286`) has a three-level nested try/except that handles three separate concerns in one body:

```
try: open default browser
    → on failure: try to get Brave controller
        → on failure: manually register Brave from known paths
        if controller: open in Brave
except outer Brave errors: log failure
if all failed: log final failure
```

**Full current implementation:**
```python
def _open_url_in_browser(self, latest_url: str, label: str | None = None) -> None:
    """Open a URL in the default browser, with fallback to Brave."""
    try:
        if webbrowser.open_new_tab(latest_url):
            self.logEdit.appendPlainText(
                f"Opened latest for {label or latest_url} in default browser",
            )
            return
    except (webbrowser.Error, OSError) as exc:
        utils.log_exception(exc, "Failed to open URL in default browser")
    try:
        try:
            controller = webbrowser.get("brave")
        except (webbrowser.Error, OSError) as exc:
            utils.log_exception(exc, "Failed to get Brave controller via webbrowser.get")
            brave_paths = [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            ]
            controller = None
            for p in brave_paths:
                if Path(p).exists():
                    webbrowser.register(
                        "windows-brave", None, webbrowser.BackgroundBrowser(p)
                    )
                    controller = webbrowser.get("windows-brave")
                    break
        if controller:
            controller.open_new_tab(latest_url)
            self.logEdit.appendPlainText(
                f"Opened latest for {label or latest_url} in Brave",
            )
            return
    except (webbrowser.Error, OSError) as e:
        self.logEdit.appendPlainText(f"Failed to open Brave: {e}")
        utils.log_exception(e, "Failed to open URL in Brave")
    self.logEdit.appendPlainText(f"Failed to open latest for {label or latest_url}")
```

---

## Goal

Extract two private helpers so the top-level method reads as a three-step cascade with no nesting.

---

## New Method: `_try_open_default_browser`

```python
def _try_open_default_browser(self, url: str, label: str | None) -> bool:
    """Try to open URL in the system default browser. Returns True on success."""
    try:
        if webbrowser.open_new_tab(url):
            self.logEdit.appendPlainText(
                f"Opened latest for {label or url} in default browser",
            )
            return True
    except (webbrowser.Error, OSError) as exc:
        utils.log_exception(exc, "Failed to open URL in default browser")
    return False
```

---

## New Method: `_get_brave_controller`

```python
_BRAVE_PATHS: list[str] = [
    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
]

def _get_brave_controller(self) -> webbrowser.BaseBrowser | None:
    """Return a Brave browser controller, registering it from disk if needed."""
    try:
        return webbrowser.get("brave")
    except (webbrowser.Error, OSError) as exc:
        utils.log_exception(exc, "Failed to get Brave controller via webbrowser.get")
    for p in self._BRAVE_PATHS:
        if Path(p).exists():
            webbrowser.register("windows-brave", None, webbrowser.BackgroundBrowser(p))
            try:
                return webbrowser.get("windows-brave")
            except (webbrowser.Error, OSError):
                pass
    return None
```

Note: `_BRAVE_PATHS` is a class-level constant so it is not recreated on each call. Move it to the class body above `__init__`.

---

## Revised `_open_url_in_browser`

```python
def _open_url_in_browser(self, latest_url: str, label: str | None = None) -> None:
    """Open a URL in the default browser, with fallback to Brave."""
    if self._try_open_default_browser(latest_url, label):
        return
    try:
        controller = self._get_brave_controller()
        if controller:
            controller.open_new_tab(latest_url)
            self.logEdit.appendPlainText(
                f"Opened latest for {label or latest_url} in Brave",
            )
            return
    except (webbrowser.Error, OSError) as e:
        self.logEdit.appendPlainText(f"Failed to open Brave: {e}")
        utils.log_exception(e, "Failed to open URL in Brave")
    self.logEdit.appendPlainText(f"Failed to open latest for {label or latest_url}")
```

The nesting goes from three levels to one.

---

## File Summary

| Action | File | Detail |
|---|---|---|
| **Modify** | `vid downloader.pyw` | Add class constant `_BRAVE_PATHS`; add 2 helpers (~20 lines); top-level method shrinks from ~45 lines to ~12 lines |

---

## Verification

1. Run all tests: `pytest tests/ -v`
2. Test opening a URL with the default browser available.
3. Test the Brave fallback: temporarily comment out the `webbrowser.open_new_tab` success path and confirm Brave opens.
4. Test the all-failed path: confirm the failure message is logged when neither browser opens.

---

## Implementation Notes

**Status:** ✅ DONE (2026-04-18)

- Added `ClassVar` import from `typing` (placed in correct isort position).
- Added `_BRAVE_PATHS: ClassVar[list[str]]` class constant.
- Extracted `_try_open_default_browser(url, label) -> bool` and `_get_brave_controller() -> BaseBrowser | None`.
- `_get_brave_controller` uses `contextlib.suppress` for the per-path fallback registration error (cleaner than a nested try/except).
- `_open_url_in_browser` reduced from 45 lines / 3 nesting levels to 12 lines / 1 level.
- 243 tests pass.
