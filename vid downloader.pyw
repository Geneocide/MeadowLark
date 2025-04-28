import sys
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QGridLayout,
    QProgressBar,
    QPlainTextEdit,
    QPushButton,
    QCheckBox,
    QHBoxLayout,
)
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QFont, QIcon
import QYT
from hurry.filesize import size
import queue
import keyring
from datetime import timedelta

from yt_dlp import YoutubeDL
from yt_dlp import utils

from os import path, startfile
from UIClasses import *
import subprocess
import os
import psutil


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vid Downloader")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        layout = QGridLayout()

        self.buttonPlaylists = QPushButton("Playlists")
        self.buttonPlaylists.clicked.connect(
            lambda: self.requestDetected([], "1080playlists")
        )
        self.button720Playlists = QPushButton("720 Playlists")
        self.button720Playlists.clicked.connect(
            lambda: self.requestDetected([], "720playlists")
        )
        rightBox = QHBoxLayout()
        self.checkIgnoreArchive = QCheckBox("Ignore Archive?")
        self.checkIgnoreArchive.setChecked(False)
        self.buttonUpdate = QPushButton("⤓")
        self.buttonUpdate.clicked.connect(lambda: self.requestDetected([], "Update"))
        self.buttonUpdate.setVisible(True)
        self.label1080 = DropLabel("1080", "#424769", self.requestDetected)
        self.label720 = DropLabel("720", "#7077A1", self.requestDetected)
        self.labelAudio = DropLabel("audio", "#FF9843", self.requestDetected)
        self.labelOutput = QLabel("[ Waiting ]")
        self.labelOutput.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.labelOutput.setFont(QFont("Arial", 16))
        self.barProgress = QProgressBar()
        self.logEdit = QPlainTextEdit(readOnly=True)

        rightBox.addWidget(self.checkIgnoreArchive)
        rightBox.addWidget(self.buttonUpdate)

        layout.addWidget(self.buttonPlaylists, 0, 0)
        layout.addWidget(self.button720Playlists, 0, 1)
        layout.addLayout(rightBox, 0, 2)
        layout.setColumnStretch(2, 1)
        # layout.addWidget(self.checkIgnoreArchive, 0, 2)
        # layout.addWidget(self.buttonUpdate, 0, 3)
        layout.addWidget(self.label1080, 1, 0)
        layout.addWidget(self.label720, 1, 1)
        layout.addWidget(self.labelAudio, 1, 2)
        layout.addWidget(self.labelOutput, 2, 0, 1, 3)
        layout.addWidget(self.barProgress, 3, 0, 1, 3)
        layout.addWidget(self.logEdit, 4, 0, 1, 3)

        self.downloadQueue = queue.Queue()
        self.downloader = QYT.QYTQueue(self.downloadQueue)
        # self.downloader.messageChanged.connect(self.logEdit.appendPlainText)
        self.downloader.messageChanged.connect(self.handleLogEntry)
        self.downloader.queueEmpty.connect(self.handleQueueEmpty)
        self.downloader.start()
        self.setLayout(layout)

        self.latest_version = self.checkForUpdates()

    def append_properties(self, dictionary, properties):
        """
        Appends properties to a dictionary recursively.

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

    def requestDetected(self, urls, source):
        qhook = QYT.QHook()
        qlogger = QYT.QLogger(self.downloadQueue)
        if source == "Update":
            self.doUpdates(self.latest_version)
            return
        playlistsPath = {
            "1080playlists": "C:/Users/etreq/OneDrive/Desktop/scripts/playlists.txt",
            "720playlists": "C:/Users/etreq/OneDrive/Desktop/scripts/720playlists.txt",
        }.get(source)
        if playlistsPath:
            try:
                with open(playlistsPath, "r") as file:
                    urls = [line.strip() for line in file if line[0] != "#"]
            except FileNotFoundError:
                print("File not found.")

        # options constant for all downloads
        ydl_opts = {
            "logger": qlogger,
            "progress_hooks": [qhook],
            "windowsfilenames": True,
            "postprocessors": [
                {"key": "SponsorBlock"},
                {
                    "key": "ModifyChapters",
                    "remove_sponsor_segments": ["sponsor", "selfpromo"],
                },
            ],
            "socket-timeout": 120,
            "max_fragment_retries": 10,
        }
        properties = self.getOptions(urls, source)
        if properties:
            ydl_opts = self.append_properties(ydl_opts, properties)
            if ydl_opts:
                self.downloadQueue.put((urls, ydl_opts))
                qhook.infoChanged.connect(self.handleInfoChanged)
                # qlogger.messageChanged.connect(self.logEdit.appendPlainText)
                qlogger.messageChanged.connect(self.handleLogEntry)
                self.barProgress.setRange(0, 1)

    # parse input data and modify options accordingly
    def getOptions(self, urls, source):
        properties = {}
        # ignore archive checkbox
        if not self.checkIgnoreArchive.isChecked():
            properties["download_archive"] = (
                "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt"
            )
        # detect and login to nebula when necessary
        if "nebula.tv" in urls[0]:
            properties["username"] = "thegene@gmail.com"
            properties["password"] = keyring.get_password(
                "vid downloader", "thegene@gmail.com"
            )
        # detect and use cookies for youtube if necessary
        elif "youtube.com" in urls[0]:
            properties["cookiefile"] = "cookies.txt"
            # properties["cookiesfrombrowser"] = ("edge",)
        # strip out unnecessary parts of URL if dropping from Watch Later
        urls = [url.split("&list=WL")[0] for url in urls]

        # individual playlist dragged somewhere
        if "list=" in urls[0] and "playlist" not in source:
            with YoutubeDL({"extract_flat": "in_playlist"}) as ydl:
                info = ydl.extract_info(urls[0], download=False)
                playlistCount = info["playlist_count"]
                dialog = PlaylistDialog(playlistCount)
                if dialog.exec():
                    playlistInput = dialog.getPlaylistInput()
                    # a blank return will set no option so default to downloading whole playlist
                    if playlistInput:
                        properties["playlist_items"] = playlistInput
                    if source != "audio":
                        source += "playlists"
                else:  # will cancel playlist download
                    return False

        # source
        source_options = {
            "audio": {
                "format": "m4a/bestaudio/best",
                "postprocessors": [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
                ],
                "outtmpl": "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/%(title)s.%(ext)s",
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
            properties.update(source_options[source])
        else:
            properties.update(
                {
                    "format_sort": [f"res:{source}"],
                    "merge_output_format": "mp4",
                    "outtmpl": "E:/vid storage/%(title)s.%(ext)s",
                    "match_filter": utils.match_filter_func("!is_live"),
                }
            )

        return properties

    def handleLogEntry(self, entry):
        if "[Merger]" in entry:
            self.labelOutput.setText("Merging! This can take a while...")
        self.logEdit.appendPlainText(entry)

    def handleInfoChanged(self, d):
        MAX_INT = 2147483647
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get(
                "total_bytes_estimate", round(d.get("total_bytes_estimate", 0))
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
                if total > MAX_INT:
                    self.barProgress.setMaximum(MAX_INT)
                    self.barProgress.setValue(int(downloaded / total * MAX_INT))
                else:
                    self.barProgress.setMaximum(int(total))
                    self.barProgress.setValue(downloaded)

    def handleQueueEmpty(self, isEmpty):
        if isEmpty:
            self.labelOutput.setText("[ Ready ]")
        return isEmpty

    def checkForUpdates(self):
        result = subprocess.run(
            ["pip", "index", "versions", "yt-dlp"], capture_output=True, text=True
        )
        if result.returncode != 0:
            self.buttonUpdate.setStyleSheet("color: red;")
            return

        index_info = result.stdout.split("\n")
        installed_version = index_info[2].split(":")[1].strip()
        latest_version = index_info[3].split(":")[1].strip()

        if latest_version == installed_version:
            self.buttonUpdate.setVisible(False)
        else:
            self.buttonUpdate.setStyleSheet("color: red;")

        return latest_version

    def doUpdates(self, latest_version):
        upgrade_process = subprocess.run(["pip", "install", "--upgrade", "yt-dlp"])
        if upgrade_process.returncode == 0:
            result = subprocess.run(
                ["pip", "show", "yt-dlp"], capture_output=True, text=True
            )
            installed_version = result.stdout.split("\n")[1].split(":")[1].strip()
            if installed_version == latest_version:
                # update successful
                python = sys.executable
                script = os.path.realpath(sys.argv[0])

                os.execl(python, python, script, *sys.argv[1:])
            else:
                # update failed
                self.buttonUpdate.setStyleSheet("color: red;")


# def is_firefox_running():
#     """Check if Firefox is already running."""
#     for process in psutil.process_iter(["name"]):
#         if process.info["name"] == "firefox.exe":
#             return True
#     return False


if __name__ == "__main__":
    startfile(r"E:\vid storage")
    dirname = path.dirname(__file__)
    QDir.addSearchPath("icons", path.join(dirname, "resources/icons"))

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
