"""Unit tests for QYT module classes and functionality."""
# ruff: noqa: S101,SLF001

from pathlib import Path
from queue import Queue
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QObject

from QYT import HistoryHook, HistoryLogger, QHook, QLogger, QYTQueue


class TestQLogger:
    """Tests for QLogger class."""

    def test_qlogger_initialization(self) -> None:
        """Test QLogger initializes with a download queue."""
        queue = Queue()
        logger = QLogger(queue)
        assert logger.downloadQueue is queue
        assert logger.daemon is True
        assert hasattr(logger, "message_changed")

    def test_qlogger_debug(self) -> None:
        """Test debug messages are emitted (except ETA and iB/s)."""
        queue = Queue()
        logger = QLogger(queue)

        mock_signal = MagicMock()
        logger.message_changed.connect(mock_signal)

        logger.debug("Normal message")
        mock_signal.assert_called_with("Normal message")

        mock_signal.reset_mock()
        logger.debug("Message with ETA time")
        mock_signal.assert_not_called()

        mock_signal.reset_mock()
        logger.debug("Download speed: 100 iB/s")
        mock_signal.assert_not_called()

    def test_qlogger_warning(self) -> None:
        """Test warning messages are emitted."""
        queue = Queue()
        logger = QLogger(queue)
        mock_signal = MagicMock()
        logger.message_changed.connect(mock_signal)

        logger.warning("Warning message")
        mock_signal.assert_called_with("Warning message")

    def test_qlogger_error(self) -> None:
        """Test error messages are emitted."""
        queue = Queue()
        logger = QLogger(queue)
        mock_signal = MagicMock()
        logger.message_changed.connect(mock_signal)

        logger.error("Error message")
        mock_signal.assert_called_with("Error message")


class TestQHook:
    """Tests for QHook class."""

    def test_qhook_initialization(self) -> None:
        """Test QHook initializes as a QObject."""
        hook = QHook()
        assert isinstance(hook, QObject)
        assert hasattr(hook, "info_changed")

    def test_qhook_call(self) -> None:
        """Test QHook emits info_changed signal with copied dict."""
        hook = QHook()
        mock_signal = MagicMock()
        hook.info_changed.connect(mock_signal)

        test_dict = {"id": "123", "title": "Test Video"}
        hook(test_dict)

        # Verify emit was called with a dict containing the same data
        mock_signal.assert_called_once()
        emitted_dict = mock_signal.call_args[0][0]
        assert emitted_dict == test_dict
        # Verify it's a copy, not the same object
        assert emitted_dict is not test_dict


class TestHistoryLogger:
    """Tests for HistoryLogger class."""

    def test_history_logger_path(self) -> None:
        """Test HistoryLogger has correct file path."""
        assert Path("history_log.txt") == HistoryLogger.HISTORY_PATH

    def test_format_entry(self) -> None:
        """Test HistoryLogger._format_entry formatting."""
        result = HistoryLogger._format_entry(
            "2026-03-24 10:30:45",
            "youtube",
            "1080",
            "Test Video",
            "SUCCESS",
        )
        assert "[2026-03-24 10:30:45]" in result
        assert "Site: youtube" in result
        assert "Type: 1080" in result
        assert "Title: Test Video" in result
        assert "Result: SUCCESS" in result
        assert result.endswith("\n")

    def test_format_entry_failure(self) -> None:
        """Test HistoryLogger._format_entry with failure."""
        result = HistoryLogger._format_entry(
            "2026-03-24 10:30:45",
            "nebula",
            "podcast",
            "Episode 1",
            "FAIL",
        )
        assert "Result: FAIL" in result

    def test_format_entry_skipped(self) -> None:
        """Test HistoryLogger._format_entry with skipped result."""
        result = HistoryLogger._format_entry(
            "2026-03-24 10:30:45",
            "youtube",
            "audio_playlists",
            "Short Episode",
            "SKIPPED (Short duration (<3 min))",
        )
        assert "Result: SKIPPED (Short duration (<3 min))" in result

    @patch("QYT.HistoryLogger.HISTORY_PATH")
    def test_log_success(self, mock_path: MagicMock) -> None:
        """Test HistoryLogger.log writes success entry."""
        mock_file = MagicMock()
        mock_path.parent.mkdir = MagicMock()
        mock_path.open = MagicMock(return_value=mock_file.__enter__.return_value)
        mock_path.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_path.open.return_value.__exit__ = MagicMock(return_value=None)

        HistoryLogger.log("youtube", "1080", "Test Video", success=True)

        # Verify write was called
        mock_file.write.assert_called_once()
        written_content = mock_file.write.call_args[0][0]
        assert "SUCCESS" in written_content

    @patch("QYT.HistoryLogger.HISTORY_PATH")
    def test_log_skip(self, mock_path: MagicMock) -> None:
        """Test HistoryLogger.log_skip writes skip entry."""
        mock_file = MagicMock()
        mock_path.parent.mkdir = MagicMock()
        mock_path.open = MagicMock(return_value=mock_file.__enter__.return_value)
        mock_path.open.return_value.__enter__ = MagicMock(return_value=mock_file)
        mock_path.open.return_value.__exit__ = MagicMock(return_value=None)

        HistoryLogger.log_skip(
            "youtube",
            "audio_playlists",
            "Short Episode",
            "Short duration (<3 min)",
        )

        # Verify write was called
        mock_file.write.assert_called_once()
        written_content = mock_file.write.call_args[0][0]
        assert "SKIPPED (Short duration (<3 min))" in written_content


class TestHistoryHook:
    """Tests for HistoryHook class."""

    def test_history_hook_initialization(self) -> None:
        """Test HistoryHook initializes with metadata."""
        meta = {"site": "youtube", "type": "1080"}
        hook = HistoryHook(meta)
        assert hook.meta == meta
        assert hook._seen_ids == set()

    def test_history_hook_initialization_none(self) -> None:
        """Test HistoryHook with None metadata."""
        hook = HistoryHook(None)
        assert hook.meta == {}
        assert hook._seen_ids == set()

    def test_history_hook_vid_id(self) -> None:
        """Test HistoryHook._vid_id extraction."""
        hook = HistoryHook(None)

        # Test with id field
        assert hook._vid_id({"id": "abc123"}) == "abc123"

        # Test with fallback to _filename
        assert hook._vid_id({"_filename": "video.mp4"}) == "video.mp4"

        # Test with fallback to url
        assert hook._vid_id({"url": "https://example.com"}) == "https://example.com"

        # Test with no id fields
        assert hook._vid_id({}) == "unknown"

    def test_history_hook_infer_site(self) -> None:
        """Test HistoryHook._infer_site detection."""
        hook = HistoryHook({"site": "youtube"})
        assert hook._infer_site({}) == "youtube"

        hook_unknown = HistoryHook(None)
        assert hook_unknown._infer_site({"extractor_key": "youtube"}) == "youtube"
        assert hook_unknown._infer_site({"extractor": "nebula"}) == "nebula"
        assert hook_unknown._infer_site({}) == "unknown"

    @patch("QYT.HistoryLogger.log")
    def test_history_hook_call_finished(self, mock_log: MagicMock) -> None:
        """Test HistoryHook.__call__ logs on 'finished' status."""
        meta = {"site": "youtube", "type": "1080"}
        hook = HistoryHook(meta)

        event = {
            "status": "finished",
            "info_dict": {"id": "123", "title": "Test Video"},
        }
        hook(event)

        # Verify logging occurred
        mock_log.assert_called_once()
        args = mock_log.call_args
        assert args[1]["success"] is True

    @patch("QYT.HistoryLogger.log")
    def test_history_hook_call_deduplication(
        self,
        mock_log: MagicMock,
    ) -> None:
        """Test HistoryHook deduplicates by video ID."""
        meta = {"site": "youtube", "type": "1080"}
        hook = HistoryHook(meta)

        event = {
            "status": "finished",
            "info_dict": {"id": "123", "title": "Test Video"},
        }

        hook(event)
        hook(event)  # Call again with same id

        # Should only log once
        assert mock_log.call_count == 1


class TestQYTQueue:
    """Tests for QYTQueue class."""

    def test_qytqueue_initialization(self) -> None:
        """Test QYTQueue initializes as a QThread."""
        queue = Queue()
        ydl_queue = QYTQueue(queue)
        assert ydl_queue.downloadQueue is queue
        assert ydl_queue.daemon is True
        assert hasattr(ydl_queue, "message_changed")
        assert hasattr(ydl_queue, "queue_empty")

    def test_extract_title_from_urls(self) -> None:
        """Test _extract_title returns URL if extraction fails."""
        queue = Queue()
        ydl_queue = QYTQueue(queue)

        # With empty list
        assert ydl_queue._extract_title([]) == "(unknown)"

        # With URL
        urls = ["https://youtube.com/watch?v=test"]
        # This will fail silently since YoutubeDL is not mocked
        title = ydl_queue._extract_title(urls)
        assert isinstance(title, str)
        # If extraction failed, should have returned URL or unknown
        assert title in (urls[0], "(unknown)")

    def test_try_720_fallback_conditions(self) -> None:
        """Test _try_720_fallback early exit conditions."""
        queue = Queue()
        ydl_queue = QYTQueue(queue)

        options = {}
        # Should return False if error_str doesn't indicate format unavailable
        success, error = ydl_queue._try_720_fallback(
            ["url"],
            options,
            "title",
            "youtube",
            "Some other error",
        )
        assert success is False
        assert error == "Some other error"

        # Should return False if already tried 720 fallback
        options = {"_tried_720_fallback": True}
        success, error = ydl_queue._try_720_fallback(
            ["url"],
            options,
            "title",
            "youtube",
            "Requested format is not available",
        )
        assert success is False

    def test_try_without_sponsorblock_conditions(self) -> None:
        """Test _try_without_sponsorblock early exit conditions."""
        queue = Queue()
        ydl_queue = QYTQueue(queue)

        options = {}
        # Should return False if error doesn't mention SponsorBlock API
        success, error = ydl_queue._try_without_sponsorblock(
            ["url"],
            options,
            "title",
            "youtube",
            "1080",
            "Some other error",
        )
        assert success is False
        assert error == "Some other error"

        # Should return False if already tried without sponsorblock
        options = {"_tried_without_sponsorblock": True}
        success, error = ydl_queue._try_without_sponsorblock(
            ["url"],
            options,
            "title",
            "youtube",
            "1080",
            "Unable to communicate with SponsorBlock API",
        )
        assert success is False
