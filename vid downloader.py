import sys
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QWidget,
    QGridLayout,
    QProgressBar,
    QPlainTextEdit,
    QPushButton,
)
from PyQt6.QtCore import pyqtSignal
import QYT
from hurry.filesize import size
import queue
import keyring
from datetime import timedelta

dropped = []


class DropLabel(QLabel):
    urlsDropped = pyqtSignal(str, str)

    def __init__(self, text, color, connection):
        QLabel.__init__(self, text)
        self.setStyleSheet(f"background-color:{color}")
        self.setMinimumSize(300, 300)
        self.setAcceptDrops(True)
        self.urlsDropped.connect(connection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()

        # self.setText(f"Dropped URLs: {urls[0].toString()}")

        self.urlsDropped.emit(urls[0].toString(), self.text())


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.downloadQueue = queue.Queue()
        layout = QGridLayout()

        self.buttonPlaylists = QPushButton("Playlists")
        self.label1080 = DropLabel("1080", "red", self.updateOutput)
        self.label720 = DropLabel("720", "green", self.updateOutput)
        self.labelAudio = DropLabel("audio", "brown", self.updateOutput)
        self.labelOutput = QLabel("This is the output")
        self.labelOutput.setStyleSheet("background-color:lightblue")
        self.barProgress = QProgressBar()
        self.logEdit = QPlainTextEdit(readOnly=True)

        layout.addWidget(self.buttonPlaylists, 0, 0)
        layout.addWidget(self.label1080, 1, 0)
        layout.addWidget(self.label720, 1, 1)
        layout.addWidget(self.labelAudio, 1, 2)
        layout.addWidget(self.labelOutput, 2, 0, 1, 3)
        layout.addWidget(self.barProgress, 3, 0, 1, 3)
        layout.addWidget(self.logEdit, 4, 0, 1, 3)

        self.downloader = QYT.QYTQueue(self.downloadQueue)
        self.downloader.start()
        self.setLayout(layout)

    def updateOutput(self, url, source):
        # self.downloadQueue.put(url)

        qhook = QYT.QHook()
        qlogger = QYT.QLogger()

        ydl_opts = {
            "logger": qlogger,
            "progress_hooks": [qhook],
            "windowsfilenames": True,
            "download_archive": "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt",
        }
        ydl_opts = self.getOptions(url, source, ydl_opts)
        self.downloadQueue.put((url, ydl_opts))
        # self.downloader.download([url], ydl_opts)
        qhook.infoChanged.connect(self.handleInfoChanged)
        qlogger.messageChanged.connect(self.logEdit.appendPlainText)
        self.barProgress.setRange(0, 1)

    def getOptions(self, url, source, options):
        if "nebula.tv" in url:
            options["username"] = "thegene@gmail.com"
            options["password"] = keyring.get_password(
                "vid downloader", "thegene@gmail.com"
            )
        if source == "audio":
            options["format"] = "m4a/bestaudio/best"
            options["postprocessors"] = [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}
            ]
            options["outtmpl"] = "E:/vid storage/audio/%(title)s.%(ext)s"
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
            output = f"{size(downloaded)} of {size(total)} at {size(d['speed'])}/s"
            if d["eta"]:
                output += f" | ETA: {timedelta(seconds=round(d['eta']))}"
            self.labelOutput.setText(output)
            if total > 2147483647:  # scale things down if too big to fit in int
                self.barProgress.setMaximum(2147483647)
                self.barProgress.setValue(int(downloaded / total * 2147483647))
            else:
                self.barProgress.setMaximum(total)
                self.barProgress.setValue(downloaded)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec())
