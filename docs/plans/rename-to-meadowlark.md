# Rename: vid downloader → MeadowLark

## Context
The app is being rebranded from "Vid Downloader" to "MeadowLark". The GitHub repository has already been renamed from `Geneocide/vid-downloader` to `Geneocide/MeadowLark`. All user-facing strings, file names, build artifacts, config identifiers, and API URLs need to reflect the new name. Historical docs in `docs/plans/done/` and `.github/prompts/done/` are left as-is.

---

## Naming conventions applied

| Context | Old | New |
|---|---|---|
| Display (UI, titles) | `Vid Downloader` | `MeadowLark` |
| PascalCase (files, dirs, exe) | `VidDownloader` | `MeadowLark` |
| snake_case (spec, package) | `vid_downloader` | `meadowlark` |
| kebab-case (pyproject) | `vid-downloader` | `meadowlark` |
| Entry point filename | `vid downloader.pyw` | `meadowlark.pyw` |

---

## Step 1 — Rename files

| Old path | New path |
|---|---|
| `vid downloader.pyw` | `meadowlark.pyw` |
| `vid_downloader.spec` | `meadowlark.spec` |

Use `git mv` so history is preserved.

---

## Step 2 — Content changes by file

### `meadowlark.pyw` (after rename)
- Module docstring: `Vid Downloader - A PyQt6-based GUI application…` → `MeadowLark - A PyQt6-based GUI application…`
- Class docstring (line ~159): `Vid Downloader application` → `MeadowLark application`
- `__init__` docstring (line ~171): `Vid Downloader is a PyQt6-based GUI application` → `MeadowLark is a PyQt6-based GUI application`
- `self.setWindowTitle("Vid Downloader")` → `self.setWindowTitle("MeadowLark")`

### `meadowlark.spec` (after rename)
- `["vid downloader.pyw"]` → `["meadowlark.pyw"]`
- `name="VidDownloader"` → `name="MeadowLark"` (both the EXE and COLLECT blocks)

### `pyproject.toml`
- `name = "vid-downloader"` → `name = "meadowlark"`

### `README.md`
- `# Vid Downloader` → `# MeadowLark`
- `uv run python "vid downloader.pyw"` → `uv run python "meadowlark.pyw"`

### `installer/setup.iss`
- `#define AppName "Vid Downloader"` → `#define AppName "MeadowLark"`
- `#define AppExe  "VidDownloader.exe"` → `#define AppExe  "MeadowLark.exe"`
- `DefaultDirName={autopf}\VidDownloader` → `DefaultDirName={autopf}\MeadowLark`
- `OutputBaseFilename=VidDownloader-Setup-{#AppVersion}` → `OutputBaseFilename=MeadowLark-Setup-{#AppVersion}`
- `Source: "..\dist\VidDownloader\*"` → `Source: "..\dist\MeadowLark\*"`

### `.github/workflows/release.yml`
- `uv run pyinstaller vid_downloader.spec` → `uv run pyinstaller meadowlark.spec`
- `dist\VidDownloader\` → `dist\MeadowLark\` (two `Copy-Item` lines)
- `installer_output/VidDownloader-Setup-*.exe` → `installer_output/MeadowLark-Setup-*.exe`

### `QYT.py`
- `Path.home() / "AppData" / "Roaming" / "VidDownloader" / ".env"` → `… / "MeadowLark" / ".env"`

### `src/first_run_wizard.py`
- `_APPDATA_DIR = Path.home() / "AppData" / "Roaming" / "VidDownloader"` → `… / "MeadowLark"`
- `self.setWindowTitle("Welcome — Vid Downloader Setup")` → `"Welcome — MeadowLark Setup"`
- `"<b>Welcome to Vid Downloader!</b><br><br>"` → `"<b>Welcome to MeadowLark!</b><br><br>"`

### `src/version_utils.py`
- `"https://api.github.com/repos/Geneocide/vid-downloader/releases"` → `"https://api.github.com/repos/Geneocide/MeadowLark/releases"`

### `tests/test_version_utils.py`
- `"VidDownloader-Setup-99.9.9.exe"` → `"MeadowLark-Setup-99.9.9.exe"`
- `https://github.com/Geneocide/vid-downloader/releases/tag/v99.9.9` → `https://github.com/Geneocide/MeadowLark/releases/tag/v99.9.9` (two occurrences)

### `tests/test_private_video_handling.py`
- `Path(__file__).parent.parent / "vid downloader.pyw"` → `… / "meadowlark.pyw"`

---

## Files NOT changed
- `docs/plans/done/**` — archival, left as-is
- `.github/prompts/done/**` — archival, left as-is
- `build/` and `dist/` — generated artifacts, regenerated on next build
- `resources/icons/downFrog.ico` — icon filename is unrelated to the app name

---

## Verification
1. `git mv` renames appear correctly in `git status`
2. `uv run python meadowlark.pyw` launches with window title "MeadowLark"
3. `uv run pytest` passes (particularly `test_version_utils.py` and `test_private_video_handling.py`)
4. `uv run pyinstaller meadowlark.spec` builds to `dist\MeadowLark\MeadowLark.exe`
5. Installer script compiles to `installer_output\MeadowLark-Setup-*.exe`
