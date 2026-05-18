"""
MeadowLark - A PyQt6-based GUI application for downloading and managing video and audio content from YouTube and other platforms using yt-dlp.

This application provides a user-friendly interface for batch downloading videos, playlists, and audio files with customizable options. It supports drag-and-drop, playlist selection, progress tracking, and automatic updates for yt-dlp.

Features:
- Drag-and-drop support for video/audio URLs.
- Batch downloading of playlists (1080p, 720p, audio-only).
- Custom output templates and post-processing (e.g., SponsorBlock, chapter modification).
- Progress bar and real-time log output.
- Optional archive checking to avoid duplicate downloads.
- Automatic detection and login for supported platforms (e.g., Nebula).
- Cookie-based authentication for YouTube.
- Update checker and one-click upgrade for yt-dlp.
- Integration with system keyring for secure credential storage.
- Opens download directory and sets up application icon resources on startup.

Usage:
- Run this script directly to launch the GUI.
- Drag URLs or select playlist options to queue downloads.
- Monitor progress and logs in the main window.
- Use the update button to check for and install yt-dlp updates.

Dependencies:
- Python 3.10+
- PyQt6
- yt-dlp
- hurry.filesize
- keyring
- Custom modules: QYT, UIClasses

Author: Gene
"""

import contextlib
import logging
import os
import queue
import shutil
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from os import startfile
from pathlib import Path
from typing import ClassVar
from urllib.parse import parse_qs, urlparse

import yt_dlp
from hurry.filesize import size
from PyQt6.QtCore import (
    QDir,
    QObject,
    QPoint,
    QProcess,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QCloseEvent,
    QFont,
    QIcon,
    QKeySequence,
    QSessionManager,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGridLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import QYT
import utils
from src import live_queue
from src.config import (
    ALWAYS_ON_TOP,
    ARCHIVE_PATH,
    COOKIES_FILE,
    LABEL_BTN_720,
    LABEL_BTN_PLAYLISTS,
    LABEL_BTN_PODCASTS,
    LABEL_DROP_720,
    LABEL_DROP_1080,
    LABEL_DROP_AUDIO,
    LABEL_OUTPUT_FONT_NAME,
    LABEL_OUTPUT_FONT_SIZE,
    LABEL_READY_TEXT,
    LIVE_QUEUE_CHECK_INTERVAL_MINUTES,
    LIVE_QUEUE_FILE,
    PLAYLISTS_720_FILE,
    PLAYLISTS_AUDIO_FILE,
    PLAYLISTS_FILE,
    PODCAST_AUTO_CHECK,
    PODCAST_MISC_OUTPUT_DIR,
    VENV_SCRIPTS_DIR,
    VIDEO_STORAGE_DIR,
    YDL_COMMON_ERRORS,
    YDL_EXTRACTION_ERRORS,
)
from src.first_run_wizard import FirstRunWizard, needs_first_run
from src.history_dialog import HistoryDialog
from src.match_filter import build_match_filter
from src.podcast_filtering import (
    PODCAST_MIN_DURATION_SECONDS,
    append_to_archive_and_mark_skipped,
    check_sponsorblock_for_video_id,
    format_timestamp_readable,
    load_downloaded_video_ids,
    parse_scheduled_time_from_error,
    parse_video_timestamp,
)
from src.podcast_helpers import fetch_latest_accessible_entry
from src.settings_dialog import (
    SettingsDialog,
    _init_runtime_settings,
    _persist_setting,
    get_setting,
)
from src.url_utils import extract_playlist_id
from UIClasses import DropLabel, PlaylistButton, PlaylistDialog

logger = logging.getLogger(__name__)

# Helper for podcast playlist handling -------------------------------------------------
#
# YouTube sometimes reports that the *latest* video in a playlist is a "Private
# video".  Calling ``yt_dlp`` with ``playlistend=1`` will either raise an exception
# containing the words "Private video" or return an info dict whose one entry has a
# title beginning with that string.  In both cases the normal podcast-check logic
# treats that as a hard error and flags the entire playlist as broken.  The desired
# behaviour is instead to ignore the private item and pretend the previous accessible
# video is the latest.  ``_fetch_latest_accessible_entry`` encapsulates that logic so
# it can be exercised by unit tests.
#
# New strategy (2026-02-27): instead of scraping the entire playlist when a
# private video is detected we incrementally request the last N entries, growing
# N by one each attempt.  This avoids a full playlist fetch in the common case of
# a single private stub.  A limit prevents runaway loops.

# how many entries to look ahead before giving up - see src/podcast_helpers.py


# Constants
MAX_INT_PROGRESS = 2147483647
THREAD_QUIT_TIMEOUT_MS = 2000
THREAD_TERMINATE_TIMEOUT_MS = 1000


def _make_podcast_status_entry(
    podcast: str,
    url: str,
    status: str = "(unknown)",
    latest_date: str = "(unknown)",
    **kwargs: object,
) -> dict:
    """Create a podcast status entry dict with standard keys and optional extensions."""
    return {
        "podcast": podcast,
        "latest_date": latest_date,
        "status": status,
        "url": url,
        **kwargs,
    }


class MyWindow(QWidget):
    """
    MyWindow - A PyQt6-based main window for the MeadowLark application, providing a GUI for downloading and managing video and audio content from YouTube and other platforms.

    Features include playlist and audio download options, drag-and-drop support, progress tracking, log display, update checking, and integration with custom download queue and processing logic.
    """

    live_queue_log = pyqtSignal(str)

    _BRAVE_PATHS: ClassVar[list[str]] = [
        r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
        r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
    ]

    def __init__(self) -> None:
        """
        MeadowLark is a PyQt6-based GUI application for downloading and managing video and audio content from YouTube and other platforms using yt-dlp.

        Provides a user-friendly interface for batch downloading videos, playlists, and audio files with customizable options. Features include drag-and-drop support, playlist selection, progress tracking, real-time logging, archive checking, automatic yt-dlp updates, and secure credential storage via keyring.

        Run this script to launch the GUI, queue downloads, monitor progress, and manage updates.
        """
        super().__init__()
        self.setWindowTitle("MeadowLark")
        if ALWAYS_ON_TOP:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        _init_runtime_settings()
        self._settings_dialog: SettingsDialog | None = None
        self._ready_text = LABEL_READY_TEXT

        self._setup_ui_layout()
        self._setup_queue_and_downloader()
        self._setup_timers()
        self._setup_podcast_state()

        QShortcut(QKeySequence("Ctrl+H"), self).activated.connect(self._show_history)
        QShortcut(QKeySequence("Ctrl+U"), self).activated.connect(
            self._start_app_update_check
        )

        self.live_queue_log.connect(self.handle_log_entry)

        self.playlist_comments = {}

        update_available, _, _ = utils.is_yt_dlp_update_available()
        self.buttonUpdate.setVisible(update_available)

        self._maybe_start_auto_app_update_check()

    def _build_podcast_container(self) -> QWidget:
        """Build the podcast button + indicator container widget."""
        self.buttonAudioPlaylists = PlaylistButton(
            LABEL_BTN_PODCASTS,
            str(PLAYLISTS_AUDIO_FILE),
        )
        self.buttonAudioPlaylists.setMaximumWidth(140)
        self.buttonAudioPlaylists.clicked.connect(
            lambda: self.playlist_button_clicked("audio_playlists"),
        )
        self.podcastIndicator = QPushButton("", self)
        self.podcastIndicator.setFixedSize(34, 34)
        self.podcastIndicator.setFlat(True)
        self.podcastIndicator.setStyleSheet(
            "font-size:18px;background:transparent;border:0px",
        )
        self.podcastIndicator.setToolTip("Podcast status")
        self.podcastIndicator.clicked.connect(self._show_podcast_status)
        container = QWidget()
        inner = QGridLayout()
        inner.setContentsMargins(0, 0, 0, 0)
        inner.addWidget(self.buttonAudioPlaylists, 0, 0)
        inner.addWidget(self.podcastIndicator, 0, 1)
        container.setLayout(inner)
        return container

    def _setup_ui_layout(self) -> None:
        """Create and arrange all UI widgets and layout."""
        layout = QGridLayout()

        self.buttonPlaylists = PlaylistButton(LABEL_BTN_PLAYLISTS, str(PLAYLISTS_FILE))
        self.buttonPlaylists.clicked.connect(
            lambda: self.playlist_button_clicked("1080playlists"),
        )
        self.button720Playlists = PlaylistButton(LABEL_BTN_720, str(PLAYLISTS_720_FILE))
        self.button720Playlists.clicked.connect(
            lambda: self.playlist_button_clicked("720playlists"),
        )
        self.checkIgnoreArchive = QCheckBox("Ignore Archive?")
        self.checkIgnoreArchive.setChecked(False)
        self.checkSkipDownload = QCheckBox("Skip Download")
        self.checkSkipDownload.setChecked(False)
        self.buttonUpdate = QPushButton("⤓")
        self.buttonUpdate.clicked.connect(lambda: self.request_detected([], "Update"))
        self.buttonUpdate.setVisible(True)
        self.buttonSettings = QPushButton("⚙")
        self.buttonSettings.clicked.connect(self._open_settings)
        self.label1080 = DropLabel(
            LABEL_DROP_1080, "#424769", self.request_detected, source_key="1080"
        )
        self.label720 = DropLabel(
            LABEL_DROP_720, "#7077A1", self.request_detected, source_key="720"
        )
        self.labelAudio = DropLabel(
            LABEL_DROP_AUDIO, "#FF9843", self.request_detected, source_key="audio"
        )
        self.labelOutput = QLabel(self._ready_text)
        self.labelOutput.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.labelOutput.setFont(QFont(LABEL_OUTPUT_FONT_NAME, LABEL_OUTPUT_FONT_SIZE))
        self.barProgress = QProgressBar()
        self.logEdit = QPlainTextEdit(readOnly=True)

        layout.addWidget(self.checkSkipDownload, 0, 0)
        layout.addWidget(self.checkIgnoreArchive, 0, 1)
        layout.addWidget(self.buttonUpdate, 0, 2)
        layout.addWidget(self.buttonSettings, 0, 3)
        layout.addWidget(self.buttonPlaylists, 1, 0)
        layout.addWidget(self.button720Playlists, 1, 1)
        layout.addWidget(self._build_podcast_container(), 1, 2, 1, 2)
        layout.setColumnStretch(2, 1)
        layout.addWidget(self.label1080, 2, 0)
        layout.addWidget(self.label720, 2, 1)
        layout.addWidget(self.labelAudio, 2, 2, 1, 2)
        layout.addWidget(self.labelOutput, 3, 0, 1, 4)
        layout.addWidget(self.barProgress, 4, 0, 1, 4)
        layout.addWidget(self.logEdit, 5, 0, 1, 4)

        self.setLayout(layout)

    def _setup_queue_and_downloader(self) -> None:
        """Set up download queue, downloader, and signal connections."""
        self.downloadQueue = queue.Queue()
        self.downloader = QYT.QYTQueue(self.downloadQueue)
        self.downloader.message_changed.connect(self.handle_log_entry)
        self.downloader.queue_empty.connect(self.handle_queue_empty)
        self.downloader.history_entry_added.connect(self._on_history_entry_added)
        self.downloader.start()

    def _setup_timers(self) -> None:
        """Create and start timers for live queue and podcast checks."""
        # Live queue setup and periodic recheck every 30 minutes
        self.live_queue_path = LIVE_QUEUE_FILE
        self.live_queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.live_queue_path.touch(exist_ok=True)
        self.live_check_timer = QTimer(self)
        self.live_check_timer.setInterval(LIVE_QUEUE_CHECK_INTERVAL_MINUTES * 60 * 1000)
        self.live_check_timer.timeout.connect(self.check_live_queue)
        self.live_check_timer.start()
        # Do an initial check on startup
        self.check_live_queue()

        # Schedule hourly automated YT Podcasts check (runs at :15 past the hour)
        if PODCAST_AUTO_CHECK:
            self._schedule_hourly_podcast_checks()

    def _setup_podcast_state(self) -> None:
        """Initialize podcast-related attributes and state."""
        self._podcast_pending_urls: set[str] = set()
        self._last_podcast_check_error = False
        self._podcast_check_running = False
        # Keep worker/thread refs so they don't get GC'd while running
        self._podcast_worker = None
        self._podcast_worker_thread = None
        # Cache the last podcast statuses (populated after each background check)
        self._podcast_last_statuses: list[dict] = []
        # Latest-URL cache: maps playlist_url -> {"latest_url": str, "latest_ts": int|None, "fetched_at": float}
        self._podcast_latest_url_cache: dict[str, dict] = {}
        # track podcasts for which a Download Now request is in progress
        self._podcasts_downloading: set[str] = set()
        # default indicator to unknown/all good
        self._set_podcast_indicator("all_good")

        # Ensure podcast worker threads are shut down on application exit
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._shutdown_podcast_thread)

    def _load_playlist_urls(self, source: str) -> list[dict[str, str]] | None:
        """Load URLs and associated comments from playlist file for the given source, or return None."""
        playlists_path = utils.get_playlist_file_for_source(source)
        if playlists_path:
            try:
                playlist_data = []
                last_comment = None
                with Path(playlists_path).open("r", encoding="utf-8") as file:
                    for line in file:
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("#"):
                            last_comment = line[1:].strip()
                        else:
                            playlist_data.append({"url": line, "comment": last_comment})
                            last_comment = None  # Reset for next URL
            except FileNotFoundError:
                print("File not found.")
                return None
            else:
                return playlist_data
        return None

    def _setup_podcast_check(self, urls: list, ydl_opts: dict) -> None:
        """Set up background podcast check for SponsorBlock info."""
        # If a check is already running, skip this trigger
        if getattr(self, "_podcast_check_running", False):
            self.logEdit.appendPlainText(
                "Podcast check already running; skipping this trigger.",
            )
        else:
            # Indicate check in progress and run off the UI thread
            self._podcast_check_running = True
            self._set_podcast_indicator("checking")
            self.labelOutput.setText(
                "Checking podcasts for SponsorBlock info...",
            )

            # Avoid passing Qt QObject instances (logger/progress hooks) into worker threads.
            worker_ydl_opts = dict(ydl_opts)
            worker_ydl_opts.pop("logger", None)
            worker_ydl_opts.pop("progress_hooks", None)
            worker = self._PodcastCheckWorker(
                self._filter_audio_playlist_urls,
                urls,
                worker_ydl_opts,
            )
            thread = QThread(self)
            thread.setObjectName("PodcastCheckThread")
            worker.moveToThread(thread)
            thread.started.connect(worker.run)
            # When the thread finishes, log it and update the status label (connect as separate slots)
            thread.finished.connect(
                lambda: self.logEdit.appendPlainText(
                    "Podcast check thread finished.",
                ),
            )
            thread.finished.connect(
                lambda: self.labelOutput.setText(self._ready_text),
            )

            # Store references to avoid GC while running
            self._podcast_worker = worker
            self._podcast_worker_thread = thread

            def _on_finished(
                to_download: list,
                pending: list,
                had_error: bool,
                messages: list[str],
                statuses: list[str],
            ) -> None:
                # Handle results back on the main thread
                try:
                    self._on_podcast_check_finished(
                        to_download,
                        pending,
                        had_error,
                        ydl_opts,
                        messages,
                        statuses,
                    )
                finally:
                    # Clear stored refs
                    self._podcast_worker = None
                    self._podcast_worker_thread = None

            worker.finished.connect(_on_finished)
            worker.finished.connect(thread.quit)
            worker.finished.connect(worker.deleteLater)
            thread.finished.connect(thread.deleteLater)
            try:
                thread.start()
                # Helpful log for debugging repeated starts
                self.logEdit.appendPlainText(
                    "Started podcast check (background thread).",
                )
            except RuntimeError as e:
                self.logEdit.appendPlainText(
                    f"Failed to start podcast check thread: {e}",
                )
                utils.log_exception(
                    e,
                    "Failed to start podcast check thread",
                )
                self._podcast_check_running = False
                self._set_podcast_indicator("error")

    def _handle_playlist_dialog(self, urls: list, source: str) -> dict | None:
        """Handle playlist dialog for individual playlists, return playlist_items or None to cancel."""
        if "list=" in urls[0] and "playlist" not in source:
            with yt_dlp.YoutubeDL({"extract_flat": "in_playlist"}) as ydl:
                info = ydl.extract_info(urls[0], download=False)
                playlist_count = info["playlist_count"]
                dialog = PlaylistDialog(playlist_count)
                if dialog.exec():
                    playlist_input = dialog.get_playlist_input()
                    # a blank return will set no option so default to downloading whole playlist
                    properties = {}
                    if playlist_input:
                        properties["playlist_items"] = playlist_input
                    if source != "audio":
                        source += "playlists"
                    return properties
                # will cancel playlist download
                return None
        return {}

    def playlist_button_clicked(self, source: str) -> None:
        """
        Handle playlist button click with optional confirmation if Ignore Archive is checked.

        Args:
            source (str): The source/playlist type (e.g., "1080playlists", "720playlists", "audio_playlists").
        """
        if self.checkIgnoreArchive.isChecked():
            reply = QMessageBox.warning(
                self,
                "Ignore Archive Enabled",
                "You have 'Ignore Archive?' checked. This will re-download previously downloaded videos.\n\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
        self.request_detected([], source)

    def append_properties(self, dictionary: dict, properties: dict) -> dict:
        """Merge properties into dictionary recursively."""
        # Merge properties into dictionary recursively using the shared utility.
        return utils.merge_dicts_recursive(dictionary, properties)

    def request_detected(self, urls: list, source: str) -> None:
        """
        Handle a detected download request by preparing options, updating URLs if needed, and queuing the download task.

        Args:
            urls (list): List of URLs to process.
            source (str): The source type or action (e.g., playlist type or 'Update').

        If the source is 'Update', triggers the update process. Otherwise, prepares yt-dlp options, merges additional properties, and enqueues the download with progress and log handlers.
        """
        if source == "Update":
            self.do_updates()
            return
        qhook, qlogger, ydl_opts = self._create_download_context()

        # Load playlist URLs if applicable
        if not urls:  # Only load from file if no URLs provided (e.g., button press)
            playlist_data = self._load_playlist_urls(source)
            if playlist_data is not None:
                urls = [item["url"] for item in playlist_data]
                self.playlist_comments.clear()
                for item in playlist_data:
                    if item["comment"]:
                        parsed = urlparse(item["url"])
                        query = parse_qs(parsed.query)
                        if "list" in query:
                            pl_id = query["list"][0]
                            self.playlist_comments[pl_id] = item["comment"]

        properties = self.get_options(urls, source)
        if properties:
            ydl_opts = self.append_properties(ydl_opts, properties)
            if ydl_opts:
                # Provide metadata for history logging
                ydl_opts["qmeta"] = {
                    "site": utils.detect_site_from_urls(urls),
                    "type": source,
                }
                # Pass playlist comments for fallback folder naming
                if (
                    source in ["720playlists", "1080playlists"]
                    and self.playlist_comments
                ):
                    ydl_opts["qmeta"]["playlist_comments"] = self.playlist_comments

                # Special handling for YT Podcasts: filter new episodes <24h without SponsorBlock
                if source == "audio_playlists":
                    self._setup_podcast_check(urls, ydl_opts)
                else:
                    self.downloadQueue.put((urls, ydl_opts))
                    self._wire_download_signals(qhook, qlogger)
                    self.barProgress.setRange(0, 1)

    def skip_downloading(self, urls: list, source: str) -> None:
        """Skip downloading the given URLs for the source."""
        self.labelOutput.setText("Skipping downloads.")
        qlogger = QYT.QLogger(self.downloadQueue)
        total_added = 0
        archive_path = ARCHIVE_PATH
        # Read existing IDs using centralized function
        existing_ids = load_downloaded_video_ids(str(archive_path))
        for url in urls:
            # Use extract_flat="in_playlist" for playlists, True for single videos
            ydl_opts = {
                "extract_flat": "in_playlist" if "lists" in source else True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                entries = info.get("entries", [info])
                with archive_path.open("a", encoding="utf-8") as archive:
                    for entry in entries:
                        video_id = entry.get("id")
                        if video_id and video_id not in existing_ids:
                            archive.write(f"youtube {video_id}\n")
                            total_added += 1
                            qlogger.debug("Added to archive: youtube %(video_id)s")
        self.labelOutput.setText("IDs added to archive.")
        self.barProgress.setRange(0, 1)
        self.barProgress.setValue(1)
        self.logEdit.appendPlainText(
            f"Archive-only mode: {total_added} IDs written.",
        )
        self.handle_queue_empty()

    def get_options(
        self,
        urls: list,
        source: str,
        skip_playlist_dialog: bool = False,
    ) -> dict | None:
        """
        Build yt-dlp options dict based on URLs and source type.

        Args:
            urls: List of URLs to process.
            source: The source type (e.g., "1080playlists", "audio").
            skip_playlist_dialog: If True, bypass playlist dialog during live-queue check.

        Returns:
            Dict of yt-dlp options, or None if download should be skipped/cancelled.
        """
        if self.checkSkipDownload.isChecked():
            self.skip_downloading(urls, source)
            return None

        # If a playlist file contained no URLs, bail out early to avoid errors
        if not urls:
            self.logEdit.appendPlainText(f"No URLs found for source: {source}")
            return None

        properties = {}

        # ignore archive checkbox
        if not self.checkIgnoreArchive.isChecked():
            properties["download_archive"] = str(ARCHIVE_PATH)

        # detect if YT
        if "youtube.com" in urls[0]:
            # Use a custom match_filter that records live videos for later
            properties["match_filter"] = self.make_match_filter(source)

        # strip out unnecessary parts of URL if dropping from Watch Later
        urls = [url.split("&list=WL")[0] for url in urls]

        if not skip_playlist_dialog:
            # Handle individual playlist dialog
            playlist_props = self._handle_playlist_dialog(urls, source)
            if playlist_props is None:
                return None  # cancelled
            properties.update(playlist_props)

        # Get source-specific options
        source_props = utils.get_source_options(source)
        properties.update(source_props)

        return properties

    def handle_log_entry(self, entry: str) -> None:
        """
        Append a log entry to the log display and updates the output label if a merge operation is detected.

        Args:
            entry: The log message to display.
        """
        if "[Merger]" in entry:
            self.labelOutput.setText("Merging! This can take a while...")
        self.logEdit.appendPlainText(entry)

    def handle_info_changed(self, d: dict) -> None:
        """
        Update the progress bar and output label with current download status, including downloaded size, total size, speed, and ETA.

        Args:
            d (dict): Dictionary containing download progress information.
        """
        max_int = MAX_INT_PROGRESS
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get(
                "total_bytes_estimate",
                round(d.get("total_bytes_estimate", 0)),
            )
            downloaded = d.get("downloaded_bytes", 0)
            speed = d.get("speed", 0)
            if not speed:
                speed = 0
            output = f"{size(downloaded)} of {size(total)} at {size(speed)}/s"
            if d.get("eta"):
                output += f" | ETA: {timedelta(seconds=round(d.get('eta')))}"
            self.labelOutput.setText(output)
            if total is not None:
                if total > max_int:
                    self.barProgress.setMaximum(max_int)
                    self.barProgress.setValue(int(downloaded / total * max_int))
                else:
                    self.barProgress.setMaximum(int(total))
                    self.barProgress.setValue(downloaded)

    def handle_queue_empty(self) -> None:
        """Update the output label to indicate that the download queue is ready and update podcast indicator if applicable."""
        self.labelOutput.setText(self._ready_text)
        # If podcast downloads finished, reflect pending/all_good state
        if self._podcast_pending_urls:
            self._set_podcast_indicator("pending")
        # Only set to all_good if not currently running
        elif not getattr(self, "_podcast_check_running", False):
            # If previous check had an error, show error
            if getattr(self, "_last_podcast_check_error", False):
                self._set_podcast_indicator("error")
            else:
                self._set_podcast_indicator("all_good")

        # mark any podcasts that were downloading as completed
        if self._podcasts_downloading:
            if getattr(self, "_podcast_last_statuses", None):
                for s in self._podcast_last_statuses:
                    if s.get("url") in self._podcasts_downloading:
                        s["status"] = "Downloaded"
                # refresh table UI if visible
                with contextlib.suppress(Exception):
                    self._refresh_podcast_status_dialog()
            # clear the set now that we've updated statuses
            self._podcasts_downloading.clear()

        # Cleanup any stored qhook/logger refs to allow GC now that downloads finished
        if hasattr(self, "_active_qhooks"):
            self._active_qhooks.clear()

    class _AppUpdateWorker(QObject):
        """Worker that checks GitHub Releases for a newer app version off the GUI thread."""

        finished = pyqtSignal(
            bool, str, str
        )  # (update_available, latest_tag, download_url)

        def run(self) -> None:
            update_available, tag, url = utils.is_app_update_available()
            self.finished.emit(bool(update_available), tag or "", url or "")

    class _PodcastCheckWorker(QObject):
        """Worker that runs podcast playlist expansion and SponsorBlock checks off the GUI thread."""

        # finished: to_download, pending, had_error, messages, statuses
        finished = pyqtSignal(list, list, bool, list, list)

        def __init__(self, func: Callable, urls: list, ydl_opts: dict) -> None:
            super().__init__()
            self.func = func
            self.urls = urls
            self.ydl_opts = ydl_opts
            # Best-effort cancellation flag (worker cooperatively checks this)
            self._stop_requested = False

        def request_stop(self) -> None:
            """Signal the worker to attempt to stop (best-effort)."""
            self._stop_requested = True

        def run(self) -> None:
            errors: list[str] = []
            statuses: list[dict] = []
            to_download, pending, had_error = [], [], False
            try:
                # Honor stop requests before starting heavy work
                if self._stop_requested:
                    errors.append(
                        "Podcast check aborted before start (stop requested).",
                    )
                    to_download, pending, had_error = [], [], True
                else:
                    result = self.func(self.urls, self.ydl_opts)
                    # Support multiple return shapes:
                    # - (to_download, pending, had_error)
                    # - (to_download, pending, had_error, messages)
                    # - (to_download, pending, had_error, messages, statuses)
                    if isinstance(result, tuple):
                        if len(result) == 5:
                            to_download, pending, had_error, errors, statuses = result
                        elif len(result) == 4:
                            to_download, pending, had_error, errors = result
                        else:
                            to_download, pending, had_error = result
                    else:
                        to_download, pending, had_error = result
                    # If a stop was requested while running, treat as aborted
                    if self._stop_requested:
                        errors.append("Podcast check aborted (stop requested).")
                        to_download, pending, had_error = [], [], True
            except Exception as exc:  # noqa: BLE001
                to_download, pending, had_error = [], [], True
                errors.append(f"Podcast check worker exception: {exc}")
                utils.log_exception(exc, "Podcast check worker exception")
            # Emit results back to the main thread; the main thread will perform any GUI logging.
            with contextlib.suppress(RuntimeError):
                self.finished.emit(to_download, pending, had_error, errors, statuses)
            # If the main thread or receiver has gone away, swallow to avoid crashing

    # --- Live queue management ---
    def make_match_filter(self, source: str) -> Callable:
        """Build a match_filter that skips live/upcoming videos and queues them."""
        return build_match_filter(
            source,
            add_to_queue_fn=self.add_to_live_queue,
            log_fn=self.live_queue_log.emit,
        )

    def load_live_queue(self) -> live_queue.LiveQueueEntries:
        """Load live queue entries; returns {url: (source, playlist_id)}."""
        return live_queue.load_live_queue(self.live_queue_path)

    def save_live_queue(self, entries: live_queue.LiveQueueEntries) -> None:
        """Save the live queue entries to file."""
        live_queue.save_live_queue(self.live_queue_path, entries)

    def _create_download_context(self) -> tuple[QYT.QHook, QYT.QLogger, dict]:
        """Create a fresh QHook, QLogger, and base ydl_opts dict."""
        qhook = QYT.QHook()
        qlogger = QYT.QLogger(self.downloadQueue)
        ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)
        return qhook, qlogger, ydl_opts

    def _fork_download_context(
        self,
        base_opts: dict,
    ) -> tuple[QYT.QHook, QYT.QLogger, dict]:
        """Create a fresh QHook/QLogger and return a copy of base_opts with them wired in."""
        qhook = QYT.QHook()
        qlogger = QYT.QLogger(self.downloadQueue)
        opts = dict(base_opts)
        opts["logger"] = qlogger
        opts["progress_hooks"] = [qhook]
        return qhook, qlogger, opts

    def _wire_download_signals(self, qhook: QYT.QHook, qlogger: QYT.QLogger) -> None:
        """Connect qhook/qlogger signals to the main window handler slots."""
        qhook.info_changed.connect(self.handle_info_changed)
        qlogger.message_changed.connect(self.handle_log_entry)

    def add_to_live_queue(
        self,
        url: str,
        source: str,
        playlist_id: str | None = None,
    ) -> None:
        """Add a URL to the live queue."""
        live_queue.add_to_live_queue(self.live_queue_path, url, source, playlist_id)

    def check_live_queue(self) -> None:
        """Check the live queue for ended streams and queue them for download."""
        entries = self.load_live_queue()
        if not entries:
            return
        remaining: dict[str, tuple[str, str | None]] = {}
        for url, (source, playlist_id) in entries.items():
            try:
                with yt_dlp.YoutubeDL(
                    {
                        "quiet": True,
                        "skip_download": True,
                        "cookiefile": get_setting("VID_DL_COOKIES_FILE")
                        or str(COOKIES_FILE),
                        "extract_flat": True,
                    },
                ) as ydl:
                    info = ydl.extract_info(url, download=False)
                if info is None:
                    remaining[url] = (source, playlist_id)
                    continue
                is_live = info.get("is_live")
                live_status = info.get("live_status")
                if is_live or live_status in ("is_live", "is_upcoming"):
                    # Still live; keep it in the queue
                    remaining[url] = (source, playlist_id)
                else:
                    self.logEdit.appendPlainText(
                        f"Live ended, queued: {url} [{source}]",
                    )
                    qhook, qlogger, ydl_opts = self._create_download_context()
                    properties = self.get_options(
                        [url],
                        source,
                        skip_playlist_dialog=True,
                    )
                    if properties:
                        # Don't re-apply match_filter: stream already confirmed ended
                        properties.pop("match_filter", None)
                        ydl_opts = self.append_properties(ydl_opts, properties)
                        qmeta: dict = {
                            "site": utils.detect_site_from_urls([url]),
                            "type": source,
                        }
                        if playlist_id:
                            playlist_comments = utils.load_playlist_comments_for_source(
                                source,
                            )
                            if playlist_comments:
                                qmeta["playlist_comments"] = playlist_comments
                                qmeta["playlist_id"] = playlist_id
                        ydl_opts["qmeta"] = qmeta

                        self.downloadQueue.put(([url], ydl_opts))
                        self._wire_download_signals(qhook, qlogger)
            except YDL_EXTRACTION_ERRORS as e:
                # If any error in checking, keep it for later
                self.logEdit.appendPlainText(
                    f"Error checking live url {url}: {e}",
                )
                utils.log_exception(e, f"Error checking live url {url}")
                remaining[url] = (source, playlist_id)
            except Exception as e:  # noqa: BLE001
                self.logEdit.appendPlainText(
                    f"Unexpected error checking live url {url}: {e}",
                )
                utils.log_exception(e, f"Unexpected error checking live url {url}")
                remaining[url] = (source, playlist_id)
        self.save_live_queue(remaining)

    def _episode_already_archived(
        self,
        vid: str,
        existing_ids: set[str],
        status_entry: dict,
    ) -> bool:
        if vid in existing_ids:
            status_entry["status"] = "Downloaded"
            return True
        return False

    def _skip_if_update_episode(
        self,
        entry: dict,
        vid: str,
        webpage: str,
        archive_path: str | None,
        existing_ids: set[str],
        messages: list[str],
        status_entry: dict,
    ) -> bool:
        title = entry.get("title", "") or ""
        if "(Update)" not in title:
            return False
        append_to_archive_and_mark_skipped(
            archive_path,
            vid,
            existing_ids,
            title,
            messages,
        )
        status_entry["status"] = "Skipped (Update)"
        QYT.HistoryLogger().log_skip(
            site=utils.detect_site_from_urls([webpage]),
            dtype="audio_playlists",
            title=title,
            reason="Update exception",
        )
        return True

    def _skip_if_short_duration(
        self,
        entry: dict,
        vid: str,
        webpage: str,
        archive_path: str | None,
        existing_ids: set[str],
        messages: list[str],
        status_entry: dict,
    ) -> bool:
        duration = entry.get("duration")
        title = entry.get("title", "") or ""
        if duration is None or duration >= PODCAST_MIN_DURATION_SECONDS:
            return False
        append_to_archive_and_mark_skipped(
            archive_path,
            vid,
            existing_ids,
            title,
            messages,
            reason="Short duration (<3 min)",
        )
        status_entry["status"] = "Skipped Short"
        QYT.HistoryLogger().log_skip(
            site=utils.detect_site_from_urls([webpage]),
            dtype="audio_playlists",
            title=title,
            reason="Short duration (<3 min)",
        )
        return True

    def _classify_episode_by_age(
        self,
        vid: str,
        webpage: str,
        ts: float | None,
        now_ts: float,
        playlist_label: str,
        to_download: list,
        pending: list,
        status_entry: dict,
        *,
        bypass_sponsorblock_wait: bool = False,
    ) -> None:
        obj = {"url": webpage, "playlist": playlist_label}
        if ts is None:
            to_download.append(obj)
            status_entry["status"] = "Ready"
            return
        status_entry["latest_date"] = format_timestamp_readable(ts)
        if ts > now_ts:
            status_entry["status"] = "Upcoming"
            status_entry["recheck_ts"] = ts
            return
        age_seconds = now_ts - ts
        if bypass_sponsorblock_wait or age_seconds >= 24 * 60 * 60:
            to_download.append(obj)
            status_entry["status"] = "Ready"
            return
        site = utils.detect_site_from_urls([webpage])
        if site != "youtube" or check_sponsorblock_for_video_id(vid):
            to_download.append(obj)
            status_entry["status"] = "Ready"
        else:
            pending.append(obj)
            status_entry["status"] = "Pending SponsorBlock"

    def _filter_audio_playlist_urls(  # noqa: C901, PLR0912, PLR0915
        self,
        urls: list,
        ydl_opts: dict,
        *,
        bypass_sponsorblock_wait: bool = False,
    ) -> tuple[list, list, bool, list, list]:
        """
        Expand playlist URLs and return enriched objects with per-episode URL and resolved playlist label.

        Returns: (to_download_objs, pending_objs, had_error, messages, statuses)
        where each obj is {"url": <video_url>, "playlist": <playlist_label>}.

        Only the most recent item in each playlist is inspected to keep work
        minimal.  If the latest entry is a private video, this used to cause a
        hard error and mark the entire podcast as broken; we now detect that
        case, skip the private entry and pretend the previous accessible video
        is the latest.  ``messages`` will include an informational note and
        ``had_error`` remains False when skipping a private item.

        pending_urls is a
        list of video URLs for which SponsorBlock info was not yet present. had_error will be True
        if any errors occurred during expansion. messages is a list of human-readable strings to
        be logged from the main thread. statuses is a list of dicts with {podcast, latest_date, status, url}.
        """
        to_download: list[dict] = []
        pending: list[dict] = []
        had_error = False
        messages: list[str] = []
        statuses: list[dict] = []
        archive_path = ydl_opts.get("download_archive")
        existing_ids: set[str] = load_downloaded_video_ids(archive_path)
        now_ts = datetime.now(tz=timezone.utc).timestamp()
        audio_pl_comments = utils.load_playlist_comments_for_source("audio_playlists")

        for url in urls:
            try:
                if archive_path and existing_ids:
                    cached = self._cache_get_fresh_entry(url)
                    if cached is not None:
                        cached_vid = cached.get("video_id")
                        if cached_vid and cached_vid in existing_ids:
                            pl_id = extract_playlist_id(url)
                            if pl_id and pl_id in audio_pl_comments:
                                playlist_label = utils.sanitize_for_path(
                                    audio_pl_comments[pl_id]
                                )
                            else:
                                playlist_label = url
                            status_entry = _make_podcast_status_entry(
                                playlist_label,
                                url,
                                status="Downloaded",
                                latest_url=cached.get("latest_url"),
                                latest_ts=cached.get("latest_ts"),
                            )
                            statuses.append(status_entry)
                            continue

                entries, skipped, info = fetch_latest_accessible_entry(url)
                if skipped:
                    messages.append(
                        f"Latest episode for podcast {url} is private - using previous accessible video",
                    )
                pl_id = extract_playlist_id(url)
                if pl_id and pl_id in audio_pl_comments:
                    playlist_label = utils.sanitize_for_path(audio_pl_comments[pl_id])
                else:
                    playlist_label = utils.resolve_playlist_label(info, url)
                status_entry = _make_podcast_status_entry(playlist_label, url)

                vid: str | None = None
                for entry in entries:
                    vid = entry.get("id") or entry.get("url")
                    webpage = entry.get("webpage_url") or entry.get("url")
                    if not vid or not webpage:
                        continue
                    status_entry["latest_url"] = webpage
                    status_entry["latest_ts"] = parse_video_timestamp(entry)

                    if self._episode_already_archived(vid, existing_ids, status_entry):
                        break
                    if self._skip_if_update_episode(
                        entry,
                        vid,
                        webpage,
                        archive_path,
                        existing_ids,
                        messages,
                        status_entry,
                    ):
                        break
                    if self._skip_if_short_duration(
                        entry,
                        vid,
                        webpage,
                        archive_path,
                        existing_ids,
                        messages,
                        status_entry,
                    ):
                        break

                    ts = parse_video_timestamp(entry)
                    self._classify_episode_by_age(
                        vid,
                        webpage,
                        ts,
                        now_ts,
                        playlist_label,
                        to_download,
                        pending,
                        status_entry,
                        bypass_sponsorblock_wait=bypass_sponsorblock_wait,
                    )
                    break

                self._cache_put(
                    url,
                    status_entry.get("latest_url"),
                    status_entry.get("latest_ts"),
                    video_id=vid,
                )
                statuses.append(status_entry)
            except YDL_EXTRACTION_ERRORS as e:
                utils.log_exception(e, f"Error expanding playlist/url {url}")
                errstr = str(e)
                scheduled_ts = parse_scheduled_time_from_error(errstr)
                if scheduled_ts:
                    statuses.append(
                        _make_podcast_status_entry(
                            url,
                            url,
                            status="Upcoming",
                            latest_date="(scheduled)",
                            recheck_ts=scheduled_ts,
                        ),
                    )
                    messages.append(
                        f"Podcast {url} scheduled; will recheck at {datetime.fromtimestamp(scheduled_ts).astimezone().strftime('%Y-%m-%d %H:%M:%S')}",
                    )
                else:
                    had_error = True
                    messages.append(f"Error expanding playlist/url {url}: {e}")
                    statuses.append(
                        _make_podcast_status_entry(
                            url,
                            url,
                            status=f"Error: {e}",
                            latest_date="(error)",
                        ),
                    )

        return to_download, pending, had_error, messages, statuses

    def _set_podcast_indicator(self, state: str) -> None:
        """
        Set the podcast indicator button visual state.

        state: one of 'checking', 'busy', 'pending', 'all_good', 'error'
        """
        states = {
            "checking": ("⏳", "Checking podcasts..."),
            "busy": ("🔄", "Downloads queued/active for podcasts"),
            "pending": ("⏳", "Pending SponsorBlock info for some episodes"),
            "all_good": ("✅", "All podcasts up to date"),
            "error": ("⚠️", "Error while checking podcasts"),
        }
        symbol, tip = states.get(state, ("❔", "Unknown podcast status"))
        self.podcastIndicator.setText(symbol)
        self.podcastIndicator.setToolTip(tip)

    def _create_podcast_status_table(self, statuses: list[dict]) -> QTableWidget:
        """Create and populate a podcast status table widget."""
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Podcast", "Latest Episode", "Status"])
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )
        table.setRowCount(len(statuses))
        for i, s in enumerate(statuses):
            table.setItem(i, 0, QTableWidgetItem(s.get("podcast") or "(unknown)"))
            table.setItem(
                i,
                1,
                QTableWidgetItem(s.get("latest_date") or "(unknown)"),
            )
            table.setItem(i, 2, QTableWidgetItem(s.get("status") or "(unknown)"))
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(
            self._on_podcast_status_context_menu,
        )
        return table

    def _show_podcast_status(self) -> None:
        """
        Open a non-blocking dialog showing the last known podcast statuses.

        This uses cached data from the last background check and will NOT trigger a re-check.
        If a dialog is already open, bring it to the front instead of creating a new one.
        """
        # Reuse existing dialog if open
        existing = getattr(self, "_podcast_status_dialog", None)
        if existing and getattr(existing, "isVisible", lambda: False)():
            try:
                existing.raise_()
                existing.activateWindow()
            except (RuntimeError, AttributeError) as exc:
                utils.log_exception(
                    exc,
                    "Failed to focus existing podcast status dialog",
                )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("Podcast Status")
        layout = QVBoxLayout()

        if not self._podcast_last_statuses:
            lbl = QLabel(
                "No cached podcast status available.\nPress 'YT Podcasts' to refresh.",
            )
            layout.addWidget(lbl)
            self._podcast_status_table = None
        else:
            table = self._create_podcast_status_table(self._podcast_last_statuses)
            layout.addWidget(table)
            self._podcast_status_table = table

        dialog.setLayout(layout)
        dialog.setModal(False)  # non-blocking
        dialog.show()
        # Keep a reference so it doesn't get GC'd immediately and allow refreshes
        self._podcast_status_dialog = dialog
        # Ensure we clear our reference when the dialog is destroyed
        dialog.destroyed.connect(self._on_podcast_status_dialog_destroyed)

    def _on_podcast_status_dialog_destroyed(self) -> None:
        """Clear stored references when the status dialog is destroyed."""
        self._podcast_status_dialog = None
        self._podcast_status_table = None

    def _show_history(self) -> None:
        """Open a non-blocking dialog showing download history (Ctrl+H)."""
        existing = getattr(self, "_history_dialog", None)
        if existing and getattr(existing, "isVisible", lambda: False)():
            try:
                existing.raise_()
                existing.activateWindow()
            except (RuntimeError, AttributeError) as exc:
                utils.log_exception(exc, "Failed to focus existing history dialog")
            return

        dialog = HistoryDialog(self)
        dialog.destroyed.connect(self._on_history_dialog_destroyed)
        dialog.show()
        self._history_dialog = dialog

    def _on_history_dialog_destroyed(self) -> None:
        self._history_dialog = None

    def _on_history_entry_added(self, record: dict) -> None:
        dialog = getattr(self, "_history_dialog", None)
        if dialog and dialog.isVisible():
            dialog.prepend_row(record)

    # Cache TTL: 6 hours
    CACHE_TTL_SECONDS = 6 * 60 * 60

    def _cache_put(
        self,
        playlist_url: str,
        latest_url: str | None,
        latest_ts: int | None,
        *,
        video_id: str | None = None,
    ) -> None:
        """Store or update a cache entry for a podcast's latest URL."""
        if not playlist_url or not latest_url:
            return
        self._podcast_latest_url_cache[playlist_url] = {
            "latest_url": latest_url,
            "latest_ts": latest_ts,
            "fetched_at": time.time(),
            "video_id": video_id,
        }

    def _cache_get_fresh(self, playlist_url: str) -> str | None:
        """Retrieve cached latest URL if present and not stale (within TTL)."""
        entry = self._podcast_latest_url_cache.get(playlist_url)
        if not entry:
            return None
        # Check time-based TTL
        if (time.time() - entry.get("fetched_at", 0)) > self.CACHE_TTL_SECONDS:
            return None
        return entry.get("latest_url")

    def _cache_get_fresh_entry(self, playlist_url: str) -> dict | None:
        """Return the raw cache dict for playlist_url if present and within TTL."""
        entry = self._podcast_latest_url_cache.get(playlist_url)
        if not entry:
            return None
        if (time.time() - entry.get("fetched_at", 0)) > self.CACHE_TTL_SECONDS:
            return None
        return entry

    def _on_podcast_status_context_menu(self, pos: QPoint) -> None:
        """Handle right-click context menu on Podcast Status table."""
        table = getattr(self, "_podcast_status_table", None)
        if not table:
            return
        index = table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        menu = QMenu(table)
        action_open = menu.addAction("Open Latest Video in Browser")

        def _do_open() -> None:
            statuses = getattr(self, "_podcast_last_statuses", [])
            if 0 <= row < len(statuses):
                st = statuses[row]
                playlist_url = st.get("url")
                label = st.get("podcast")
                # Prefer status-provided latest_url (from cache populated by status generation)
                latest_url = st.get("latest_url")
                if not latest_url and playlist_url:
                    latest_url = self._cache_get_fresh(playlist_url)
                if latest_url:
                    self._open_url_in_browser(latest_url, label)
                else:
                    # Fallback: resolve on-demand and cache
                    resolved = self._resolve_latest_via_ytdlp(playlist_url)
                    if resolved:
                        self._cache_put(
                            playlist_url,
                            resolved["url"],
                            resolved.get("ts"),
                        )
                        self._open_url_in_browser(resolved["url"], label)
                    else:
                        self.logEdit.appendPlainText(
                            f"Could not resolve latest episode for {label or playlist_url}",
                        )

        action_open.triggered.connect(_do_open)

        # new Download Now option for bypassing SponsorBlock wait
        def _do_download_now() -> None:
            self._download_podcast_now_action(row)

        action_download = menu.addAction("Download Now")
        action_download.triggered.connect(_do_download_now)

        menu.exec(table.viewport().mapToGlobal(pos))

    def _resolve_latest_via_ytdlp(self, playlist_url: str) -> dict | None:
        """
        Use yt-dlp to resolve the latest episode URL from a playlist.

        Returns dict with {"url": webpage_url, "ts": timestamp} or None on error.
        """
        try:
            info = utils.extract_playlist_info(playlist_url, playlistend=1)
            entries = info.get("entries", [info])
            if not entries:
                return None
            latest = entries[0]
            webpage = latest.get("webpage_url") or latest.get("url")
            ts = latest.get("timestamp")
            if webpage:
                return {"url": webpage, "ts": ts}
            return None
        except YDL_COMMON_ERRORS as exc:
            utils.log_exception(
                exc,
                f"Failed to resolve latest episode via yt-dlp for {playlist_url}",
            )
            return None

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

    def _get_brave_controller(self) -> webbrowser.BaseBrowser | None:
        """Return a Brave browser controller, registering it from disk if needed."""
        try:
            return webbrowser.get("brave")
        except (webbrowser.Error, OSError) as exc:
            utils.log_exception(
                exc,
                "Failed to get Brave controller via webbrowser.get",
            )
        for p in self._BRAVE_PATHS:
            if Path(p).exists():
                webbrowser.register(
                    "windows-brave",
                    None,
                    webbrowser.BackgroundBrowser(p),
                )
                with contextlib.suppress(webbrowser.Error, OSError):
                    return webbrowser.get("windows-brave")
        return None

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

    def _refresh_podcast_status_dialog(self) -> None:
        """Refresh the contents of the Podcast Status dialog if it's currently visible."""
        dialog = getattr(self, "_podcast_status_dialog", None)
        if not dialog or not getattr(dialog, "isVisible", lambda: False)():
            return
        layout = dialog.layout()
        # Remove existing widgets
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)
        if not self._podcast_last_statuses:
            layout.addWidget(
                QLabel(
                    "No cached podcast status available.\nPress 'YT Podcasts' to refresh.",
                ),
            )
            self._podcast_status_table = None
            return
        table = self._create_podcast_status_table(self._podcast_last_statuses)
        layout.addWidget(table)
        self._podcast_status_table = table

    def _download_podcast_now_action(self, row: int) -> None:
        """
        Initiate an immediate download of all pending episodes for the podcast at `row`.

        This bypasses the usual 24-hour / SponsorBlock wait period by invoking
        ``_filter_audio_playlist_urls`` with ``bypass_sponsorblock_wait=True`` and
        then reusing the normal ``_on_podcast_check_finished`` handler to queue the
        returned URLs.
        """
        statuses = getattr(self, "_podcast_last_statuses", [])
        if not (0 <= row < len(statuses)):
            return
        st = statuses[row]
        playlist_url = st.get("url")
        if not playlist_url:
            return

        # register that this podcast is actively downloading
        self._podcasts_downloading.add(playlist_url)

        # build ydl options similarly to the normal request path
        _, _, ydl_opts = self._create_download_context()
        properties = self.get_options([playlist_url], "audio_playlists")
        if properties:
            ydl_opts = self.append_properties(ydl_opts, properties)
            # attach metadata used by history/logging code
            ydl_opts["qmeta"] = {
                "site": utils.detect_site_from_urls([playlist_url]),
                "type": "audio_playlists",
            }

        # perform filtering immediately on the main thread
        to_download, pending, had_error, messages, statuses2 = (
            self._filter_audio_playlist_urls(
                [playlist_url],
                ydl_opts,
                bypass_sponsorblock_wait=True,
            )
        )

        # merge the single returned status into the existing list so we don't wipe
        # out the other rows in the status table
        current = list(getattr(self, "_podcast_last_statuses", []))
        updated = []
        found = False
        for s in current:
            if s.get("url") == playlist_url:
                found = True
                # take the new entry if available
                new = next((x for x in statuses2 if x.get("url") == playlist_url), None)
                if new:
                    new = dict(new)
                    # mark downloading regardless of what the filter says
                    new["status"] = "Downloading"
                    updated.append(new)
                else:
                    updated.append(s)
            else:
                updated.append(s)
        if not found:
            # podcast wasn't previously in table, just append new entries
            for item in statuses2:
                new_item = dict(item)
                new_item["status"] = "Downloading"
                updated.append(new_item)
        # pass merged list to handler so UI keeps all rows
        self._on_podcast_check_finished(
            to_download,
            pending,
            had_error,
            ydl_opts,
            messages,
            updated,
        )

    def _schedule_podcast_rechecks(self, statuses: list[dict]) -> None:
        """Store podcast statuses and schedule QTimer rechecks for upcoming episodes."""
        self._podcast_last_statuses = statuses
        if not hasattr(self, "_podcast_recheck_times"):
            self._podcast_recheck_times = {}
        if not hasattr(self, "_podcast_recheck_timers"):
            self._podcast_recheck_timers = {}
        for s in statuses:
            try:
                url = s.get("url")
                lu = s.get("latest_url")
                lts = s.get("latest_ts")
                if url and lu:
                    self._cache_put(url, lu, lts)
                rts = s.get("recheck_ts")
                if rts and url:
                    self._podcast_recheck_times[url] = rts
                    now_ts = datetime.now(tz=timezone.utc).timestamp()
                    if rts > now_ts and url not in self._podcast_recheck_timers:
                        delay_ms = int((rts - now_ts) * 1000)
                        t = QTimer(self)
                        t.setSingleShot(True)
                        t.timeout.connect(
                            lambda u=url: self.request_detected([u], "audio_playlists"),
                        )
                        try:
                            t.start(delay_ms)
                            self._podcast_recheck_timers[url] = t
                        except (RuntimeError, ValueError, TypeError) as exc:
                            self.logEdit.appendPlainText(
                                f"Failed to schedule recheck timer for {url}",
                            )
                            utils.log_exception(
                                exc,
                                f"Failed to schedule recheck timer for {url}",
                            )
                else:
                    self._podcast_recheck_times.pop(url, None)
                    t = self._podcast_recheck_timers.pop(url, None)
                    if t:
                        with contextlib.suppress(Exception):
                            t.stop()
            except (AttributeError, TypeError, KeyError, RuntimeError) as exc:  # noqa: PERF203
                utils.log_exception(
                    exc,
                    "Unexpected error while processing podcast statuses",
                )

    def _queue_podcast_downloads_grouped(
        self,
        to_download: list[dict],
        ydl_opts: dict,
    ) -> None:
        """Queue podcast downloads grouped by playlist label, one batch per label."""
        base_dir = str(
            Path(
                get_setting("VID_DL_PODCAST_MISC_OUTPUT_DIR")
                or str(PODCAST_MISC_OUTPUT_DIR)
            ).parent
        )
        groups: dict[str, list[str]] = {}
        for obj in to_download:
            try:
                label = obj.get("playlist") or "misc"
            except (AttributeError, TypeError) as exc:
                label = "misc"
                utils.log_exception(
                    exc,
                    "Failed to read playlist label from podcast object",
                )
            safe_label = utils.slugify_if_too_long(base_dir, label)
            url = obj.get("url") if isinstance(obj, dict) else obj
            if url:
                groups.setdefault(safe_label, []).append(url)
        if not groups:
            return
        for label, urls in groups.items():
            qhook, qlogger, batch_opts = self._fork_download_context(
                ydl_opts if isinstance(ydl_opts, dict) else {},
            )
            batch_opts["outtmpl"] = f"{base_dir}/{label}/%(title)s.%(ext)s"
            self.downloadQueue.put((urls, batch_opts))
            self._wire_download_signals(qhook, qlogger)
            if not hasattr(self, "_active_qhooks"):
                self._active_qhooks = []
            self._active_qhooks.append((qhook, qlogger))
        self.barProgress.setRange(0, 1)

    def _queue_podcast_downloads_flat(
        self,
        to_download: list[str],
        ydl_opts: dict,
    ) -> None:
        """Queue all podcast download URLs as a single batch."""
        qhook, qlogger, download_opts = self._fork_download_context(
            ydl_opts if isinstance(ydl_opts, dict) else {},
        )
        self.downloadQueue.put((to_download, download_opts))
        self._wire_download_signals(qhook, qlogger)
        if not hasattr(self, "_active_qhooks"):
            self._active_qhooks = []
        self._active_qhooks.append((qhook, qlogger))
        self.barProgress.setRange(0, 1)

    def _update_podcast_indicator(
        self,
        had_error: bool,
        to_download: list,
        pending_urls: set[str],
    ) -> None:
        """Set the podcast status indicator based on current results."""
        if had_error:
            self._set_podcast_indicator("error")
        elif to_download:
            self._set_podcast_indicator("busy")
        elif pending_urls:
            self._set_podcast_indicator("pending")
        else:
            self._set_podcast_indicator("all_good")

    def _on_podcast_check_finished(
        self,
        to_download: list,
        pending: list,
        had_error: bool,
        ydl_opts: dict,
        messages: list | None,
        statuses: list | None = None,
    ) -> None:
        """Handle results of a background podcast check (runs in main thread)."""
        for m in messages or []:
            self.logEdit.appendPlainText(m)

        if statuses:
            self._schedule_podcast_rechecks(statuses)

        self._last_podcast_check_error = had_error
        self._podcast_pending_urls.clear()
        for v in pending:
            url = v.get("url") if isinstance(v, dict) else v
            if url:
                self._podcast_pending_urls.add(url)

        if to_download:
            if isinstance(to_download[0], dict):
                self._queue_podcast_downloads_grouped(to_download, ydl_opts)
            else:
                self._queue_podcast_downloads_flat(to_download, ydl_opts)

        self._update_podcast_indicator(
            had_error,
            to_download,
            self._podcast_pending_urls,
        )
        self._podcast_check_running = False

        if not had_error and not to_download and not self._podcast_pending_urls:
            self.logEdit.appendPlainText(
                "No eligible podcast episodes found for immediate download. Pending items will be rechecked at the next scheduled YT Podcasts check.",
            )
        self.logEdit.appendPlainText(
            f"Podcast check complete: {len(to_download)} queued, {len(self._podcast_pending_urls)} pending, error={had_error}",
        )
        try:
            self._refresh_podcast_status_dialog()
        except (RuntimeError, AttributeError) as e:
            self.logEdit.appendPlainText(f"Error refreshing Podcast Status dialog: {e}")
            utils.log_exception(e, "Error refreshing Podcast Status dialog")

    def _shutdown_podcast_thread(self) -> None:
        """Attempt a clean shutdown of any running podcast worker thread."""
        thread = getattr(self, "_podcast_worker_thread", None)
        worker = getattr(self, "_podcast_worker", None)
        if not thread:
            return
        try:
            if worker and hasattr(worker, "request_stop"):
                worker.request_stop()
            if thread.isRunning():
                self.logEdit.appendPlainText("Shutting down podcast worker thread...")
                thread.quit()
                # Wait a short while for clean exit
                if not thread.wait(THREAD_QUIT_TIMEOUT_MS):
                    self.logEdit.appendPlainText(
                        "Podcast worker did not exit; terminating thread.",
                    )
                    try:
                        thread.terminate()
                    except (RuntimeError, OSError) as e:
                        self.logEdit.appendPlainText(
                            f"Error terminating podcast thread: {e}",
                        )
                        utils.log_exception(e, "Error terminating podcast thread")
                    thread.wait(THREAD_TERMINATE_TIMEOUT_MS)
        except (RuntimeError, OSError) as e:
            self.logEdit.appendPlainText(f"Error shutting down podcast thread: {e}")
            utils.log_exception(e, "Error shutting down podcast thread")
        finally:
            self._podcast_worker = None
            self._podcast_worker_thread = None

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Ensure background podcast checks are stopped when the window closes."""
        try:
            self._shutdown_podcast_thread()
        finally:
            super().closeEvent(event)

    def _on_session_commit(self, manager: QSessionManager) -> None:
        logger.error(
            "SHUTDOWN: App closed by OS session event (hibernate/shutdown/logoff)"
        )

    # --- Hourly automated YT Podcasts checks ---
    def _schedule_hourly_podcast_checks(self) -> None:
        """Schedule the initial single-shot to fire at the next :15 past the hour, then start recurring hourly checks."""
        now = datetime.now(tz=timezone.utc)
        # Target minute is 15 past the hour
        target = now.replace(minute=15, second=0, microsecond=0)
        if now >= target:
            target = target + timedelta(hours=1)
        delay_ms = int((target - now).total_seconds() * 1000)
        QTimer.singleShot(delay_ms, self._start_hourly_podcast_timer)
        self.logEdit.appendPlainText(
            f"Scheduled hourly YT Podcasts checks beginning {target.astimezone().strftime('%Y-%m-%d %H:%M:%S')}",
        )

    def _start_hourly_podcast_timer(self) -> None:
        # Run once immediately at the scheduled time, then start recurring hourly timer.
        # Guard: _restart_podcast_timer may have already created an active timer via Settings.
        self._hourly_podcast_check()
        if (
            not hasattr(self, "_podcast_hour_timer")
            or not self._podcast_hour_timer.isActive()
        ):
            self._podcast_hour_timer = QTimer(self)
            self._podcast_hour_timer.setInterval(60 * 60 * 1000)  # 1 hour
            self._podcast_hour_timer.timeout.connect(self._hourly_podcast_check)
            self._podcast_hour_timer.start()

    def _hourly_podcast_check(self) -> None:
        """Perform a scheduled YT Podcasts check. Skips if 'Ignore Archive?' is enabled to avoid prompting."""
        if self.checkIgnoreArchive.isChecked():
            self.logEdit.appendPlainText(
                "Skipping scheduled YT Podcasts check because 'Ignore Archive?' is enabled.",
            )
            return
        self.logEdit.appendPlainText("Running scheduled YT Podcasts check (hourly).")
        # Use the same code path as the button, but avoid showing GUI prompts
        self.request_detected([], "audio_playlists")

    def _open_settings(self) -> None:
        """Open (or raise) the Settings dialog."""
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self)
            self._settings_dialog.settings_changed.connect(self.reload_settings)
            self._settings_dialog.finished.connect(
                lambda: setattr(self, "_settings_dialog", None)
            )
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def reload_settings(self, changes: dict) -> None:
        """Apply live setting changes emitted by the Settings dialog."""
        self._apply_label_changes(changes)
        self._apply_path_changes(changes)
        podcast_keys = {
            "VID_DL_PODCAST_AUTO_CHECK",
            "VID_DL_PODCAST_CHECK_INTERVAL_MINUTES",
        }
        if podcast_keys & changes.keys():
            self._restart_podcast_timer()
        if "VID_DL_ALWAYS_ON_TOP" in changes:
            self._apply_always_on_top(changes["VID_DL_ALWAYS_ON_TOP"])

    def _apply_always_on_top(self, enabled: bool) -> None:
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()  # setWindowFlags hides the window; must re-show

    def _apply_label_changes(self, changes: dict) -> None:
        """Update widget text from settings changes."""
        if "VID_DL_LABEL_DROP_1080" in changes:
            self.label1080.setText(changes["VID_DL_LABEL_DROP_1080"])
            self.label1080.originalText = changes["VID_DL_LABEL_DROP_1080"]
        if "VID_DL_LABEL_DROP_720" in changes:
            self.label720.setText(changes["VID_DL_LABEL_DROP_720"])
            self.label720.originalText = changes["VID_DL_LABEL_DROP_720"]
        if "VID_DL_LABEL_DROP_AUDIO" in changes:
            self.labelAudio.setText(changes["VID_DL_LABEL_DROP_AUDIO"])
            self.labelAudio.originalText = changes["VID_DL_LABEL_DROP_AUDIO"]
        if "VID_DL_LABEL_READY_TEXT" in changes:
            self._ready_text = changes["VID_DL_LABEL_READY_TEXT"]
            if self.labelOutput.text() != "Checking podcasts for SponsorBlock info...":
                self.labelOutput.setText(self._ready_text)
        if "VID_DL_LABEL_BTN_PLAYLISTS" in changes:
            self.buttonPlaylists.setText(changes["VID_DL_LABEL_BTN_PLAYLISTS"])
        if "VID_DL_LABEL_BTN_720" in changes:
            self.button720Playlists.setText(changes["VID_DL_LABEL_BTN_720"])
        if "VID_DL_LABEL_BTN_PODCASTS" in changes:
            self.buttonAudioPlaylists.setText(changes["VID_DL_LABEL_BTN_PODCASTS"])

    def _apply_path_changes(self, changes: dict) -> None:
        """Update playlist paths from settings changes."""
        if "VID_DL_PLAYLISTS_FILE" in changes:
            self.buttonPlaylists.playlist_path = Path(changes["VID_DL_PLAYLISTS_FILE"])
        if "VID_DL_PLAYLISTS_720_FILE" in changes:
            self.button720Playlists.playlist_path = Path(
                changes["VID_DL_PLAYLISTS_720_FILE"]
            )
        if "VID_DL_PLAYLISTS_AUDIO_FILE" in changes:
            self.buttonAudioPlaylists.playlist_path = Path(
                changes["VID_DL_PLAYLISTS_AUDIO_FILE"]
            )

    def _restart_podcast_timer(self) -> None:
        """Stop the existing hourly podcast timer and restart it if auto-check is enabled."""
        if hasattr(self, "_podcast_hour_timer"):
            self._podcast_hour_timer.stop()
        auto = get_setting("VID_DL_PODCAST_AUTO_CHECK")
        if auto:
            interval_min = int(
                get_setting("VID_DL_PODCAST_CHECK_INTERVAL_MINUTES") or 60
            )
            self._podcast_hour_timer = QTimer(self)
            self._podcast_hour_timer.setInterval(interval_min * 60 * 1000)
            self._podcast_hour_timer.timeout.connect(self._hourly_podcast_check)
            self._podcast_hour_timer.start()
            self.logEdit.appendPlainText(
                f"Podcast auto-check restarted: every {interval_min} min."
            )
        else:
            self.logEdit.appendPlainText("Podcast auto-check disabled.")

    def _start_app_update_check(self, auto: bool = False) -> None:
        """Start a background check for a newer app version."""
        self._app_update_worker = self._AppUpdateWorker()
        self._app_update_thread = QThread(self)
        self._app_update_worker.moveToThread(self._app_update_thread)
        self._app_update_thread.started.connect(self._app_update_worker.run)
        self._app_update_worker.finished.connect(
            lambda avail, tag, url: self._on_app_update_result(avail, tag, url, auto=auto)
        )
        self._app_update_worker.finished.connect(self._app_update_thread.quit)
        self._app_update_thread.start()

    def _maybe_start_auto_app_update_check(self) -> None:
        """Fire a background app-update check at most once per week if the setting is on."""
        if not get_setting("VID_DL_APP_UPDATE_AUTO_CHECK"):
            logger.info("Auto app update check disabled by setting")
            return
        last_checked = get_setting("VID_DL_APP_UPDATE_LAST_CHECKED")
        if last_checked:
            try:
                last_dt = date.fromisoformat(str(last_checked))
                if (date.today() - last_dt).days < 7:
                    logger.info("Auto app update check skipped: last checked %s", last_checked)
                    return
            except ValueError:
                pass
        logger.info("Starting automatic app update check")
        self._start_app_update_check(auto=True)

    def _on_app_update_result(
        self,
        update_available: bool,
        latest_tag: str,
        download_url: str,
        *,
        auto: bool = False,
    ) -> None:
        """Handle the result of the background app update check."""
        if auto:
            _persist_setting(
                "VID_DL_APP_UPDATE_LAST_CHECKED", date.today().isoformat()
            )
        if not update_available:
            if not auto:
                QMessageBox.information(
                    self,
                    "No Update Available",
                    "You are running the latest version.",
                )
            else:
                logger.info("Auto app update check: already on latest version")
            return
        answer = QMessageBox.question(
            self,
            "Update Available",
            f"Version {latest_tag} is available. Download now?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            webbrowser.open(download_url)

    def do_updates(self) -> None:
        """
        Update YT_DLP at start.

        Upgrade yt-dlp to the latest version using uv, open the changelog in the default browser,
        and restart the application if the update is successful. Updates the UI to indicate failure
        if the installed version does not match the latest version after the update attempt.
        """
        uv_path = shutil.which("uv")
        if uv_path is None:
            self.buttonUpdate.setStyleSheet("color: red;")
            return

        # 1. Update the lockfile to the latest yt-dlp
        lock_process = subprocess.run(  # noqa: S603
            [uv_path, "lock", "--upgrade-package", "yt-dlp"],
            check=False,
        )
        # 2. Sync the environment to actually install the new yt-dlp, using the updated lockfile
        sync_process = subprocess.run(  # noqa: S603
            [uv_path, "sync"],
            check=False,
        )

        if lock_process.returncode == 0 and sync_process.returncode == 0:
            webbrowser.open("https://github.com/yt-dlp/yt-dlp/blob/master/Changelog.md")
            # Update successful, restart app
            python = sys.executable
            script = os.path.realpath(sys.argv[0])
            subprocess.Popen([python, script, *sys.argv[1:]])  # noqa: S603
            sys.exit()
        else:
            # Update failed or no version change
            self.buttonUpdate.setStyleSheet("color: red;")


if __name__ == "__main__":
    _storage = Path(VIDEO_STORAGE_DIR)
    if _storage.exists():
        startfile(str(_storage))  # noqa: S606
    if getattr(sys, "frozen", False):
        dirname = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        dirname = Path(__file__).parent
    QDir.addSearchPath("icons", str(dirname / "resources" / "icons"))

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon("icons:meadowlark.png"))
    app.setQuitOnLastWindowClosed(True)

    window = MyWindow()
    app.commitDataRequest.connect(window._on_session_commit)
    window.show()

    if needs_first_run():
        _wizard = FirstRunWizard(window)
        if _wizard.exec() == QDialog.DialogCode.Accepted:
            _restart_args = sys.argv[1:] if getattr(sys, "frozen", False) else sys.argv
            QProcess.startDetached(sys.executable, _restart_args)
            app.quit()

    if not shutil.which("ffmpeg"):
        QMessageBox.warning(
            None,
            "FFmpeg not found",
            "FFmpeg is not installed or not on PATH.\nAudio and podcast downloads will fail.",
        )

    deno_exe = Path(VENV_SCRIPTS_DIR) / "deno.exe"
    if not deno_exe.exists():
        if getattr(sys, "frozen", False):
            _deno_msg = f"Deno not found at {deno_exe}.\nYouTube downloads may fail."
        else:
            _deno_msg = f"Deno not found at {deno_exe}.\nRun `uv sync` to install it."
        QMessageBox.warning(None, "Deno not found", _deno_msg)

    app.exec()

# TODO: size control for error logs (low priority)
# TODO: resizing makes Audio big (low priority)
# TODO: make sure tests don't leave logs in the real error log
# TODO: better cookie.txt explanation
# TODO: settings to toggle mark as watched for YT
# TODO: auto update check with opt out settings
