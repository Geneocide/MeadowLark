from PyQt6.QtWidgets import (
    QLabel,
    QGridLayout,
    QPushButton,
    QDialog,
    QLineEdit,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, pyqtSignal
from threading import Timer


class PlaylistDialog(QDialog):
    def __init__(self, playlistCount, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Playlist Dialog")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        label = QLabel(
            f"There are {playlistCount} videos in the playlist. Which do you want? Blank = all or format like (3,5,7-9)"
        )
        label.setFont(QFont("Arial", 12))
        self.playlistInput = QLineEdit()
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)

        layout = QGridLayout()
        layout.addWidget(label, 0, 0, 1, 2)
        layout.addWidget(self.playlistInput, 1, 0)
        layout.addWidget(ok_button, 1, 1)

        self.setLayout(layout)

    def getPlaylistInput(self):
        return self.playlistInput.text()


class DropLabel(QLabel):
    urlsDropped = pyqtSignal(list, str)
    originalText = ""

    def __init__(self, text, color, connection):
        QLabel.__init__(self, text)
        self.originalText = text
        self.setStyleSheet(f"background-color:{color}")
        self.setMinimumSize(150, 150)
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
        t = Timer(2, timeout)
        t.start()
        urls = event.mimeData().urls()
        self.urlsDropped.emit([url.toString() for url in urls], self.originalText)
