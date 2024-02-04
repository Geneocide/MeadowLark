from PyQt6.QtWidgets import (
    QLabel,
    QGridLayout,
    QPushButton,
    QDialog,
    QLineEdit,
)
from PyQt6.QtGui import QFont, QDragEnterEvent
from PyQt6.QtCore import Qt, pyqtSignal, QTimer


class PlaylistDialog(QDialog):
    ADDED_TEXT = "Added!!!"
    urlsDropped = pyqtSignal(list, str)

    def __init__(self, playlistCount, parent=None):
        super().__init__(parent)

        self.setWindowTitle(self.tr("Playlist Dialog"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        label = QLabel(
            self.tr(
                f"There are {playlistCount} videos in the playlist. Which do you want? Blank = all or format like (3,5,7-9)"
            )
        )
        label.setFont(QFont(QFont().defaultFamily(), 12))
        self.playlistInput = QLineEdit()
        ok_button = QPushButton()
        ok_button.setText("OK")
        ok_button.clicked.connect(self.accept)

        layout = QGridLayout()
        layout.addWidget(label, 0, 0, 1, 2)
        layout.addWidget(self.playlistInput, 1, 0)
        layout.addWidget(ok_button, 1, 1)

        self.setLayout(layout)

    def getPlaylistInput(self):
        return self.playlistInput.text()

    def dragEnterEvent(self, event):
        """
        Handle the drag enter event.

        Args:
            event (QDragEnterEvent): The drag enter event.
        """
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()


class DropLabel(QLabel):
    ADDED_TEXT = "Added!!!"
    urlsDropped = pyqtSignal(list, str)

    def __init__(
        self,
        text,
        color,
        connection,
        min_width=150,
        min_height=150,
        font_family="Arial",
        font_size=32,
    ):
        super().__init__(text)
        self.originalText = text
        self.setStyleSheet(f"background-color:{color}")
        self.setMinimumSize(min_width, min_height)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont(font_family, font_size))
        self.urlsDropped.connect(connection)
        self.timer = QTimer()

    def dragEnterEvent(self, event: QDragEnterEvent) -> bool:
        """
        Handle the drag enter event.

        Args:
            event (QDragEnterEvent): The drag enter event.
        """
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        self.setText(self.ADDED_TEXT)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.setText(self.originalText))
        self.timer.start(2000)
        urls = event.mimeData().urls()
        self.urlsDropped.emit([url.toString() for url in urls], self.originalText)

    # def dropEvent(self, event):
    #     def timeout():
    #         self.setText(self.originalText)

    #     self.setText("Added!!!")
    #     t = Timer(2, timeout)
    #     t.start()
    #     urls = event.mimeData().urls()
    #     self.urlsDropped.emit([url.toString() for url in urls], self.originalText)
