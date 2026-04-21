# Plan: Fix Application Window Icon in Installed Build

## Context
When the app is installed via the Inno Setup installer and launched, the application window icon does not appear, even though the desktop shortcut icon works correctly.

**Root cause:** PyInstaller (6.0+) one-folder mode places all bundled data under an `_internal/` subdirectory inside the install directory. The code that sets up the Qt icon search path uses `Path(sys.executable).parent`, which resolves to the install root (e.g., `C:\Program Files\VidDownloader\`). This means the search path points to `…\resources\icons\`, which doesn't exist — the actual path is `…\_internal\resources\icons\`.

The desktop shortcut works because Inno Setup extracts the icon directly from the embedded icon in `VidDownloader.exe` (set via PyInstaller's `icon=` argument in the spec file) — no runtime path resolution needed.

`sys._MEIPASS` is the correct PyInstaller attribute for the `_internal` directory and is already used correctly in [src/config.py](../../src/config.py#L89).

## Fix

**File:** [vid downloader.pyw](../../vid%20downloader.pyw) — lines 1765–1769

Change:
```python
if getattr(sys, "frozen", False):
    dirname = Path(sys.executable).parent
else:
    dirname = Path(__file__).parent
QDir.addSearchPath("icons", str(dirname / "resources" / "icons"))
```

To:
```python
if getattr(sys, "frozen", False):
    dirname = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    dirname = Path(__file__).parent
QDir.addSearchPath("icons", str(dirname / "resources" / "icons"))
```

Also remove the TODO comment on line 1809:
```
# TODO: bug: icon not used when installed from installer
```

## Why This Works
- `sys._MEIPASS` resolves to `_internal/` inside the install dir at runtime, matching where PyInstaller places `resources/icons/downFrog.png`.
- `sys.executable` resolves to the exe's directory (one level up from `_internal/`), which is wrong for resource lookup.
- This pattern matches how `src/config.py` already handles `VENV_SCRIPTS_DIR`.

## Verification
1. Run `pyinstaller vid_downloader.spec` to rebuild the dist.
2. Run Inno Setup on `installer/setup.iss` to produce a fresh installer.
3. Install the app.
4. Launch from the Start Menu (not the desktop shortcut) and confirm the window/taskbar icon displays the frog icon.
5. Launch from the desktop shortcut and confirm it still works.
