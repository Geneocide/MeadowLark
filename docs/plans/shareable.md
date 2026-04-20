# Plan: Make Video Downloader Shareable

## Context
The app has been used personally. Moving to shareable means eliminating developer-specific assumptions and providing a clear path for others to install and run it. Two audiences: developer peers first, non-technical users second.

---

## Phase 1: Developer-Shareable

The three env vars with machine-specific hardcoded fallbacks are:
- `VID_DL_VIDEO_STORAGE_DIR` — falls back to `E:/vid storage`
- `VID_DL_ARCHIVE_PATH` — falls back to `C:/Users/etreq/OneDrive/…/tfarchive.txt`
- `VID_DL_PODCAST_MISC_OUTPUT_DIR` — falls back to `C:/Users/etreq/OneDrive/…/misc`

All other env vars (`VID_DL_ERROR_LOG`, `VID_DL_HISTORY_LOG`, `VID_DL_RESOURCES_DIR`, timeout/numeric vars, etc.) have safe relative or generic defaults — no changes needed there.

**Post-Phase-1 fix — `cookies.txt` isolation** ✅

`COOKIES_FILE` had no env var override, and `download_service.py` used a hardcoded `r"resources\cookies.txt"` instead of the config constant. Each user should supply their own cookies (or none), not inherit the repo owner's login sessions.

- `src/config.py`: changed `COOKIES_FILE` to use `_resolve_path("VID_DL_COOKIES_FILE", ...)` 
- `src/download_service.py`: replaced `r"resources\cookies.txt"` with `str(COOKIES_FILE)` and added `COOKIES_FILE` to the config import
- `.env.example`: added `VID_DL_COOKIES_FILE` entry with a warning not to share it

### Recommended execution order

**Step 1 — Add `.env` to `.gitignore`** ✅

`.env` is currently **not** in `.gitignore`. Add it now or it risks being committed with personal paths.

**File:** `.gitignore` — append:
```
.env
```

> **Impl note:** Done. `.env` appended to `.gitignore`.

---

**Step 2 — Add `python-dotenv` dependency** ✅

**File:** `pyproject.toml` — add to `dependencies`:
```toml
"python-dotenv>=1.0.0",
```

Then run `uv sync`.

> **Impl note:** Added. `uv sync` installed `python-dotenv==1.2.2`.

---

**Step 3 — Create personal `.env` (project root, gitignored)** ✅

This is the safety net. With this in place, changing the fallback defaults in Step 5 has zero effect on your setup.

**File:** `.env` (new):
```dotenv
VID_DL_VIDEO_STORAGE_DIR=E:/vid storage
VID_DL_ARCHIVE_PATH=C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt
VID_DL_PODCAST_MISC_OUTPUT_DIR=C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/misc
```

> **Impl note:** Created at project root. Confirmed gitignored.

---

**Step 4 — Load `.env` at startup** ✅

**File:** `QYT.py` — add at the top, **before** any `from src.config import …`:
```python
from dotenv import load_dotenv
load_dotenv()
```

`load_dotenv()` must run before `src.config` is imported, because config reads env vars at module-load time.

> **Impl note:** Added just before `from src.config import` in `QYT.py`. Chain works because `vid downloader.pyw` does `import QYT` (line 72) before `from src.config import (...)` (line 75), so `src.config` is first loaded with env vars already populated.

---

**Step 5 — Fix hardcoded path defaults** (`src/config.py:73,77,81`) ✅

With your `.env` in place (Step 3), this change is invisible to your setup.

| Line | Current | Replacement |
|------|---------|-------------|
| 73 (`ARCHIVE_PATH`) | `"C:/Users/etreq/OneDrive/…/tfarchive.txt"` | `str(Path(__file__).parent.parent / "resources" / "archive.txt")` |
| 77 (`PODCAST_MISC_OUTPUT_DIR`) | `"C:/Users/etreq/OneDrive/…/misc"` | `str(Path.home() / "Music" / "Podcasts")` |
| 81 (`VIDEO_STORAGE_DIR`) | `"E:/vid storage"` | `str(Path.home() / "Videos")` |

Verify `from pathlib import Path` is already imported in `src/config.py`.

> **Impl note:** Done. `pathlib.Path` was already imported. Defaults now use `Path(__file__)` and `Path.home()`.

---

**Step 6 — Guard the startup `startfile()` call** (`vid downloader.pyw:~1760`) ✅

Current:
```python
startfile(r"E:\vid storage")  # noqa: S606
```

Replace with:
```python
_storage = Path(VIDEO_STORAGE_DIR)
if _storage.exists():
    startfile(str(_storage))  # noqa: S606
```

`VIDEO_STORAGE_DIR` is already imported from `src.config` at that call site; verify `Path` is also imported.

> **Impl note:** Done. Both `VIDEO_STORAGE_DIR` and `Path` were already imported at that call site.

---

**Step 7 — Add FFmpeg startup check** ✅

`yt-dlp` silently fails on audio/podcast downloads if FFmpeg is missing. Show a warning after the main window is created.

**File:** `vid downloader.pyw` (post `window.show()`):
```python
import shutil
if not shutil.which("ffmpeg"):
    QMessageBox.warning(
        None,
        "FFmpeg not found",
        "FFmpeg is not installed or not on PATH.\nAudio and podcast downloads will fail.",
    )
```

> **Impl note:** Done. `shutil` and `QMessageBox` were already imported. Check placed after `window.show()`.

---

**Step 8 — Add Deno startup check** ✅

Deno is installed into `.venv/Scripts` via the `deno` PyPI package, so `shutil.which` won't find it on PATH. Check the venv path directly:

```python
from src.config import VENV_SCRIPTS_DIR
from pathlib import Path
deno_exe = Path(VENV_SCRIPTS_DIR) / "deno.exe"
if not deno_exe.exists():
    QMessageBox.warning(
        None,
        "Deno not found",
        f"Deno not found at {deno_exe}.\nRun `uv sync` to install it.",
    )
```

> **Impl note:** Done. Added `VENV_SCRIPTS_DIR` to the `src.config` import block. Check placed after FFmpeg check.

---

**Step 9 — Fix hardcoded test paths** ✅

**`tests/test_private_video_handling.py:61`** — used to dynamically import the main module:
```python
# Current:
r"c:\Users\etreq\dev\vid downloader\vid downloader.pyw"

# Replace with:
str(Path(__file__).parent.parent / "vid downloader.pyw")
```

**`tests/test_download_service.py:105`** — assertion that checks the podcast output path:
```python
# Current:
assert options["outtmpl"].startswith("C:/Users/etreq/OneDrive/…/misc/")

# Replace with (import the config value):
from src.config import PODCAST_MISC_OUTPUT_DIR
assert options["outtmpl"].startswith(str(PODCAST_MISC_OUTPUT_DIR))
```

Note: `tests/test_download_executor.py` uses `"E:/vid storage"` extensively, but those are intentional path-parsing fixtures — leave them as-is.

> **Impl note:** Done. Also added `from pathlib import Path` import to `test_private_video_handling.py` (was missing). `PODCAST_MISC_OUTPUT_DIR` added to existing `src.config` import in `test_download_service.py`. Used `.as_posix()` (not `str()`) because `ydl_options.py` builds `outtmpl` with `.as_posix()` — `str(Path)` on Windows returns backslashes which wouldn't match.

---

**Step 10 — Create `.env.example`** (committed to repo) ✅

Documents all supported env vars for new users.

> **Impl note:** Created at project root.

---

**Step 11 — Write README.md** ✅

Sections:
1. Prerequisites: Python ≥3.10, `uv`, FFmpeg (link to install), Deno (auto-installed via `uv sync`)
2. Setup: `git clone`, `uv sync`, copy `.env.example` → `.env`, fill in the three required paths
3. Run: `uv run python "vid downloader.pyw"`
4. Env var reference table

> **Impl note:** Written. Previous README.md was empty (1 line placeholder).

---

**Step 12 — CI pipeline** ✅ (medium priority, can defer)

**File:** `.github/workflows/ci.yml`

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest
      - run: uv run ruff check
```

> **Impl note:** Created `.github/workflows/ci.yml`. `.github/workflows/` directory did not exist.

---

### Summary: files changed

| File | Change |
|------|--------|
| `.gitignore` | Add `.env` |
| `pyproject.toml` | Add `python-dotenv` dep |
| `.env` (new, gitignored) | Your personal paths |
| `QYT.py` | `load_dotenv()` at top + FFmpeg/Deno checks |
| `src/config.py:73,77,81` | Replace hardcoded fallbacks with `Path.home()` equivalents |
| `vid downloader.pyw:~1760` | Guard `startfile()` with existence check |
| `tests/test_private_video_handling.py:61` | Replace absolute path with `Path(__file__)` relative |
| `tests/test_download_service.py:105` | Replace OneDrive path with `PODCAST_MISC_OUTPUT_DIR` import |
| `.env.example` (new) | Template for other users |
| `README.md` | Full setup guide |
| `.github/workflows/ci.yml` (new) | Automated tests + lint |

### Verification

1. Delete `.env` temporarily → app starts, uses `Path.home()/Videos` as default, no crash
2. Restore `.env` → app uses `E:/vid storage` again, storage folder opens on startup
3. `uv run pytest` → all tests pass including the two fixed test files
4. `git status` → `.env` not listed as untracked

---

## Phase 2: Non-Technical Users

Three tracks, in recommended implementation order:

1. **First-run wizard** — pure Python/Qt, no tooling required, improves UX for all audiences
2. **PyInstaller spec** — packages the app as a standalone `.exe`
3. **Release workflow + Inno Setup installer** — bundles FFmpeg, creates a one-click installer

---

### Recommended execution order

**Step 13 — Load user config from AppData** (`QYT.py`) ✅

Non-technical users running the installed `.exe` will never have a project `.env`. Their config
lives at `%APPDATA%\VidDownloader\.env` (written by the wizard in Step 14). `load_dotenv()` must
pick it up automatically.

Current (`QYT.py` top of file):
```python
from dotenv import load_dotenv
load_dotenv()
```

Replace with:
```python
from pathlib import Path
from dotenv import load_dotenv

_user_env = Path.home() / "AppData" / "Roaming" / "VidDownloader" / ".env"
load_dotenv(dotenv_path=_user_env if _user_env.exists() else None)
load_dotenv()   # also load project .env in dev (won't override vars already set)
```

`load_dotenv()` skips env vars already present in `os.environ`, so user AppData config wins over
any project `.env`.

> **Impl note:** Done. `Path` was already imported in `QYT.py`; only the two `load_dotenv` calls needed replacing.

---

**Step 14 — Create `src/first_run_wizard.py`** (new file) ✅

Shows a folder-picker dialog on first launch. Writes chosen paths to
`%APPDATA%\VidDownloader\.env` so they're loaded next time (Step 13).

```python
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

_APPDATA_DIR = Path.home() / "AppData" / "Roaming" / "VidDownloader"
_USER_ENV = _APPDATA_DIR / ".env"


def needs_first_run() -> bool:
    return not _USER_ENV.exists()


class FirstRunWizard(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome — Vid Downloader Setup")
        self.setMinimumWidth(500)
        self._video_dir = str(Path.home() / "Videos")
        self._podcast_dir = str(Path.home() / "Music" / "Podcasts")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(
            "<b>Welcome to Vid Downloader!</b><br><br>"
            "Where should downloaded videos be saved?"
        ))
        vid_row = QHBoxLayout()
        self._video_edit = QLineEdit(self._video_dir)
        vid_browse = QPushButton("Browse…")
        vid_browse.clicked.connect(self._browse_video)
        vid_row.addWidget(self._video_edit)
        vid_row.addWidget(vid_browse)
        layout.addLayout(vid_row)

        layout.addWidget(QLabel("Where should podcast episodes be saved? (optional)"))
        pod_row = QHBoxLayout()
        self._podcast_edit = QLineEdit(self._podcast_dir)
        pod_browse = QPushButton("Browse…")
        pod_browse.clicked.connect(self._browse_podcast)
        pod_row.addWidget(self._podcast_edit)
        pod_row.addWidget(pod_browse)
        layout.addLayout(pod_row)

        layout.addWidget(QLabel(
            "<i>Settings are saved to AppData and can be changed there later.</i>"
        ))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_video(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select Video Folder", self._video_edit.text())
        if chosen:
            self._video_edit.setText(chosen)

    def _browse_podcast(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select Podcast Folder", self._podcast_edit.text())
        if chosen:
            self._podcast_edit.setText(chosen)

    def accept(self) -> None:
        _APPDATA_DIR.mkdir(parents=True, exist_ok=True)
        lines = [
            f"VID_DL_VIDEO_STORAGE_DIR={self._video_edit.text()}\n",
            f"VID_DL_PODCAST_MISC_OUTPUT_DIR={self._podcast_edit.text()}\n",
        ]
        _USER_ENV.write_text("".join(lines), encoding="utf-8")
        super().accept()
```

> **Impl note:** Done. Created at `src/first_run_wizard.py`. Matches the plan spec exactly.

---

**Step 15 — Show wizard on first launch** (`vid downloader.pyw`) ✅

Add import and call site after `window.show()` in the `if __name__ == "__main__":` block.

Add to imports (near other `src` imports at top of file):
```python
from src.first_run_wizard import FirstRunWizard, needs_first_run
```

After `window.show()` (before the FFmpeg check):
```python
if needs_first_run():
    _wizard = FirstRunWizard(window)
    _wizard.exec()
```

> **Impl note:** Done. Import added near other `src` imports; call site placed after `window.show()`, before FFmpeg check.

---

**Step 16 — Patch path detection for packaged mode** (`vid downloader.pyw:~1762`) ✅

PyInstaller sets `sys.frozen = True` and places bundled files relative to `sys.executable`, not
`__file__`. The `QDir.addSearchPath` call (icons) will break without this.

Current:
```python
dirname = Path(__file__).parent
QDir.addSearchPath("icons", str(dirname / "resources" / "icons"))
```

Replace with:
```python
if getattr(sys, "frozen", False):
    dirname = Path(sys.executable).parent
else:
    dirname = Path(__file__).parent
QDir.addSearchPath("icons", str(dirname / "resources" / "icons"))
```

> **Impl note:** Done. `sys` was already imported. Replaced the single `dirname = Path(__file__).parent` line.

---

**Step 17 — Add `pyinstaller` dev dependency** (`pyproject.toml`) ✅

```toml
[dependency-groups]
dev = [
    "pyinstaller>=6.0",
]
```

Then run: `uv sync --group dev`

> **Impl note:** Done. Added `[dependency-groups]` section. Run `uv sync --group dev` to install.

---

**Step 18 — Create `vid_downloader.spec`** (new file, project root) ✅

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["vid downloader.pyw"],
    pathex=[],
    binaries=[],
    datas=[
        ("resources", "resources"),
    ],
    hiddenimports=[
        *collect_submodules("yt_dlp"),
        "keyring.backends.Windows",
        "wakepy._implementations",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VidDownloader",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon="resources/icons/downFrog.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="VidDownloader",
)
```

**Notes:**
- `collect_submodules("yt_dlp")` prevents missing-extractor errors at runtime (yt-dlp uses dynamic
  imports for its 1800+ extractors).
- `console=False` matches the `.pyw` behaviour — no terminal window.
- `icon` expects `.ico`; convert `downFrog.png` → `downFrog.ico` via Pillow or an online tool and
  commit alongside the `.png`.
- Output is a folder (`dist/VidDownloader/`) — one-folder mode is preferred over one-file because
  startup is faster and FFmpeg can be dropped in by the installer.
- Test locally: `uv run pyinstaller vid_downloader.spec`, then run `dist\VidDownloader\VidDownloader.exe`.

> **Impl note:** Done. Created at project root. `resources/icons/downFrog.ico` does not exist yet — only `.png` is present. Convert before building: `python -c "from PIL import Image; Image.open('resources/icons/downFrog.png').save('resources/icons/downFrog.ico')"` (requires Pillow, or use an online converter). Spec has an inline comment as a reminder.

---

**Step 19 — Create `.github/workflows/release.yml`** (new file) ✅

Triggers on version tags. Builds the exe, bundles FFmpeg, and uploads a zipped release to GitHub.

```yaml
name: Release
on:
  push:
    tags: ["v*.*.*"]

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3

      - name: Install dependencies (incl. dev group for PyInstaller)
        run: uv sync --group dev

      - name: Build executable
        run: uv run pyinstaller vid_downloader.spec

      - name: Download FFmpeg
        shell: pwsh
        run: |
          $url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
          Invoke-WebRequest -Uri $url -OutFile ffmpeg.zip
          Expand-Archive ffmpeg.zip -DestinationPath ffmpeg_tmp
          $bin = Get-ChildItem ffmpeg_tmp -Recurse -Filter "bin" -Directory | Select-Object -First 1
          Copy-Item "$($bin.FullName)\ffmpeg.exe"  dist\VidDownloader\
          Copy-Item "$($bin.FullName)\ffprobe.exe" dist\VidDownloader\

      - name: Zip dist folder
        shell: pwsh
        run: Compress-Archive -Path dist\VidDownloader -DestinationPath VidDownloader-${{ github.ref_name }}.zip

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: VidDownloader-${{ github.ref_name }}.zip
```

**Notes:**
- FFmpeg is copied into `dist\VidDownloader\` so `shutil.which("ffmpeg")` finds it when the
  install folder is on PATH, and the Inno Setup installer (Step 20) picks it up automatically.
- Tag format: `git tag v1.0.0 && git push origin v1.0.0`

> **Impl note:** Done. Created alongside existing `ci.yml`.

---

**Step 20 — Create `installer/setup.iss`** (new file, Inno Setup 6) ✅

Packages `dist\VidDownloader\` (FFmpeg already inside) into a one-click Windows installer with a
desktop shortcut and user-PATH entry so `shutil.which("ffmpeg")` works after install.

```iss
; installer/setup.iss
#define AppName    "Vid Downloader"
#define AppVersion "1.0.0"
#define AppExe     "VidDownloader.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=etreq
DefaultDirName={autopf}\VidDownloader
DefaultGroupName={#AppName}
OutputDir=..\installer_output
OutputBaseFilename=VidDownloader-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\VidDownloader\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Add app directory to user PATH so ffmpeg.exe is found by shutil.which()
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path";
  ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}'))

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKCU, 'Environment', 'Path', OrigPath)
  then begin Result := True; exit; end;
  Result := Pos(';' + Uppercase(Param) + ';',
                ';' + Uppercase(OrigPath) + ';') = 0;
end;
```

**Notes:**
- `PrivilegesRequired=lowest` allows install without admin (uses `%LocalAppData%\Programs\`).
- Compile locally: `iscc installer\setup.iss` (requires [Inno Setup 6](https://jrsoftware.org/isdl.php)).
- The `[Registry]` PATH entry takes effect immediately after the installer broadcasts the env-change
  message — no terminal restart required.

> **Impl note:** Done. Created `installer/` directory and `installer/setup.iss`. `installer_output/` (the compiled output dir) is not gitignored — add it if needed.

---

### Summary: new/changed files

| File | Change |
|------|--------|
| `QYT.py` | Load AppData `.env` before project `.env` |
| `src/first_run_wizard.py` | New — `needs_first_run()` + `FirstRunWizard` dialog |
| `vid downloader.pyw` | Add wizard call after `window.show()`; frozen-mode path fix |
| `pyproject.toml` | Add `[dependency-groups] dev = ["pyinstaller>=6.0"]` |
| `vid_downloader.spec` | New — PyInstaller build spec |
| `.github/workflows/release.yml` | New — tag-triggered build + GitHub release |
| `installer/setup.iss` | New — Inno Setup script |

### Verification

1. **Wizard** — delete `%APPDATA%\VidDownloader\.env`, run `uv run python "vid downloader.pyw"` → wizard appears; pick a folder; re-launch → wizard absent, chosen path used.
2. **PyInstaller build** — `uv run pyinstaller vid_downloader.spec` → `dist\VidDownloader\VidDownloader.exe` runs, icons load, downloads work.
3. **Release workflow** — push a `v0.0.1-test` tag → Actions job produces `VidDownloader-v0.0.1-test.zip` with `ffmpeg.exe` inside.
4. **Installer** — `iscc installer\setup.iss` → run installer → shortcut appears, `shutil.which("ffmpeg")` returns a path in a new terminal.
