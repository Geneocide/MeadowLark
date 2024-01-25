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
            lambda: self.requestDetected([], "playlists")
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
        self.labelOutput = QLabel("This is the output")
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
        self.downloader.messageChanged.connect(self.logEdit.appendPlainText)
        self.downloader.queueEmpty.connect(self.handleQueueEmpty)
        self.downloader.start()
        self.setLayout(layout)

    def requestDetected(self, urls, source):
        qhook = QYT.QHook()
        qlogger = QYT.QLogger()
        playlistsPath = None
        if source == "playlists":
            playlistsPath = "C:/Users/etreq/OneDrive/Desktop/scripts/playlists.txt"
        elif source == "720playlists":
            playlistsPath = "C:/Users/etreq/OneDrive/Desktop/scripts/720playlists.txt"
        if playlistsPath:
            with open(playlistsPath, "r") as file:
                for line in file:
                    line = line.strip()
                    if line[0] != "#":  # ignore comment lines
                        urls.append(line)

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
            qlogger.messageChanged.connect(self.logEdit.appendPlainText)
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
        if source == "audio":
            options["format"] = "m4a/bestaudio/best"
            options["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
            ]
            options["outtmpl"] = "E:/vid storage/audio/%(title)s.%(ext)s"
        elif "playlists" in source:
            options["format_sort"] = (
                ["res:720"] if source == "720playlists" else ["res:1080"]
            )
            options["merge_output_format"] = "mp4"
            options[
                "outtmpl"
            ] = "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s"
            options["ignoreerrors"] = "only_download"
        # is a dragged 1080 or 720 video
        else:
            options["format_sort"] = [f"res:{source}"]
            options["merge_output_format"] = "mp4"
            options["outtmpl"] = "E:/vid storage/%(title)s.%(ext)s"

        return options

    def handleInfoChanged(self, d):
        if d["status"] == "downloading":
            if "total_bytes" in d:
                total = d["total_bytes"]
                downloaded = d["downloaded_bytes"]
            elif "total_bytes_estimate" in d:
                total = d["total_bytes_estimate"]
                total = round(total)
                downloaded = d["downloaded_bytes"]
            speed = d["speed"] if d["speed"] else 0
            output = f"{size(downloaded)} of {size(total)} at {size(speed)}/s"
            if d["eta"]:
                output += f" | ETA: {timedelta(seconds=round(d['eta']))}"
            self.labelOutput.setText(output)
            if total > 2147483647:  # scale things down if too big to fit in int
                self.barProgress.setMaximum(2147483647)
                self.barProgress.setValue(int(downloaded / total * 2147483647))
            else:
                self.barProgress.setMaximum(total)
                self.barProgress.setValue(downloaded)

    def handleQueueEmpty(self, isEmpty):
        if isEmpty:
            self.labelOutput.setText("[ Ready ]")


if __name__ == "__main__":
    dirname = path.dirname(__file__)
    QDir.addSearchPath("icons", path.join(dirname, "resources/icons"))

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon("icons:downFrog.png"))
    app.setQuitOnLastWindowClosed(True)

    window = MyWindow()
    window.show()

    sys.exit(app.exec())
