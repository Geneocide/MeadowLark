"""
Defines custom PyQt6 widgets for playlist selection and drag-and-drop functionality.

PlaylistDialog provides a dialog for users to specify which videos from a playlist to select, supporting both manual input and drag-and-drop of URLs.

DropLabel is a QLabel subclass that accepts dropped URLs, emits a signal when URLs are dropped, and provides visual feedback.

"""

from os import startfile
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont, QMouseEvent
from PyQt6.QtWidgets import (
    QDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

import utils


class PlaylistDialog(QDialog):
    """
    A dialog for selecting specific videos from a playlist, supporting manual input and drag-and-drop of URLs.

    Provides a text input for specifying video indices and an OK button to confirm selection. Emits a signal when URLs are dropped.
    """

    ADDED_TEXT = "Added!!!"
    urls_dropped = pyqtSignal(list, str)

    def __init__(self, playlist_count: int, parent: QWidget = None) -> None:
        """
        Initialize the playlist selection dialog, setting up the window title, input field, and OK button.

        Displays the total number of videos in the playlist and allows users to specify which videos to select.
        """
        super().__init__(parent)

        self.setWindowTitle(self.tr("Playlist Dialog"))
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        label = QLabel(
            self.tr(
                f"There are {playlist_count} videos in the playlist. Which do you want? Blank = all or format like (3,5,7-9)",
            ),
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

    def get_playlist_input(self) -> str:
        """
        Return the current text entered in the playlist input field.

        Returns:
            str: The text from the playlist input.
        """
        return self.playlistInput.text()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
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
    """
    .

    A QLabel subclass that accepts drag-and-drop of URLs, emits a signal when URLs are dropped, and provides visual feedback by temporarily changing its text.

    Args:
        text (str): The label's initial text.
        color (str): The background color for the label.
        connection (callable): Slot to connect to the urls_dropped signal.

    Signals:
        urls_dropped (list, str): Emitted with a list of dropped URLs and the original label text.
    """

    ADDED_TEXT = "Added!!!"
    urls_dropped = pyqtSignal(list, str)

    def __init__(
        self,
        text: str,
        color: str,
        connection: Any,  # noqa: ANN401
    ) -> None:
        """
        Initialize the label with custom text, background color, and a connection for the URLs dropped signal.

        Args:
            text (str): The label text.
            color (str): The background color.
            connection (callable): Slot to connect to the urls_dropped signal.
        """
        super().__init__(text)
        min_width = 150
        min_height = 150
        font_family = "Arial"
        font_size = 32
        self.originalText = text
        self.setStyleSheet(f"background-color:{color}")
        self.setMinimumSize(min_width, min_height)
        self.setAcceptDrops(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFont(QFont(font_family, font_size))
        self.urls_dropped.connect(connection)
        self.timer = QTimer()

    def dragEnterEvent(self, event: QDragEnterEvent) -> bool:  # noqa: N802
        """
        Handle the drag enter event.

        Args:
            event (QDragEnterEvent): The drag enter event.
        """
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        """
        Handle the drop event by updating the label text, starting a timer to revert the text, and emitting the dropped URLs via the urls_dropped signal.

        Args:
            event (QDropEvent): The drop event containing the dropped data.
        """
        self.setText(self.ADDED_TEXT)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(lambda: self.setText(self.originalText))
        self.timer.start(2000)
        urls = event.mimeData().urls()
        self.urls_dropped.emit([url.toString() for url in urls], self.originalText)

    # def dropEvent(self, event):
    #     def timeout():
    #         self.setText(self.originalText)

    #     self.setText("Added!!!")
    #     t = Timer(2, timeout)
    #     t.start()
    #     urls = event.mimeData().urls()
    #     self.urlsDropped.emit([url.toString() for url in urls], self.originalText)


class PlaylistButton(QPushButton):
    """
    .

    A QPushButton subclass that opens a playlist file on right-click.

    Displays a button that opens the associated playlist file when right-clicked.
    """

    def __init__(
        self,
        text: str,
        playlist_path: str | Path,
        *args: Any,  # noqa: ANN401
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        """
        .

        Initialize the button with text, playlist path, and optional Qt arguments.

        Args:
            text: The button label text.
            playlist_path: Path to the playlist file.
            *args: Additional positional arguments for QPushButton.
            **kwargs: Additional keyword arguments for QPushButton.
        """
        super().__init__(text, *args, **kwargs)
        self.playlist_path = Path(playlist_path)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        """
        .

        Handle mouse press events to open playlist on right-click.

        Args:
            event: The mouse press event.
        """
        if event.button() == Qt.MouseButton.RightButton:
            if self.playlist_path.exists():
                startfile(self.playlist_path)  # noqa: S606
            else:
                try:
                    raise FileNotFoundError(
                        f"Playlist file not found: {self.playlist_path}",
                    )
                except FileNotFoundError as e:
                    utils.log_exception(
                        e,
                        "Failed to open playlist file on right-click",
                    )
        else:
            super().mousePressEvent(event)
