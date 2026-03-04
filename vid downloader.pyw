"""
Vid Downloader - A PyQt6-based GUI application for downloading and managing video and audio content from YouTube and other platforms using yt-dlp.

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
import os
import queue
import re
import shutil
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from os import startfile
from pathlib import Path

import requests
import yt_dlp
from hurry.filesize import size
from PyQt6.QtCore import QDir, QObject, QPoint, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
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
from UIClasses import DropLabel, PlaylistButton, PlaylistDialog

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

# how many entries to look ahead before giving up
MAX_LOOKAHEAD = 5


def _fetch_latest_accessible_entry(url: str) -> tuple[list, bool, dict]:
    """
    Return a tuple suitable for :func:`_filter_audio_playlist_urls`.

    This function employs an incremental lookahead strategy (increasing
    ``playlistend``) rather than fetching the entire playlist when private
    videos are encountered.

    ``url`` is a playlist or channel URL.  First we attempt a lightweight
    extraction limited to the first entry (``playlistend=1``).  If the call
    succeeds but the entry's ``title`` starts with ``"Private video"`` or the
    extraction raises any exception whose string contains that phrase, the
    result is considered a "private latest" case.

    In that situation we perform a second extraction with ``ignoreerrors=True``
    (no ``playlistend``) and walk the returned list backwards until we find a
    non-private entry.  That entry is returned in a one-item list and ``skipped``
    is set to ``True``.  ``skipped`` is ``False`` if no private video was
    encountered.  The original ``info`` dict from yt-dlp is also returned so
    that callers can derive a playlist label.

    The original exception is re-raised if the playlist has no accessible
    entries; callers may let it bubble up so the existing error-path logic can
    apply.
    """
    original_exc: Exception | None = None
    # try progressively larger tail slices rather than full scrape
    for n in range(1, MAX_LOOKAHEAD + 1):
        try:
            with yt_dlp.YoutubeDL(
                {"quiet": True, "no_warnings": True, "playlist_items": str(n)},
            ) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:
            original_exc = exc
            if "Private video" in str(exc):
                # try again with larger playlistend
                continue
            # some other error - propagate immediately
            raise

        entries = info.get("entries", [info])
        if not entries:
            # nothing at all; give up
            break
        # examine the *last* entry returned (should be the n'th-from-end)
        cand = entries[-1]
        title = cand.get("title", "")
        if isinstance(title, str) and title.startswith("Private video"):
            # private, keep looking
            original_exc = original_exc or Exception("Private video")
            continue
        # found a non-private entry
        return [cand], True if n > 1 or original_exc is not None else False, info

    # exhausted lookahead window or playlist ended
    if original_exc:
        raise original_exc
    # nothing special happened - return what we got from first call if any
    raise Exception("Unable to resolve latest accessible entry")


# end helper


class MyWindow(QWidget):
    """
    MyWindow - A PyQt6-based main window for the Vid Downloader application, providing a GUI for downloading and managing video and audio content from YouTube and other platforms.

    Features include playlist and audio download options, drag-and-drop support, progress tracking, log display, update checking, and integration with custom download queue and processing logic.
    """

    def __init__(self) -> None:
        """
        Vid Downloader is a PyQt6-based GUI application for downloading and managing video and audio content from YouTube and other platforms using yt-dlp.

        Provides a user-friendly interface for batch downloading videos, playlists, and audio files with customizable options. Features include drag-and-drop support, playlist selection, progress tracking, real-time logging, archive checking, automatic yt-dlp updates, and secure credential storage via keyring.

        Run this script to launch the GUI, queue downloads, monitor progress, and manage updates.
        """
        super().__init__()
        self.setWindowTitle("Vid Downloader")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        layout = QGridLayout()

        self.buttonPlaylists = PlaylistButton(
            "Playlists",
            r"Z:\misc\dev\vid downloader\resources\playlists\playlists.txt",
        )
        self.buttonPlaylists.clicked.connect(
            lambda: self.playlist_button_clicked("1080playlists"),
        )
        self.button720Playlists = PlaylistButton(
            "720 Playlists",
            r"Z:\misc\dev\vid downloader\resources\playlists\720playlists.txt",
        )
        self.button720Playlists.clicked.connect(
            lambda: self.playlist_button_clicked("720playlists"),
        )
        self.buttonAudioPlaylists = PlaylistButton(
            "YT Podcasts",
            r"Z:\misc\dev\vid downloader\resources\playlists\audio playlists.txt",
        )
        # Make the Podcasts button smaller and add an adjacent status indicator
        self.buttonAudioPlaylists.setMaximumWidth(140)
        self.buttonAudioPlaylists.clicked.connect(
            lambda: self.playlist_button_clicked("audio_playlists"),
        )

        # Podcast indicator: shows status (checking, pending, busy, ok, error)
        self.podcastIndicator = QPushButton("", self)
        self.podcastIndicator.setFixedSize(34, 34)
        self.podcastIndicator.setFlat(True)
        self.podcastIndicator.setStyleSheet(
            "font-size:18px;background:transparent;border:0px",
        )
        self.podcastIndicator.setToolTip("Podcast status")
        self.podcastIndicator.clicked.connect(self._show_podcast_status)
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
        self.checkIgnoreArchive = QCheckBox("Ignore Archive?")
        self.checkIgnoreArchive.setChecked(False)
        self.checkSkipDownload = QCheckBox("Skip Download")
        self.checkSkipDownload.setChecked(False)
        self.buttonUpdate = QPushButton("⤓")
        self.buttonUpdate.clicked.connect(lambda: self.request_detected([], "Update"))
        self.buttonUpdate.setVisible(True)
        self.label1080 = DropLabel("1080", "#424769", self.request_detected)
        self.label720 = DropLabel("720", "#7077A1", self.request_detected)
        self.labelAudio = DropLabel("audio", "#FF9843", self.request_detected)
        self.labelOutput = QLabel("[ Ready ]")
        self.labelOutput.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.labelOutput.setFont(QFont("Arial", 16))
        self.barProgress = QProgressBar()
        self.logEdit = QPlainTextEdit(readOnly=True)

        layout.addWidget(self.checkSkipDownload, 0, 0)
        layout.addWidget(self.checkIgnoreArchive, 0, 1)
        layout.addWidget(self.buttonUpdate, 0, 2)
        layout.addWidget(self.buttonPlaylists, 1, 0)
        layout.addWidget(self.button720Playlists, 1, 1)
        # Use a small container to hold the Podcasts button and the indicator
        podcast_container = QWidget()
        podcast_layout = QGridLayout()
        podcast_layout.setContentsMargins(0, 0, 0, 0)
        podcast_layout.addWidget(self.buttonAudioPlaylists, 0, 0)
        podcast_layout.addWidget(self.podcastIndicator, 0, 1)
        podcast_container.setLayout(podcast_layout)
        layout.addWidget(podcast_container, 1, 2)
        layout.setColumnStretch(2, 1)
        layout.addWidget(self.label1080, 2, 0)
        layout.addWidget(self.label720, 2, 1)
        layout.addWidget(self.labelAudio, 2, 2)
        layout.addWidget(self.labelOutput, 3, 0, 1, 3)
        layout.addWidget(self.barProgress, 4, 0, 1, 3)
        layout.addWidget(self.logEdit, 5, 0, 1, 3)

        self.downloadQueue = queue.Queue()
        self.downloader = QYT.QYTQueue(self.downloadQueue)
        self.downloader.message_changed.connect(self.handle_log_entry)
        self.downloader.queue_empty.connect(self.handle_queue_empty)
        self.downloader.start()
        self.setLayout(layout)

        # Live queue setup and periodic recheck every 30 minutes
        self.live_queue_path = Path("resources/live_queue.txt")
        self.live_queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.live_queue_path.touch(exist_ok=True)
        self.live_check_timer = QTimer(self)
        self.live_check_timer.setInterval(30 * 60 * 1000)  # 30 minutes
        self.live_check_timer.timeout.connect(self.check_live_queue)
        self.live_check_timer.start()
        # Do an initial check on startup
        self.check_live_queue()

        # SponsorBlock per-video retry scheduling removed — hourly YT Podcasts checks will re-evaluate pending episodes.
        # Schedule hourly automated YT Podcasts check (runs at :15 past the hour)
        self._schedule_hourly_podcast_checks()

        # Ensure podcast worker threads are shut down on application exit
        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._shutdown_podcast_thread)

        update_available, _, _ = utils.is_yt_dlp_update_available()
        self.buttonUpdate.setVisible(update_available)

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
        qhook = QYT.QHook()
        qlogger = QYT.QLogger(self.downloadQueue)
        if source == "Update":
            self.do_updates()
            return
        playlists_path = utils.get_playlist_file_for_source(source)
        if playlists_path:
            try:
                with Path(playlists_path).open("r", encoding="utf-8") as file:
                    # Skip blank lines and comments safely
                    urls = [
                        line.strip()
                        for line in file
                        if line.strip() and not line.strip().startswith("#")
                    ]
            except FileNotFoundError:
                print("File not found.")

        # options constant for all downloads
        ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)

        properties = self.get_options(urls, source)
        if properties:
            ydl_opts = self.append_properties(ydl_opts, properties)
            if ydl_opts:
                # Provide metadata for history logging
                ydl_opts["qmeta"] = {
                    "site": utils.detect_site_from_urls(urls),
                    "type": source,
                }

                # Special handling for YT Podcasts: filter new episodes <24h without SponsorBlock
                if source == "audio_playlists":
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
                            lambda: self.labelOutput.setText("[ Ready ]"),
                        )

                        # Store references to avoid GC while running
                        self._podcast_worker = worker
                        self._podcast_worker_thread = thread

                        def _on_finished(
                            to_download,
                            pending,
                            had_error,
                            messages,
                            statuses,
                        ):
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
                        except Exception as e:
                            self.logEdit.appendPlainText(
                                f"Failed to start podcast check thread: {e}",
                            )
                            self._podcast_check_running = False
                            self._set_podcast_indicator("error")
                else:
                    self.downloadQueue.put((urls, ydl_opts))
                    qhook.info_changed.connect(self.handle_info_changed)
                    # qlogger.message_changed.connect(self.logEdit.appendPlainText)
                    qlogger.message_changed.connect(self.handle_log_entry)
                    self.barProgress.setRange(0, 1)

    def skip_downloading(self, urls: list, source: str) -> None:
        self.labelOutput.setText("Skipping downloads.")
        qlogger = QYT.QLogger(self.downloadQueue)
        total_added = 0
        archive_path = Path("C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt")
        # Read existing IDs into a set
        if archive_path.exists():
            with archive_path.open("r", encoding="utf-8") as archive:
                existing_ids = {
                    line.strip().split()[-1] for line in archive if line.strip()
                }
        else:
            existing_ids = set()
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

    # parse input data and modify options accordingly
    def get_options(self, urls: list, source: str) -> dict | None:
        """
        Handle a detected download request by preparing options, updating URLs if needed, and queuing the download task.

        Args:
            urls (list): List of URLs to process.
            source (str): The source type or action (e.g., playlist type or 'Update').

        If the source is 'Update', triggers the update process. Otherwise, prepares yt-dlp options, merges additional properties, and enqueues the download with progress and log handlers.
        """
        properties = {}
        if self.checkSkipDownload.isChecked():
            self.skip_downloading(urls, source)
            return None

        # If a playlist file contained no URLs, bail out early to avoid errors
        if not urls:
            self.logEdit.appendPlainText(f"No URLs found for source: {source}")
            return None

        # ignore archive checkbox
        if not self.checkIgnoreArchive.isChecked():
            properties["download_archive"] = (
                "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt"
            )

        # detect if YT
        if "youtube.com" in urls[0]:
            # Use a custom match_filter that records live videos for later
            properties["match_filter"] = self.make_match_filter(source)
            # properties["postprocessors"] = [
            #     {"key": "SponsorBlock"},
            #     {
            #         "key": "ModifyChapters",
            #         "remove_sponsor_segments": ["sponsor", "selfpromo"],
            #     },
            # ]

        # strip out unnecessary parts of URL if dropping from Watch Later
        urls = [url.split("&list=WL")[0] for url in urls]

        # individual playlist dragged somewhere
        if "list=" in urls[0] and "playlist" not in source:
            with yt_dlp.YoutubeDL({"extract_flat": "in_playlist"}) as ydl:
                info = ydl.extract_info(urls[0], download=False)
                playlist_count = info["playlist_count"]
                dialog = PlaylistDialog(playlist_count)
                if dialog.exec():
                    playlist_input = dialog.get_playlist_input()
                    # a blank return will set no option so default to downloading whole playlist
                    if playlist_input:
                        properties["playlist_items"] = playlist_input
                    if source != "audio":
                        source += "playlists"
                else:  # will cancel playlist download
                    return None

        # source
        source_options = {
            "audio": {
                "format": "m4a/bestaudio/best",
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
                ],
                "outtmpl": "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/misc/%(title)s.%(ext)s",
            },
            "audio_playlists": {
                "format": "m4a/bestaudio/best",
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
                ],
                "outtmpl": "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/misc/%(title)s.%(ext)s",
                "ignoreerrors": "only_download",
            },
            "720playlists": {
                # Prefer 720p mp4 video + m4a audio, else best 720p with any audio, else fallback best
                "format": (
                    "bestvideo*[height=720][ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo*[height=720]+bestaudio/"
                    "best[height=720]/best"
                ),
                "merge_output_format": "mp4",
                "outtmpl": "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s",
                "ignoreerrors": "only_download",
            },
            "1080playlists": {
                # Prefer 1080p mp4 video + m4a audio, else best 1080p with any audio, else fallback best
                "format": (
                    "bestvideo*[height=1080][ext=mp4]+bestaudio[ext=m4a]/"
                    "bestvideo*[height=1080]+bestaudio/"
                    "best[height=1080]/best"
                ),
                "merge_output_format": "mp4",
                "outtmpl": "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s",
                "ignoreerrors": "only_download",
            },
        }

        if source in source_options:
            if "playlists" in source:
                # Use a custom match_filter that records live videos for later
                properties["match_filter"] = self.make_match_filter(source)
            properties.update(source_options[source])
        else:
            # Build a format string that targets the requested height if source is numeric like "1080" or "720"
            try:
                height = int(source)
            except ValueError:
                height = None
            if height:
                fmt = (
                    f"bestvideo*[height={height}][ext=mp4]+bestaudio[ext=m4a]/"
                    f"bestvideo*[height={height}]+bestaudio/"
                    f"best[height={height}]/best"
                )
            else:
                fmt = "bestvideo*+bestaudio/best"
            properties.update(
                {
                    "format": fmt,
                    "merge_output_format": "mp4",
                    "outtmpl": "E:/vid storage/%(title)s.%(ext)s",
                },
            )

        # Ensure we always apply our custom match filter if not already set
        if "match_filter" not in properties:
            properties["match_filter"] = self.make_match_filter(source)

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
        max_int = 2147483647
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
        self.labelOutput.setText("[ Ready ]")
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

    class _PodcastCheckWorker(QObject):
        """Worker that runs podcast playlist expansion and SponsorBlock checks off the GUI thread."""

        # finished: to_download, pending, had_error, messages, statuses
        finished = pyqtSignal(list, list, bool, list, list)

        def __init__(self, func, urls: list, ydl_opts: dict) -> None:
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
            # Emit results back to the main thread; the main thread will perform any GUI logging.
            with contextlib.suppress(RuntimeError):
                self.finished.emit(to_download, pending, had_error, errors, statuses)
            # If the main thread or receiver has gone away, swallow to avoid crashing

    # --- Live queue management ---
    def make_match_filter(self, source: str):
        """
        Build a custom match_filter that...

        - Skips live and upcoming videos now
        - Records them into a persistent live queue for later re-check
        - Skips videos that need auth
        """

        def _mf(info: dict, incomplete: bool) -> str | None:
            try:
                is_live = info.get("is_live")
                live_status = info.get("live_status")
                availability = info.get("availability")
                if availability in ("needs_auth", "scheduled"):
                    return f"Skipping: {availability}"
                if is_live or live_status in ("is_live", "is_upcoming"):
                    url = (
                        info.get("webpage_url")
                        or info.get("original_url")
                        or info.get("url")
                    )
                    if url:
                        self.add_to_live_queue(url, source)
                        self.logEdit.appendPlainText(
                            f"Queued live for later: {url} [{source}]",
                        )
                    return "Skipping live; queued for later"
            except Exception:
                # If anything goes wrong, allow download to proceed rather than crash
                return None
            return None

        return _mf

    def load_live_queue(self) -> dict[str, str]:
        entries: dict[str, str] = {}
        if self.live_queue_path.exists():
            with self.live_queue_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    # stored as: source|url
                    parts = line.split("|", 1)
                    if len(parts) == 2 and parts[1]:
                        entries[parts[1]] = parts[0]
        return entries

    def save_live_queue(self, entries: dict[str, str]) -> None:
        with self.live_queue_path.open("w", encoding="utf-8") as f:
            for url, source in entries.items():
                f.write(f"{source}|{url}\n")

    def add_to_live_queue(self, url: str, source: str) -> None:
        entries = self.load_live_queue()
        # Avoid duplicates
        entries[url] = source
        self.save_live_queue(entries)

    def check_live_queue(self) -> None:
        entries = self.load_live_queue()
        if not entries:
            return
        remaining: dict[str, str] = {}
        for url, source in entries.items():
            try:
                with yt_dlp.YoutubeDL(
                    {
                        "quiet": True,
                        "skip_download": True,
                        "cookiefile": r"resources\cookies.txt",
                        "extract_flat": True,
                    },
                ) as ydl:
                    info = ydl.extract_info(url, download=False)
                is_live = info.get("is_live")
                live_status = info.get("live_status")
                if is_live or live_status in ("is_live", "is_upcoming"):
                    # Still live; keep it in the queue
                    remaining[url] = source
                else:
                    # Live ended -> enqueue for download with original source options
                    self.logEdit.appendPlainText(
                        f"Live ended, queued: {url} [{source}]",
                    )
                    qhook = QYT.QHook()
                    qlogger = QYT.QLogger(self.downloadQueue)
                    ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)
                    properties = self.get_options([url], source)
                    if properties:
                        properties["match_filter"] = self.make_match_filter(source)
                        ydl_opts = self.append_properties(ydl_opts, properties)
                        # Provide metadata for history logging on requeued lives
                        ydl_opts["qmeta"] = {
                            "site": utils.detect_site_from_urls([url]),
                            "type": source,
                        }

                        self.downloadQueue.put(([url], ydl_opts))
                        qhook.info_changed.connect(self.handle_info_changed)
                        qlogger.message_changed.connect(self.handle_log_entry)
            except Exception as e:  # noqa: BLE001
                # If any error in checking, keep it for later
                self.logEdit.appendPlainText(
                    f"Error checking live url {url}: {e}",
                )
                remaining[url] = source
        self.save_live_queue(remaining)

    # --- SponsorBlock checks for YT Podcasts ---
    def _check_sponsorblock_for_video_id(self, video_id: str) -> bool:
        """Return True if SponsorBlock has segments for `video_id` (YouTube id)."""
        try:
            # SponsorBlock API: returns [] if no segments
            url = f"https://sponsor.ajay.app/api/skipSegments?videoID={video_id}"
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                data = r.json()
                return bool(data)
        except Exception:
            # Treat as not having SponsorBlock if the API fails
            pass
        return False

    def _filter_audio_playlist_urls(
        self,
        urls: list,
        ydl_opts: dict,
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
        to_download: list[str] = []
        pending: list[str] = []
        had_error = False
        messages: list[str] = []
        statuses: list[dict] = []
        archive_path = ydl_opts.get("download_archive")
        existing_ids: set[str] = set()
        if archive_path and Path(archive_path).exists():
            try:
                with Path(archive_path).open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split()
                        existing_ids.add(parts[-1])
            except Exception:
                existing_ids = set()

        now_ts = datetime.now(tz=timezone.utc).timestamp()
        for url in urls:
            try:
                # Fetch the latest accessible entry.  This helper will return a
                # one-item list and a flag indicating whether a private video was
                # skipped; it may re-raise if the playlist contains no
                # accessible entries.
                entries, skipped, info = _fetch_latest_accessible_entry(url)
                if skipped:
                    messages.append(
                        f"Latest episode for podcast {url} is private - using previous accessible video",
                    )
                # Resolve a robust playlist label and build base status entry for this podcast
                playlist_label = utils.resolve_playlist_label(info, url)
                status_entry: dict = {
                    "podcast": playlist_label,
                    "latest_date": "(unknown)",
                    "status": "(unknown)",
                    "url": url,
                }

                for entry in entries:
                    vid = entry.get("id") or entry.get("url")
                    webpage = entry.get("webpage_url") or entry.get("url")
                    if not vid or not webpage:
                        continue
                    # Store for status_entry later
                    status_entry["latest_url"] = webpage
                    status_entry["latest_ts"] = entry.get("timestamp")
                    if status_entry["latest_ts"] is None and entry.get("upload_date"):
                        try:
                            status_entry["latest_ts"] = (
                                datetime.strptime(
                                    entry.get("upload_date"),
                                    "%Y%m%d",
                                )
                                .replace(tzinfo=timezone.utc)
                                .timestamp()
                            )
                        except Exception:
                            status_entry["latest_ts"] = None
                    if vid in existing_ids:
                        # Already archived — mark and stop evaluating further entries for this podcast
                        status_entry["status"] = "Downloaded"
                        break
                    # Determine upload timestamp
                    ts = entry.get("timestamp")
                    if not ts and entry.get("upload_date"):
                        try:
                            ts = (
                                datetime.strptime(
                                    entry.get("upload_date"),
                                    "%Y%m%d",
                                )
                                .replace(tzinfo=timezone.utc)
                                .timestamp()
                            )
                        except Exception:
                            ts = None
                    if ts:
                        # If timestamp is in the future, treat as an upcoming scheduled episode
                        if ts > now_ts:
                            status_entry["status"] = "Upcoming"
                            status_entry["recheck_ts"] = ts
                        else:
                            age_seconds = now_ts - ts
                            if bypass_sponsorblock_wait:
                                # Bypass the normal 24-hour/SponsorBlock gating entirely
                                to_download.append(
                                    {"url": webpage, "playlist": playlist_label},
                                )
                                status_entry["status"] = "Ready"
                            elif age_seconds < (24 * 60 * 60):
                                # New episode; check SponsorBlock (only YouTube)
                                site = utils.detect_site_from_urls([webpage])
                                if site == "youtube":
                                    has_sb = self._check_sponsorblock_for_video_id(vid)
                                    if has_sb:
                                        to_download.append(
                                            {
                                                "url": webpage,
                                                "playlist": playlist_label,
                                            },
                                        )
                                        status_entry["status"] = "Ready"
                                    else:
                                        pending.append(
                                            {
                                                "url": webpage,
                                                "playlist": playlist_label,
                                            },
                                        )
                                        status_entry["status"] = "Pending SponsorBlock"
                                else:
                                    # Non-YouTube: fall back to not requiring SponsorBlock
                                    to_download.append(
                                        {"url": webpage, "playlist": playlist_label},
                                    )
                                    status_entry["status"] = "Ready"
                            else:
                                # Older than 24h -> download
                                to_download.append(
                                    {"url": webpage, "playlist": playlist_label},
                                )
                                status_entry["status"] = "Ready"
                    else:
                        # No timestamp -> be permissive and download
                        to_download.append({"url": webpage, "playlist": playlist_label})
                        status_entry["status"] = "Ready"

                    # latest_date formatting
                    if ts:
                        try:
                            status_entry["latest_date"] = datetime.fromtimestamp(
                                ts,
                                tz=timezone.utc,
                            ).strftime(
                                "%Y-%m-%d %H:%M:%S",
                            )
                        except Exception:
                            status_entry["latest_date"] = "(unknown)"

                # Append a single status entry per podcast after evaluating its latest entry
                # Cache the latest URL if present
                if status_entry.get("latest_url"):
                    self._cache_put(
                        url,
                        status_entry["latest_url"],
                        status_entry.get("latest_ts"),
                    )
                statuses.append(status_entry)
            except Exception as e:
                # Try to detect scheduled/upcoming events and treat them as 'Upcoming' rather than errors
                errstr = str(e)
                now_ts = datetime.now(tz=timezone.utc).timestamp()
                scheduled_ts = None
                # Pattern like: 'This live event will begin in 29 hours.'
                m = re.search(
                    r"will begin in\s*(\d+)\s*(hour|hours|day|days)",
                    errstr,
                    re.IGNORECASE,
                )
                if m:
                    n = int(m.group(1))
                    unit = m.group(2).lower()
                    delay = n * 3600 if unit.startswith("hour") else n * 86400
                    scheduled_ts = now_ts + delay
                else:
                    # Pattern: 'scheduled to begin on 2026-02-03 15:00' or similar
                    m2 = re.search(
                        r"scheduled to begin .*?(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?)",
                        errstr,
                        re.IGNORECASE,
                    )
                    if m2:
                        datestr = m2.group(1)
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                            try:
                                scheduled_ts = (
                                    datetime.strptime(
                                        datestr,
                                        fmt,
                                    )
                                    .replace(tzinfo=timezone.utc)
                                    .timestamp()
                                )
                                break
                            except Exception:
                                scheduled_ts = None
                if scheduled_ts:
                    statuses.append(
                        {
                            "podcast": url,
                            "latest_date": "(scheduled)",
                            "status": "Upcoming",
                            "url": url,
                            "recheck_ts": scheduled_ts,
                        },
                    )
                    messages.append(
                        f"Podcast {url} scheduled; will recheck at {datetime.fromtimestamp(scheduled_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}",
                    )
                else:
                    # If extracting playlist fails, record the error and continue
                    had_error = True
                    messages.append(f"Error expanding playlist/url {url}: {e}")
                    statuses.append(
                        {
                            "podcast": url,
                            "latest_date": "(error)",
                            "status": f"Error: {e}",
                            "url": url,
                        },
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
            except Exception:
                pass
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
            table = QTableWidget()
            statuses = self._podcast_last_statuses
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
            layout.addWidget(table)
            self._podcast_status_table = table
            # Wire up context menu for right-click
            table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            table.customContextMenuRequested.connect(
                self._on_podcast_status_context_menu,
            )

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

    # Cache TTL: 6 hours
    CACHE_TTL_SECONDS = 6 * 60 * 60

    def _cache_put(
        self,
        playlist_url: str,
        latest_url: str,
        latest_ts: int | None,
    ) -> None:
        """Store or update a cache entry for a podcast's latest URL."""
        if not playlist_url or not latest_url:
            return
        self._podcast_latest_url_cache[playlist_url] = {
            "latest_url": latest_url,
            "latest_ts": latest_ts,
            "fetched_at": time.time(),
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
            with yt_dlp.YoutubeDL(
                {"quiet": True, "no_warnings": True, "playlistend": 1},
            ) as ydl:
                info = ydl.extract_info(playlist_url, download=False)
            entries = info.get("entries", [info])
            if not entries:
                return None
            latest = entries[0]
            webpage = latest.get("webpage_url") or latest.get("url")
            ts = latest.get("timestamp")
            if webpage:
                return {"url": webpage, "ts": ts}
            return None
        except Exception:
            return None

    def _open_url_in_browser(self, latest_url: str, label: str | None = None) -> None:
        """Open a URL in the default browser, with fallback to Brave."""
        # Try default browser first
        try:
            if webbrowser.open_new_tab(latest_url):
                self.logEdit.appendPlainText(
                    f"Opened latest for {label or latest_url} in default browser",
                )
                return
        except Exception:
            pass
        # Fallback to Brave
        try:
            try:
                controller = webbrowser.get("brave")
            except Exception:
                brave_paths = [
                    r"C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
                    r"C:\\Program Files (x86)\\BraveSoftware\\Brave-Browser\\Application\\brave.exe",
                ]
                controller = None
                for p in brave_paths:
                    if Path(p).exists():
                        webbrowser.register(
                            "windows-brave",
                            None,
                            webbrowser.BackgroundBrowser(p),
                        )
                        controller = webbrowser.get("windows-brave")
                        break
            if controller:
                controller.open_new_tab(latest_url)
                self.logEdit.appendPlainText(
                    f"Opened latest for {label or latest_url} in Brave",
                )
                return
        except Exception as e:
            self.logEdit.appendPlainText(f"Failed to open Brave: {e}")
        # If all fails
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
        statuses = self._podcast_last_statuses
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
        layout.addWidget(table)
        self._podcast_status_table = table
        # Wire up context menu for right-click
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self._on_podcast_status_context_menu)

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
        qhook = QYT.QHook()
        qlogger = QYT.QLogger(self.downloadQueue)
        ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)
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
            for new in statuses2:
                new = dict(new)
                new["status"] = "Downloading"
                updated.append(new)
        # pass merged list to handler so UI keeps all rows
        self._on_podcast_check_finished(
            to_download,
            pending,
            had_error,
            ydl_opts,
            messages,
            updated,
        )

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
        # Log any messages returned from the worker (avoid GUI calls in the worker)
        if messages:
            for m in messages:
                self.logEdit.appendPlainText(m)

        # Cache last known statuses for non-blocking status dialog display
        if statuses:
            self._podcast_last_statuses = statuses
            # Record any per-podcast recheck timestamps so we can skip checks until scheduled time,
            # and schedule a precise recheck for feeds with known scheduled times.
            if not hasattr(self, "_podcast_recheck_times"):
                self._podcast_recheck_times = {}
            if not hasattr(self, "_podcast_recheck_timers"):
                self._podcast_recheck_timers = {}
            for s in statuses:
                try:
                    url = s.get("url")
                    # Sync cache with latest_url and latest_ts from status
                    lu = s.get("latest_url")
                    lts = s.get("latest_ts")
                    if url and lu:
                        self._cache_put(url, lu, lts)
                    rts = s.get("recheck_ts")
                    if rts:
                        self._podcast_recheck_times[url] = rts
                        # schedule a one-shot timer to re-run check at the scheduled time if not already scheduled
                        now_ts = datetime.now(
                            tz=timezone.utc,
                        ).timestamp()
                        if rts > now_ts and url not in self._podcast_recheck_timers:
                            delay_ms = int((rts - now_ts) * 1000)
                            t = QTimer(self)
                            t.setSingleShot(True)
                            t.timeout.connect(
                                lambda u=url: self.request_detected(
                                    [u],
                                    "audio_playlists",
                                ),
                            )
                            try:
                                t.start(delay_ms)
                                self._podcast_recheck_timers[url] = t
                            except Exception:
                                # If timer scheduling fails, just log and continue
                                self.logEdit.appendPlainText(
                                    f"Failed to schedule recheck timer for {url}",
                                )
                    else:
                        # Remove any stale scheduled time and cancel any timer
                        self._podcast_recheck_times.pop(url, None)
                        t = self._podcast_recheck_timers.pop(url, None)
                        if t:
                            with contextlib.suppress(Exception):
                                t.stop()
                except Exception:
                    pass

        # Update internal state
        self._last_podcast_check_error = had_error
        self._podcast_pending_urls.clear()
        for v in pending:
            self._podcast_pending_urls.add(v.get("url") if isinstance(v, dict) else v)

        # Queue downloads if present
        if to_download:
            # Determine if we received enriched objects or plain URLs
            is_obj_list = (
                isinstance(to_download, list)
                and len(to_download) > 0
                and isinstance(to_download[0], dict)
            )
            if is_obj_list:
                # Group per playlist label and set per-group outtmpl
                base_dir = "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts"
                groups: dict[str, list[str]] = {}
                for obj in to_download:
                    try:
                        label = obj.get("playlist") or "misc"
                    except Exception:
                        label = "misc"
                    # Enforce safe/short label for Windows paths
                    safe_label = utils.slugify_if_too_long(base_dir, label)
                    url = obj.get("url") if isinstance(obj, dict) else obj
                    if url:
                        groups.setdefault(safe_label, []).append(url)
                for label, urls in groups.items():
                    qhook = QYT.QHook()
                    qlogger = QYT.QLogger(self.downloadQueue)
                    batch_opts = dict(ydl_opts) if isinstance(ydl_opts, dict) else {}
                    batch_opts["logger"] = qlogger
                    batch_opts["progress_hooks"] = [qhook]
                    batch_opts["outtmpl"] = f"{base_dir}/{label}/%(title)s.%(ext)s"
                    self.downloadQueue.put((urls, batch_opts))
                    qhook.info_changed.connect(self.handle_info_changed)
                    qlogger.message_changed.connect(self.handle_log_entry)
                    if not hasattr(self, "_active_qhooks"):
                        self._active_qhooks = []
                    self._active_qhooks.append((qhook, qlogger))
                self.barProgress.setRange(0, 1)
            else:
                qhook = QYT.QHook()
                qlogger = QYT.QLogger(self.downloadQueue)
                download_opts = dict(ydl_opts) if isinstance(ydl_opts, dict) else {}
                download_opts["logger"] = qlogger
                download_opts["progress_hooks"] = [qhook]
                self.downloadQueue.put((to_download, download_opts))
                qhook.info_changed.connect(self.handle_info_changed)
                qlogger.message_changed.connect(self.handle_log_entry)
                if not hasattr(self, "_active_qhooks"):
                    self._active_qhooks = []
                self._active_qhooks.append((qhook, qlogger))
                self.barProgress.setRange(0, 1)

        # Update indicator according to results
        if had_error:
            self._set_podcast_indicator("error")
        elif to_download:
            self._set_podcast_indicator("busy")
        elif self._podcast_pending_urls:
            self._set_podcast_indicator("pending")
        else:
            self._set_podcast_indicator("all_good")

        # Reset running flag
        self._podcast_check_running = False

        if not to_download and not self._podcast_pending_urls:
            self.logEdit.appendPlainText(
                "No eligible podcast episodes found for immediate download. Pending items will be rechecked at the next scheduled YT Podcasts check.",
            )
        # Summarize results in the UI log
        self.logEdit.appendPlainText(
            f"Podcast check complete: {len(to_download)} queued, {len(self._podcast_pending_urls)} pending, error={had_error}",
        )
        # Auto-refresh the Podcast Status dialog if it is visible so users see results immediately
        try:
            self._refresh_podcast_status_dialog()
        except Exception as e:
            # Don't let refresh errors interfere with normal operation; log them for debugging
            self.logEdit.appendPlainText(f"Error refreshing Podcast Status dialog: {e}")

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
                if not thread.wait(2000):
                    self.logEdit.appendPlainText(
                        "Podcast worker did not exit; terminating thread.",
                    )
                    try:
                        thread.terminate()
                    except Exception as e:
                        self.logEdit.appendPlainText(
                            f"Error terminating podcast thread: {e}",
                        )
                    thread.wait(1000)
        except Exception as e:
            self.logEdit.appendPlainText(f"Error shutting down podcast thread: {e}")
        finally:
            self._podcast_worker = None
            self._podcast_worker_thread = None

    def closeEvent(self, event) -> None:
        """Ensure background podcast checks are stopped when the window closes."""
        try:
            self._shutdown_podcast_thread()
        finally:
            super().closeEvent(event)

    def _get_podcast_statuses(self) -> list[dict]:
        """
        Return a list of podcast status dictionaries.

        {podcast, latest_date, status, url}
        """
        statuses: list[dict] = []
        playlists_path = utils.get_playlist_file_for_source("audio_playlists")
        if not playlists_path:
            return statuses
        try:
            with Path(playlists_path).open("r", encoding="utf-8") as f:
                lines = [
                    ln.strip()
                    for ln in f
                    if ln.strip() and not ln.strip().startswith("#")
                ]
        except Exception:
            return statuses

        # read archive ids
        archive_path = "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt"
        archived_ids: set[str] = set()
        if Path(archive_path).exists():
            try:
                with Path(archive_path).open("r", encoding="utf-8") as af:
                    for line in af:
                        parts = line.strip().split()
                        if parts:
                            archived_ids.add(parts[-1])
            except Exception:
                archived_ids = set()

        now_ts = datetime.now(tz=timezone.utc).timestamp()
        for url in lines:
            try:
                # Limit to the latest episode to avoid long blocking operations
                with yt_dlp.YoutubeDL(
                    {"quiet": True, "no_warnings": True, "playlistend": 1},
                ) as ydl:
                    info = ydl.extract_info(url, download=False)
                title = info.get("title") or info.get("uploader") or url
                entries = info.get("entries", [info])
                if not entries:
                    statuses.append(
                        {
                            "podcast": title,
                            "latest_date": "(none)",
                            "status": "No episodes",
                            "url": url,
                        },
                    )
                    continue
                latest = entries[0]
                vid = latest.get("id") or latest.get("url")
                ts = latest.get("timestamp")
                webpage = latest.get("webpage_url") or latest.get("url")
                if not ts and latest.get("upload_date"):
                    try:
                        ts = (
                            datetime.strptime(
                                latest.get("upload_date"),
                                "%Y%m%d",
                            )
                            .replace(tzinfo=timezone.utc)
                            .timestamp()
                        )
                    except Exception:
                        ts = None
                latest_date = (
                    datetime.fromtimestamp(ts, tz=timezone.utc).strftime(
                        "%Y-%m-%d %H:%M:%S",
                    )
                    if ts
                    else "(unknown)"
                )
                # Determine status
                if vid and vid in archived_ids:
                    status = "Downloaded"
                elif ts and ts > now_ts:
                    # Scheduled for the future -> Upcoming
                    status = "Upcoming"
                # If very new (<24h), check SponsorBlock
                elif ts and (now_ts - ts) < (24 * 60 * 60):
                    site = utils.detect_site_from_urls(
                        [latest.get("webpage_url") or url],
                    )
                    if site == "youtube":
                        has_sb = self._check_sponsorblock_for_video_id(vid)
                        status = "Ready" if has_sb else "Pending SponsorBlock"
                    else:
                        status = "Ready"
                else:
                    status = "Ready"

                entry = {
                    "podcast": title,
                    "latest_date": latest_date,
                    "status": status,
                    "url": url,
                    "latest_url": webpage,
                    "latest_ts": ts,
                }
                if ts and ts > now_ts:
                    entry["recheck_ts"] = ts
                # Update cache immediately
                if webpage:
                    self._cache_put(url, webpage, ts)
                statuses.append(entry)
            except Exception as e:
                statuses.append(
                    {
                        "podcast": url,
                        "latest_date": "(error)",
                        "status": f"Error: {e}",
                        "url": url,
                    },
                )
        return statuses

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
            f"Scheduled hourly YT Podcasts checks beginning {target.strftime('%Y-%m-%d %H:%M:%S')}",
        )

    def _start_hourly_podcast_timer(self) -> None:
        # Run once immediately at the scheduled time, then start recurring hourly timer
        self._hourly_podcast_check()
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


# def is_firefox_running():
#     """Check if Firefox is already running."""
#     for process in psutil.process_iter(["name"]):
#         if process.info["name"] == "firefox.exe":
#             return True
#     return False


if __name__ == "__main__":
    startfile(r"E:\vid storage")  # noqa: S606
    dirname = Path(__file__).parent
    QDir.addSearchPath("icons", str(dirname / "resources" / "icons"))

    # Open Firefox
    # if not is_firefox_running():
    #     subprocess.Popen(
    #         [r"C:/Program Files/Mozilla Firefox/firefox.exe", "https://www.youtube.com"]
    #     )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon("icons:downFrog.png"))
    app.setQuitOnLastWindowClosed(True)

    window = MyWindow()
    window.show()

    app.exec()

# TODO: add way of seeing history info in app?
