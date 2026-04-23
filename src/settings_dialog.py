"""Settings dialog for MeadowLark — runtime-mutable configuration backed by AppData .env."""

import shutil
from pathlib import Path
from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .config import (
    COOKIES_FILE,
    LABEL_BTN_720,
    LABEL_BTN_PLAYLISTS,
    LABEL_BTN_PODCASTS,
    LABEL_DROP_720,
    LABEL_DROP_1080,
    LABEL_DROP_AUDIO,
    LABEL_READY_TEXT,
    PLAYLISTS_720_FILE,
    PLAYLISTS_AUDIO_FILE,
    PLAYLISTS_FILE,
    PODCAST_AUTO_CHECK,
    PODCAST_CHECK_INTERVAL_MINUTES,
    PODCAST_MISC_OUTPUT_DIR,
    VIDEO_STORAGE_DIR,
)

# ============================================================================
# Help text for every setting key
# ============================================================================

HELP_TEXT: dict[str, str] = {
    "VID_DL_VIDEO_STORAGE_DIR": (
        "Directory where downloaded videos are saved.\n"
        "Changes take effect immediately for new downloads."
    ),
    "VID_DL_PODCAST_MISC_OUTPUT_DIR": (
        "Directory where podcast audio files (m4a) are saved.\n"
        "Changes take effect immediately for new downloads."
    ),
    "VID_DL_PLAYLISTS_FILE": (
        "Playlist file for 1080p video downloads.\n"
        "The file is copied into AppData so the original can be moved or deleted.\n"
        "Each line should be a YouTube playlist URL, optionally preceded by a #Comment line."
    ),
    "VID_DL_PLAYLISTS_720_FILE": (
        "Playlist file for 720p video downloads.\n"
        "The file is copied into AppData so the original can be moved or deleted.\n"
        "Each line should be a YouTube playlist URL, optionally preceded by a #Comment line."
    ),
    "VID_DL_PLAYLISTS_AUDIO_FILE": (
        "Playlist file for podcast/audio downloads.\n"
        "The file is copied into AppData so the original can be moved or deleted.\n"
        "Each line should be a YouTube playlist URL, optionally preceded by a #Comment line."
    ),
    "VID_DL_COOKIES_FILE": (
        "Path to a cookies.txt file exported from your browser.\n"
        "Used by yt-dlp for authenticated downloads (e.g. age-restricted videos).\n"
        "The file is NOT copied — it is referenced in place so browser extensions can keep it updated."
    ),
    "VID_DL_LABEL_DROP_1080": (
        "Display text for the 1080p drop target.\n"
        "Routing behaviour is unchanged regardless of display text."
    ),
    "VID_DL_LABEL_DROP_720": (
        "Display text for the 720p drop target.\n"
        "Routing behaviour is unchanged regardless of display text."
    ),
    "VID_DL_LABEL_DROP_AUDIO": (
        "Display text for the audio/podcast drop target.\n"
        "Routing behaviour is unchanged regardless of display text."
    ),
    "VID_DL_LABEL_READY_TEXT": (
        "Text shown in the status bar when the app is idle and ready for new downloads."
    ),
    "VID_DL_LABEL_BTN_PLAYLISTS": "Label for the 1080p Playlists button.",
    "VID_DL_LABEL_BTN_720": "Label for the 720p Playlists button.",
    "VID_DL_LABEL_BTN_PODCASTS": "Label for the YT Podcasts button.",
    "VID_DL_PODCAST_AUTO_CHECK": (
        "When enabled, the app automatically checks your podcast playlists on the schedule below.\n"
        "Disable to run checks manually only."
    ),
    "VID_DL_PODCAST_CHECK_INTERVAL_MINUTES": (
        "How often (in minutes) the app automatically checks podcast playlists.\n"
        "Range: 5–1440 minutes (5 min to 24 hours)."
    ),
}

# ============================================================================
# AppData path (mirrors QYT.py and first_run_wizard.py)
# ============================================================================

_APPDATA_DIR: Path = Path.home() / "AppData" / "Roaming" / "MeadowLark"
_USER_ENV: Path = _APPDATA_DIR / ".env"
_PLAYLISTS_APPDATA_DIR: Path = _APPDATA_DIR / "playlists"

# ============================================================================
# Runtime settings store
# ============================================================================

_runtime: dict[str, Any] = {}


def _init_runtime_settings() -> None:
    """Populate the runtime store from frozen config constants.  Call once at startup."""
    _runtime.update(
        {
            "VID_DL_VIDEO_STORAGE_DIR": str(VIDEO_STORAGE_DIR),
            "VID_DL_PODCAST_MISC_OUTPUT_DIR": str(PODCAST_MISC_OUTPUT_DIR),
            "VID_DL_PLAYLISTS_FILE": str(PLAYLISTS_FILE),
            "VID_DL_PLAYLISTS_720_FILE": str(PLAYLISTS_720_FILE),
            "VID_DL_PLAYLISTS_AUDIO_FILE": str(PLAYLISTS_AUDIO_FILE),
            "VID_DL_COOKIES_FILE": str(COOKIES_FILE),
            "VID_DL_LABEL_DROP_1080": LABEL_DROP_1080,
            "VID_DL_LABEL_DROP_720": LABEL_DROP_720,
            "VID_DL_LABEL_DROP_AUDIO": LABEL_DROP_AUDIO,
            "VID_DL_LABEL_READY_TEXT": LABEL_READY_TEXT,
            "VID_DL_LABEL_BTN_PLAYLISTS": LABEL_BTN_PLAYLISTS,
            "VID_DL_LABEL_BTN_720": LABEL_BTN_720,
            "VID_DL_LABEL_BTN_PODCASTS": LABEL_BTN_PODCASTS,
            "VID_DL_PODCAST_AUTO_CHECK": PODCAST_AUTO_CHECK,
            "VID_DL_PODCAST_CHECK_INTERVAL_MINUTES": PODCAST_CHECK_INTERVAL_MINUTES,
        }
    )


def get_setting(key: str) -> Any:
    """Return the current runtime value for *key*, or None if not registered."""
    return _runtime.get(key)


def _persist_setting(key: str, value: Any) -> None:
    """Write *key=value* to the AppData .env and update the in-memory store."""
    _APPDATA_DIR.mkdir(parents=True, exist_ok=True)

    # Read existing lines, replace the matching key, or append if absent.
    lines: list[str] = []
    if _USER_ENV.exists():
        lines = _USER_ENV.read_text(encoding="utf-8").splitlines(keepends=True)

    str_value = str(value) if not isinstance(value, bool) else str(value).lower()
    key_prefix = f"{key}="
    replaced = False
    for i, line in enumerate(lines):
        if line.startswith(key_prefix):
            lines[i] = f"{key}={str_value}\n"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={str_value}\n")

    _USER_ENV.write_text("".join(lines), encoding="utf-8")
    _runtime[key] = value


def _import_playlist_file(source_path: str, dest_name: str) -> str:
    """Copy *source_path* to the AppData playlists dir as *dest_name* and return the new path."""
    _PLAYLISTS_APPDATA_DIR.mkdir(parents=True, exist_ok=True)
    dest = _PLAYLISTS_APPDATA_DIR / dest_name
    shutil.copy2(source_path, dest)
    return str(dest)


# ============================================================================
# Widget helpers
# ============================================================================


def _make_help_button(key: str, parent: QWidget) -> QPushButton:
    btn = QPushButton("?", parent)
    btn.setFixedWidth(24)
    btn.setFlat(True)
    text = HELP_TEXT.get(key, "No help available.")
    btn.clicked.connect(lambda: QMessageBox.information(parent, "Help", text))
    return btn


def _make_dir_row(
    label: str, key: str, parent: QWidget
) -> tuple[QHBoxLayout, QLineEdit]:
    edit = QLineEdit(str(get_setting(key) or ""), parent)
    browse = QPushButton("Browse…", parent)
    help_btn = _make_help_button(key, parent)

    def _browse() -> None:
        chosen = QFileDialog.getExistingDirectory(parent, label, edit.text())
        if chosen:
            edit.setText(chosen)

    browse.clicked.connect(_browse)
    row = QHBoxLayout()
    row.addWidget(edit)
    row.addWidget(browse)
    row.addWidget(help_btn)
    return row, edit


def _make_file_row(
    label: str,
    key: str,
    parent: QWidget,
    filter_str: str = "All Files (*)",
    copy_to_appdata: bool = False,
    dest_name: str = "",
) -> tuple[QHBoxLayout, QLineEdit]:
    edit = QLineEdit(str(get_setting(key) or ""), parent)
    browse = QPushButton("Browse…", parent)
    help_btn = _make_help_button(key, parent)

    def _browse() -> None:
        chosen, _ = QFileDialog.getOpenFileName(parent, label, edit.text(), filter_str)
        if not chosen:
            return
        if copy_to_appdata and dest_name:
            chosen = _import_playlist_file(chosen, dest_name)
        edit.setText(chosen)

    browse.clicked.connect(_browse)
    row = QHBoxLayout()
    row.addWidget(edit)
    row.addWidget(browse)
    row.addWidget(help_btn)
    return row, edit


# ============================================================================
# Dialog
# ============================================================================


class SettingsDialog(QDialog):
    """Non-modal settings dialog.  Emits settings_changed with {env_var: new_value} on Apply."""

    settings_changed = pyqtSignal(dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)

        self._edits: dict[str, QLineEdit | QCheckBox | QSpinBox] = {}

        tabs = QTabWidget(self)
        tabs.addTab(self._build_downloads_tab(), "Downloads")
        tabs.addTab(self._build_playlists_tab(), "Playlists")
        tabs.addTab(self._build_interface_tab(), "Interface")
        tabs.addTab(self._build_automation_tab(), "Automation")

        buttons = QDialogButtonBox(self)
        apply_btn = buttons.addButton("Apply", QDialogButtonBox.ButtonRole.ApplyRole)
        close_btn = buttons.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        apply_btn.clicked.connect(self._apply)
        close_btn.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)
        self.setLayout(layout)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_downloads_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        row, edit = _make_dir_row("Video Directory", "VID_DL_VIDEO_STORAGE_DIR", self)
        self._edits["VID_DL_VIDEO_STORAGE_DIR"] = edit
        form.addRow(QLabel("Video directory:"), _wrap(row))

        row, edit = _make_dir_row(
            "Audio/Podcast Directory", "VID_DL_PODCAST_MISC_OUTPUT_DIR", self
        )
        self._edits["VID_DL_PODCAST_MISC_OUTPUT_DIR"] = edit
        form.addRow(QLabel("Audio directory:"), _wrap(row))

        tab.setLayout(form)
        return tab

    def _build_playlists_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        specs = [
            ("Playlists file (1080p):", "VID_DL_PLAYLISTS_FILE", "playlists.txt"),
            ("Playlists file (720p):", "VID_DL_PLAYLISTS_720_FILE", "720playlists.txt"),
            (
                "Playlists file (audio):",
                "VID_DL_PLAYLISTS_AUDIO_FILE",
                "audio playlists.txt",
            ),
        ]
        for lbl, key, dest in specs:
            row, edit = _make_file_row(
                lbl,
                key,
                self,
                filter_str="Text Files (*.txt);;All Files (*)",
                copy_to_appdata=True,
                dest_name=dest,
            )
            self._edits[key] = edit
            form.addRow(QLabel(lbl), _wrap(row))

        row, edit = _make_file_row(
            "Cookies file",
            "VID_DL_COOKIES_FILE",
            self,
            filter_str="Text Files (*.txt);;All Files (*)",
            copy_to_appdata=False,
        )
        self._edits["VID_DL_COOKIES_FILE"] = edit
        form.addRow(QLabel("Cookies.txt:"), _wrap(row))

        tab.setLayout(form)
        return tab

    def _build_interface_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        text_fields: list[tuple[str, str]] = [
            ("Drop label — 1080:", "VID_DL_LABEL_DROP_1080"),
            ("Drop label — 720:", "VID_DL_LABEL_DROP_720"),
            ("Drop label — audio:", "VID_DL_LABEL_DROP_AUDIO"),
            ("Ready text:", "VID_DL_LABEL_READY_TEXT"),
            ("Button — Playlists:", "VID_DL_LABEL_BTN_PLAYLISTS"),
            ("Button — 720 Playlists:", "VID_DL_LABEL_BTN_720"),
            ("Button — YT Podcasts:", "VID_DL_LABEL_BTN_PODCASTS"),
        ]
        for lbl, key in text_fields:
            edit = QLineEdit(str(get_setting(key) or ""), self)
            help_btn = _make_help_button(key, self)
            row = QHBoxLayout()
            row.addWidget(edit)
            row.addWidget(help_btn)
            self._edits[key] = edit
            form.addRow(QLabel(lbl), _wrap(row))

        tab.setLayout(form)
        return tab

    def _build_automation_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        auto_check = QCheckBox(self)
        auto_check.setChecked(bool(get_setting("VID_DL_PODCAST_AUTO_CHECK")))
        help_auto = _make_help_button("VID_DL_PODCAST_AUTO_CHECK", self)
        auto_row = QHBoxLayout()
        auto_row.addWidget(auto_check)
        auto_row.addWidget(help_auto)
        auto_row.addStretch()
        self._edits["VID_DL_PODCAST_AUTO_CHECK"] = auto_check
        form.addRow(QLabel("Auto-check podcasts:"), _wrap(auto_row))

        interval = QSpinBox(self)
        interval.setRange(5, 1440)
        interval.setSuffix(" min")
        interval.setValue(
            int(get_setting("VID_DL_PODCAST_CHECK_INTERVAL_MINUTES") or 60)
        )
        interval.setEnabled(auto_check.isChecked())
        help_interval = _make_help_button("VID_DL_PODCAST_CHECK_INTERVAL_MINUTES", self)
        interval_row = QHBoxLayout()
        interval_row.addWidget(interval)
        interval_row.addWidget(help_interval)
        interval_row.addStretch()
        self._edits["VID_DL_PODCAST_CHECK_INTERVAL_MINUTES"] = interval
        form.addRow(QLabel("Check interval:"), _wrap(interval_row))

        auto_check.toggled.connect(interval.setEnabled)

        tab.setLayout(form)
        return tab

    # ------------------------------------------------------------------
    # Apply logic
    # ------------------------------------------------------------------

    def _apply(self) -> None:
        changes: dict[str, Any] = {}
        for key, widget in self._edits.items():
            if isinstance(widget, QCheckBox):
                new_val: Any = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                new_val = widget.value()
            else:
                new_val = widget.text().strip()

            if new_val != get_setting(key):
                _persist_setting(key, new_val)
                changes[key] = new_val

        if changes:
            self.settings_changed.emit(changes)


# ============================================================================
# Internal helper
# ============================================================================


def _wrap(layout: QHBoxLayout) -> QWidget:
    """Wrap a QHBoxLayout in a plain QWidget so it can be used as a form value widget."""
    w = QWidget()
    w.setLayout(layout)
    return w
