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

import os
import queue
import shutil
import subprocess
import sys
import webbrowser
from datetime import timedelta
from os import startfile
from pathlib import Path

import yt_dlp
from hurry.filesize import size
from PyQt6.QtCore import QDir, Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

import QYT
import utils
from UIClasses import DropLabel, PlaylistButton, PlaylistDialog


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
        self.buttonAudioPlaylists.clicked.connect(
            lambda: self.playlist_button_clicked("audio_playlists"),
        )
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
        self.labelOutput = QLabel("[ Waiting ]")
        self.labelOutput.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.labelOutput.setFont(QFont("Arial", 16))
        self.barProgress = QProgressBar()
        self.logEdit = QPlainTextEdit(readOnly=True)

        layout.addWidget(self.checkSkipDownload, 0, 0)
        layout.addWidget(self.checkIgnoreArchive, 0, 1)
        layout.addWidget(self.buttonUpdate, 0, 2)
        layout.addWidget(self.buttonPlaylists, 1, 0)
        layout.addWidget(self.button720Playlists, 1, 1)
        layout.addWidget(self.buttonAudioPlaylists, 1, 2)
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
        """
        Merge properties into dictionary recursively using the shared utility.
        """
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
                with Path(playlists_path).open("r") as file:
                    urls = [line.strip() for line in file if line[0] != "#"]
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
                "outtmpl": "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/%(playlist)s/%(title)s.%(ext)s",
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
        """Update the output label to indicate that the download queue is ready."""
        self.labelOutput.setText("[ Ready ]")

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
                if availability == "needs_auth":
                    return "Skipping: needs_auth"
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
