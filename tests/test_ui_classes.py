"""Unit tests for UIClasses module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QMouseEvent
from PyQt6.QtWidgets import QApplication

from UIClasses import DropLabel, PlaylistButton, PlaylistDialog

# Ensure QApplication exists for Qt testing
_app = QApplication.instance() or QApplication([])


class TestPlaylistDialog:
    """Tests for PlaylistDialog class."""

    def test_playlist_dialog_initialization(self) -> None:
        """Test PlaylistDialog initializes with playlist count."""
        dialog = PlaylistDialog(50)
        assert dialog.windowTitle() == "Playlist Dialog"
        assert hasattr(dialog, "playlistInput")

    def test_get_playlist_input_empty(self) -> None:
        """Test get_playlist_input returns empty string by default."""
        dialog = PlaylistDialog(10)
        assert dialog.get_playlist_input() == ""

    def test_get_playlist_input_with_text(self) -> None:
        """Test get_playlist_input returns entered text."""
        dialog = PlaylistDialog(10)
        dialog.playlistInput.setText("1,3,5-7")
        assert dialog.get_playlist_input() == "1,3,5-7"

    def test_drag_enter_event_with_urls(self) -> None:
        """Test dragEnterEvent accepts URLs."""
        dialog = PlaylistDialog(10)
        event = MagicMock(spec=QDragEnterEvent)
        event.mimeData.return_value.hasUrls.return_value = True

        dialog.dragEnterEvent(event)
        event.accept.assert_called_once()

    def test_drag_enter_event_without_urls(self) -> None:
        """Test dragEnterEvent ignores non-URL drops."""
        dialog = PlaylistDialog(10)
        event = MagicMock(spec=QDragEnterEvent)
        event.mimeData.return_value.hasUrls.return_value = False

        dialog.dragEnterEvent(event)
        event.ignore.assert_called_once()


class TestDropLabel:
    """Tests for DropLabel class."""

    def test_drop_label_initialization(self) -> None:
        """Test DropLabel initializes with text, color, and connection."""
        connection = MagicMock()
        label = DropLabel("Drop Files", "#FFFFFF", connection)

        assert label.originalText == "Drop Files"
        assert label.text() == "Drop Files"
        assert label.acceptDrops() is True

    def test_drop_label_drag_enter_with_urls(self) -> None:
        """Test DropLabel accepts drag enter for URLs."""
        connection = MagicMock()
        label = DropLabel("Drop", "#FFF", connection)
        event = MagicMock(spec=QDragEnterEvent)
        event.mimeData.return_value.hasUrls.return_value = True

        label.dragEnterEvent(event)
        event.accept.assert_called_once()

    def test_drop_label_drag_enter_without_urls(self) -> None:
        """Test DropLabel ignores drag enter for non-URLs."""
        connection = MagicMock()
        label = DropLabel("Drop", "#FFF", connection)
        event = MagicMock(spec=QDragEnterEvent)
        event.mimeData.return_value.hasUrls.return_value = False

        label.dragEnterEvent(event)
        event.ignore.assert_called_once()

    def test_drop_event_emits_signal(self) -> None:
        """Test dropEvent emits urls_dropped signal."""
        connection = MagicMock()
        label = DropLabel("Original", "#FFF", connection)
        captured = []
        label.urls_dropped.connect(lambda urls, text: captured.append((urls, text)))

        # Create mock URL objects
        url_mock = MagicMock()
        url_mock.toString.return_value = "https://example.com/video"

        event = MagicMock(spec=QDropEvent)
        event.mimeData.return_value.urls.return_value = [url_mock]

        label.dropEvent(event)

        # Verify signal was emitted with correct data
        assert captured == [(["https://example.com/video"], "Original")]

    def test_drop_event_changes_text_temporarily(self) -> None:
        """Test dropEvent changes text to ADDED_TEXT then reverts."""
        connection = MagicMock()
        label = DropLabel("Original", "#FFF", connection)
        mock_signal = MagicMock()
        label.urls_dropped.connect(mock_signal)

        url_mock = MagicMock()
        url_mock.toString.return_value = "https://example.com"

        event = MagicMock(spec=QDropEvent)
        event.mimeData.return_value.urls.return_value = [url_mock]

        label.dropEvent(event)

        # Text should be changed to ADDED_TEXT immediately
        assert label.text() == "Added!!!"
        # Timer should be set up
        assert label.timer.isSingleShot() is True


class TestPlaylistButton:
    """Tests for PlaylistButton class."""

    def test_playlist_button_initialization(self) -> None:
        """Test PlaylistButton initializes with text and path."""
        button = PlaylistButton("My Playlist", "/path/to/playlist.txt")
        assert button.text() == "My Playlist"
        assert button.playlist_path == Path("/path/to/playlist.txt")

    def test_playlist_button_mouse_press_non_right_click(self) -> None:
        """Test non-right-click mouse press uses default handling."""
        button = PlaylistButton("Playlist", "/path/to/file.txt")

        # Mock the parent class method
        with patch.object(button.__class__.__bases__[0], "mousePressEvent"):
            event = MagicMock(spec=QMouseEvent)
            event.button.return_value = Qt.MouseButton.LeftButton

            button.mousePressEvent(event)
            # Should call parent implementation for non-right-click

    @patch("UIClasses.startfile")
    def test_playlist_button_mouse_press_right_click_exists(
        self,
        mock_startfile: MagicMock,
    ) -> None:
        """Test right-click opens playlist file if it exists."""
        with patch("UIClasses.Path") as mock_path_class:
            mock_path = MagicMock()
            mock_path.exists.return_value = True
            mock_path_class.return_value = mock_path

            button = PlaylistButton("Playlist", "/path/to/file.txt")
            button.playlist_path = mock_path

            event = MagicMock(spec=QMouseEvent)
            event.button.return_value = Qt.MouseButton.RightButton

            button.mousePressEvent(event)

            mock_startfile.assert_called_once_with(mock_path)

    @patch("UIClasses.startfile")
    def test_playlist_button_mouse_press_right_click_not_exists(
        self,
        mock_startfile: MagicMock,
    ) -> None:
        """Test right-click does nothing if playlist file doesn't exist."""
        with patch("UIClasses.Path") as mock_path_class:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_path_class.return_value = mock_path

            button = PlaylistButton("Playlist", "/path/to/file.txt")
            button.playlist_path = mock_path

            event = MagicMock(spec=QMouseEvent)
            event.button.return_value = Qt.MouseButton.RightButton

            button.mousePressEvent(event)

            # startfile should not be called when file doesn't exist
            mock_startfile.assert_not_called()
