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
)
from PyQt6.QtCore import Qt, QDir
from PyQt6.QtGui import QFont, QIcon
import QYT
from hurry.filesize import size
import queue
import keyring
from datetime import timedelta
from yt_dlp import YoutubeDL
from os import path
from UIClasses import *


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vid Downloader")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.downloadQueue = queue.Queue()
        layout = QGridLayout()

        self.buttonPlaylists = QPushButton("Playlists")
        self.buttonPlaylists.clicked.connect(
            lambda: self.requestDetected([], "1080playlists")
        )
        self.button720Playlists = QPushButton("720 Playlists")
        self.button720Playlists.clicked.connect(
            lambda: self.requestDetected([], "720playlists")
        )
        self.checkIgnoreArchive = QCheckBox("Ignore Archive?")
        self.checkIgnoreArchive.setChecked(False)
        self.label1080 = DropLabel("1080", "#424769", self.requestDetected)
        self.label720 = DropLabel("720", "#7077A1", self.requestDetected)
        self.labelAudio = DropLabel("audio", "#FF9843", self.requestDetected)
        self.labelOutput = QLabel("[ Waiting ]")
        self.labelOutput.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.labelOutput.setFont(QFont("Arial", 16))
        self.barProgress = QProgressBar()
        self.logEdit = QPlainTextEdit(readOnly=True)

        layout.addWidget(self.buttonPlaylists, 0, 0)
        layout.addWidget(self.button720Playlists, 0, 1)
        layout.addWidget(self.checkIgnoreArchive, 0, 2)
        layout.addWidget(self.label1080, 1, 0)
        layout.addWidget(self.label720, 1, 1)
        layout.addWidget(self.labelAudio, 1, 2)
        layout.addWidget(self.labelOutput, 2, 0, 1, 3)
        layout.addWidget(self.barProgress, 3, 0, 1, 3)
        layout.addWidget(self.logEdit, 4, 0, 1, 3)

        self.downloader = QYT.QYTQueue(self.downloadQueue)
        # self.downloader.messageChanged.connect(self.logEdit.appendPlainText)
        self.downloader.messageChanged.connect(self.handleLogEntry)
        self.downloader.queueEmpty.connect(self.handleQueueEmpty)
        self.downloader.start()
        self.setLayout(layout)

    def requestDetected(self, urls, source):
        qhook = QYT.QHook()
        qlogger = QYT.QLogger(self.downloadQueue)
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
        }
        ydl_opts = self.getOptions(urls, source, ydl_opts)
        if ydl_opts:
            self.downloadQueue.put((urls, ydl_opts))
            qhook.infoChanged.connect(self.handleInfoChanged)
            # qlogger.messageChanged.connect(self.logEdit.appendPlainText)
            qlogger.messageChanged.connect(self.handleLogEntry)
            self.barProgress.setRange(0, 1)

    # parse input data and modify options accordingly
    def getOptions(self, urls, source, options):
        # ignore archive checkbox
        if not self.checkIgnoreArchive.isChecked():
            options[
                "download_archive"
            ] = "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt"
        # detect and login to nebula when necessary
        if "nebula.tv" in urls[0]:
            options["username"] = "thegene@gmail.com"
            options["password"] = keyring.get_password(
                "vid downloader", "thegene@gmail.com"
            )
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
                        options["playlist_items"] = playlistInput
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
            options.update(source_options[source])
        else:
            options.update(
                {
                    "format_sort": [f"res:{source}"],
                    "merge_output_format": "mp4",
                    "outtmpl": "E:/vid storage/%(title)s.%(ext)s",
                }
            )

        return options

    def handleLogEntry(self, entry):
        if "[Merger]" in entry:
            self.labelOutput.setText("Merging! This can take a while...")
        self.logEdit.appendPlainText(entry)

    def handleInfoChanged(self, d):
        MAX_INT = 2147483647
        if d.get("status") == "downloading":
            if "total_bytes" in d:
                total = d["total_bytes"]
                downloaded = d["downloaded_bytes"]
            elif "total_bytes_estimate" in d:
                total = d["total_bytes_estimate"]
                total = round(total)
                downloaded = d["downloaded_bytes"]
            speed = d["speed"] if d["speed"] else 0
            output = f"{size(downloaded)} of {size(total)} at {size(speed)}/s"
            if d.get("eta"):
                output += f" | ETA: {timedelta(seconds=round(d['eta']))}"
            self.labelOutput.setText(output)
            if total is not None:
                if total > MAX_INT:
                    self.barProgress.setMaximum(MAX_INT)
                    self.barProgress.setValue(int(downloaded / total * MAX_INT))
                else:
                    self.barProgress.setMaximum(total)
                    self.barProgress.setValue(downloaded)

    def handleQueueEmpty(self, isEmpty):
        if isEmpty:
            self.labelOutput.setText("[ Ready ]")
        return isEmpty


if __name__ == "__main__":
    dirname = path.dirname(__file__)
    QDir.addSearchPath("icons", path.join(dirname, "resources/icons"))

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon("icons:downFrog.png"))
    app.setQuitOnLastWindowClosed(True)

    window = MyWindow()
    window.show()

    app.exec()
