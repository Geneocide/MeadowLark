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
from PyQt6.QtCore import QDir, Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QLabel,
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
            lambda: self.request_detected([], "1080playlists"),
        )
        self.button720Playlists = PlaylistButton(
            "720 Playlists",
            r"Z:\misc\dev\vid downloader\resources\playlists\720playlists.txt",
        )
        self.button720Playlists.clicked.connect(
            lambda: self.request_detected([], "720playlists"),
        )
        self.buttonAudioPlaylists = PlaylistButton(
            "YT Podcasts",
            r"Z:\misc\dev\vid downloader\resources\playlists\audio playlists.txt",
        )
        self.buttonAudioPlaylists.clicked.connect(
            lambda: self.request_detected([], "audio_playlists"),
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

        update_available, _, _ = utils.is_yt_dlp_update_available()
        self.buttonUpdate.setVisible(update_available)

    def append_properties(self, dictionary: dict, properties: dict) -> dict:
        """
        Append properties to a dictionary recursively.

        Args:
            dictionary (dict): The dictionary to append properties to.
            properties (dict): The properties to append.

        Returns:
            dict: The updated dictionary.
        """
        new_dictionary = dictionary.copy()
        for key, value in properties.items():
            dictionary_value = new_dictionary.get(key)
            if isinstance(dictionary_value, (list, dict)):
                if isinstance(dictionary_value, list) and isinstance(value, list):
                    dictionary_value.extend(value)
                elif isinstance(dictionary_value, dict):
                    self.append_properties(dictionary_value, value)
            else:
                new_dictionary[key] = value
        return new_dictionary

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
        playlists_path = {
            "1080playlists": r"Z:\misc\dev\vid downloader\resources\playlists\playlists.txt",
            "720playlists": r"Z:\misc\dev\vid downloader\resources\playlists\720playlists.txt",
            "audio_playlists": r"Z:\misc\dev\vid downloader\resources\playlists\audio playlists.txt",
        }.get(source)
        if playlists_path:
            try:
                with Path(playlists_path).open("r") as file:
                    urls = [line.strip() for line in file if line[0] != "#"]
            except FileNotFoundError:
                print("File not found.")

        # options constant for all downloads
        ydl_opts = {
            "logger": qlogger,
            "progress_hooks": [qhook],
            "windowsfilenames": True,
            "socket-timeout": 120,
            "max_fragment_retries": 10,
            "mtime": True,
            "match_filter": yt_dlp.utils.match_filter_func(
                "!is_live",
            ),
            "cookiefile": r"resources\cookies.txt",
            "postprocessors": [
                {"key": "SponsorBlock"},
                {
                    "key": "ModifyChapters",
                    "remove_sponsor_segments": ["sponsor", "selfpromo"],
                },
            ],
        }

        properties = self.get_options(urls, source)
        if properties:
            ydl_opts = self.append_properties(ydl_opts, properties)
            if ydl_opts:
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
            # Existing match_filter
            match_filters = ["!is_live"]
            # Append your requested filters
            match_filters.append("live_status!=is_upcoming")
            match_filters.append("availability!=needs_auth")
            properties["match_filter"] = yt_dlp.utils.match_filter_func(
                " & ".join(match_filters),
            )
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
                "format_sort": ["res:720"],
                "merge_output_format": "mp4",
                "outtmpl": "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s",
                "ignoreerrors": "only_download",
            },
            "1080playlists": {
                "format_sort": ["res:1080"],
                "merge_output_format": "mp4",
                "outtmpl": "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s",
                "ignoreerrors": "only_download",
            },
        }

        if source in source_options:
            if "playlists" in source:
                # Existing match_filter
                match_filters = ["!is_live"]
                match_filters.append("live_status!=is_upcoming")
                match_filters.append("availability!=needs_auth")
                properties["match_filter"] = yt_dlp.utils.match_filter_func(
                    " & ".join(match_filters),
                )
            properties.update(source_options[source])
        else:
            properties.update(
                {
                    "format_sort": [f"res:{source}"],
                    "merge_output_format": "mp4",
                    "outtmpl": "E:/vid storage/%(title)s.%(ext)s",
                },
            )

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

    if not os.environ.get("YTDLP_JS"):
        deno = shutil.which("deno")
        if deno:
            os.environ["YTDLP_JS"] = deno
        else:
            os.environ["YTDLP_JS"] = "deno"  # fallback; if on PATH later it will work

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

# TODO: add a history function, perhaps last 5 actually downloaded... maybe 5 for nebula and YT separately
# TODO: queue and recheck anything that's live and dl once it's done being live?
