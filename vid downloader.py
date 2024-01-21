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
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
import QYT
from hurry.filesize import size
import queue
import keyring
from datetime import timedelta
from threading import Timer


class DropLabel(QLabel):
    urlsDropped = pyqtSignal(list, str)
    originalText = ""

    def __init__(self, text, color, connection):
        QLabel.__init__(self, text)
        self.originalText = text
        self.setStyleSheet(f"background-color:{color}")
        self.setMinimumSize(300, 300)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont("Arial", 32))
        self.urlsDropped.connect(connection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        def timeout():
            self.setText(self.originalText)

        self.setText("Added!!!")
        t = Timer(3, timeout)
        t.start()
        urls = event.mimeData().urls()
        self.urlsDropped.emit([url.toString() for url in urls], self.text())


class MyWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.downloadQueue = queue.Queue()
        layout = QGridLayout()

        self.buttonPlaylists = QPushButton("Playlists")
        self.buttonPlaylists.clicked.connect(lambda: self.dropDetected([], "playlists"))
        self.checkIgnoreArchive = QCheckBox("Ignore Archive?")
        self.checkIgnoreArchive.setChecked(False)
        self.label1080 = DropLabel("1080", "red", self.dropDetected)
        self.label720 = DropLabel("720", "green", self.dropDetected)
        self.labelAudio = DropLabel("audio", "brown", self.dropDetected)
        self.labelOutput = QLabel("This is the output")
        self.labelOutput.setStyleSheet("background-color:lightblue")
        self.labelOutput.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.labelOutput.setFont(QFont("Arial", 16))
        self.barProgress = QProgressBar()
        self.logEdit = QPlainTextEdit(readOnly=True)

        layout.addWidget(self.buttonPlaylists, 0, 0)
        layout.addWidget(self.checkIgnoreArchive, 0, 1)
        layout.addWidget(self.label1080, 1, 0)
        layout.addWidget(self.label720, 1, 1)
        layout.addWidget(self.labelAudio, 1, 2)
        layout.addWidget(self.labelOutput, 2, 0, 1, 3)
        layout.addWidget(self.barProgress, 3, 0, 1, 3)
        layout.addWidget(self.logEdit, 4, 0, 1, 3)

        self.downloader = QYT.QYTQueue(self.downloadQueue)
        self.downloader.messageChanged.connect(self.logEdit.appendPlainText)
        self.downloader.start()
        self.setLayout(layout)

    def dropDetected(self, urls, source):
        qhook = QYT.QHook()
        qlogger = QYT.QLogger()

        if source == "playlists":
            with open(
                "C:/Users/etreq/OneDrive/Desktop/scripts/playlists.txt", "r"
            ) as file:
                for line in file:
                    line = line.strip()
                    if line[0] != "#":  # ignore comment lines
                        urls.append(line)

        ydl_opts = {
            "logger": qlogger,
            "progress_hooks": [qhook],
            "windowsfilenames": True,
        }
        ydl_opts = self.getOptions(urls, source, ydl_opts)
        self.downloadQueue.put((urls, ydl_opts))
        qhook.infoChanged.connect(self.handleInfoChanged)
        qlogger.messageChanged.connect(self.logEdit.appendPlainText)
        self.barProgress.setRange(0, 1)

    def getOptions(self, urls, source, options):
        if not self.checkIgnoreArchive.isChecked():
            options[
                "download_archive"
            ] = "C:/Users/etreq/OneDrive/Desktop/scripts/tfarchive.txt"
        if "nebula.tv" in urls[0]:
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
        elif source == "playlists":
            options["format_sort"] = ["res:1080"]
            options["merge_output_format"] = "mp4"
            options[
                "outtmpl"
            ] = "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s"
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


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyWindow()
    window.setWindowTitle("Vid Downloader")
    window.show()
    sys.exit(app.exec())
