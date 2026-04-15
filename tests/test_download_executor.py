"""Tests for download executor logic with mocked yt-dlp calls."""

from unittest.mock import MagicMock, Mock, patch

from yt_dlp.utils import DownloadError, ExtractorError

from src.download_executor import DownloadExecutor


class TestDownloadExecutorInitialization:
    """Tests for DownloadExecutor initialization."""

    def test_initialization_with_callback(self) -> None:
        """Test executor initializes with message callback."""
        callback = Mock()
        executor = DownloadExecutor(message_callback=callback)
        assert executor.message_callback == callback

    def test_initialization_without_callback(self) -> None:
        """Test executor initializes with default no-op callback."""
        executor = DownloadExecutor()
        # Should not raise when called
        executor._emit_message("test")


class TestExtractTitle:
    """Tests for title extraction from URLs."""

    def test_extract_title_empty_urls(self) -> None:
        """Test extraction with empty URL list returns unknown."""
        executor = DownloadExecutor()
        title = executor._extract_title([])
        assert title == "(unknown)"

    @patch("src.download_executor.YoutubeDL")
    def test_extract_title_success(self, mock_ydl_class: Mock) -> None:
        """Test successful title extraction from first URL."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {
            "title": "Test Video Title",
        }
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        title = executor._extract_title(["https://example.com/video"])
        assert title == "Test Video Title"

    @patch("src.download_executor.YoutubeDL")
    def test_extract_title_fallback_to_url(self, mock_ydl_class: Mock) -> None:
        """Test title extraction falls back to URL if title not found."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {}
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        url = "https://example.com/video"
        title = executor._extract_title([url])
        assert title == url

    @patch("src.download_executor.YoutubeDL")
    def test_extract_title_handles_download_error(self, mock_ydl_class: Mock) -> None:
        """Test title extraction handles DownloadError gracefully."""
        mock_ydl_class.return_value.__enter__.side_effect = DownloadError(
            "Invalid URL",
        )

        executor = DownloadExecutor()
        title = executor._extract_title(["https://example.com/invalid"])
        assert title == "https://example.com/invalid"


class TestTry720Fallback:
    """Tests for 720p fallback strategy."""

    def test_no_fallback_if_error_not_format_related(self) -> None:
        """Test no fallback if error is not format-related."""
        executor = DownloadExecutor()
        options = {}
        success, error = executor._try_720_fallback(
            ["url"],
            options,
            "title",
            "youtube",
            "Some other error",
        )
        assert success is False
        assert error == "Some other error"

    def test_no_fallback_if_already_tried(self) -> None:
        """Test no fallback if already attempted 720p."""
        executor = DownloadExecutor()
        options = {"_tried_720_fallback": True}
        success, error = executor._try_720_fallback(
            ["url"],
            options,
            "title",
            "youtube",
            "Requested format is not available",
        )
        assert success is False

    @patch("src.download_executor.YoutubeDL")
    def test_720_fallback_success(self, mock_ydl_class: Mock) -> None:
        """Test successful 720p fallback."""
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        callback = Mock()

        executor = DownloadExecutor(message_callback=callback)
        options = {
            "qmeta": {"site": "youtube", "type": "1080"},
        }
        success, error = executor._try_720_fallback(
            ["https://youtube.com/watch?v=test"],
            options,
            "Test Video",
            "youtube",
            "Requested format is not available",
        )
        assert success is True
        assert error == "Requested format is not available"
        # Verify message was emitted
        callback.assert_called_once()
        assert "720" in callback.call_args[0][0]

    @patch("src.download_executor.YoutubeDL")
    def test_720_fallback_failure(self, mock_ydl_class: Mock) -> None:
        """Test 720p fallback failure with error message."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.download.side_effect = DownloadError("720p not available")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        options = {}
        success, error = executor._try_720_fallback(
            ["url"],
            options,
            "title",
            "youtube",
            "Requested format is not available",
        )
        assert success is False
        assert "720p not available" in error


class TestTryWithoutSponsorblock:
    """Tests for SponsorBlock fallback strategy."""

    def test_no_fallback_if_error_not_sponsorblock_related(self) -> None:
        """Test no fallback if error is not SponsorBlock-related."""
        executor = DownloadExecutor()
        options = {}
        success, error = executor._try_without_sponsorblock(
            ["url"],
            options,
            "title",
            "youtube",
            "audio",
            "Some other error",
        )
        assert success is False

    def test_no_fallback_if_already_tried(self) -> None:
        """Test no fallback if already attempted without SponsorBlock."""
        executor = DownloadExecutor()
        options = {"_tried_without_sponsorblock": True}
        success, error = executor._try_without_sponsorblock(
            ["url"],
            options,
            "title",
            "youtube",
            "audio",
            "Unable to communicate with SponsorBlock API",
        )
        assert success is False

    @patch("src.download_executor.utils.remove_sponsorblock_postprocessor")
    @patch("src.download_executor.YoutubeDL")
    def test_sponsorblock_fallback_success(
        self,
        mock_ydl_class: Mock,
        mock_remove_sb: Mock,
    ) -> None:
        """Test successful SponsorBlock removal fallback."""
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_remove_sb.return_value = {"modified": True}
        callback = Mock()

        executor = DownloadExecutor(message_callback=callback)
        options = {}
        success, error = executor._try_without_sponsorblock(
            ["url"],
            options,
            "title",
            "youtube",
            "audio",
            "Unable to communicate with SponsorBlock API",
        )
        assert success is True
        callback.assert_called_once()
        assert "SponsorBlock" in callback.call_args[0][0]

    @patch("src.download_executor.utils.remove_sponsorblock_postprocessor")
    @patch("src.download_executor.YoutubeDL")
    def test_sponsorblock_fallback_failure(
        self,
        mock_ydl_class: Mock,
        mock_remove_sb: Mock,
    ) -> None:
        """Test SponsorBlock removal fallback failure."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.download.side_effect = DownloadError("Download failed")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance
        mock_remove_sb.return_value = {}

        executor = DownloadExecutor()
        options = {}
        success, error = executor._try_without_sponsorblock(
            ["url"],
            options,
            "title",
            "youtube",
            "audio",
            "Unable to communicate with SponsorBlock API",
        )
        assert success is False
        assert "Download failed" in error


class TestExecute:
    """Tests for main execute() method with fallback chain."""

    @patch("src.download_executor.YoutubeDL")
    def test_execute_success_first_try(self, mock_ydl_class: Mock) -> None:
        """Test successful download on first attempt."""
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        success, error = executor.execute(["url"], {"test": True})
        assert success is True
        assert error == ""

    @patch("src.download_executor.YoutubeDL")
    def test_execute_1080_format_not_available_falls_back_to_720(
        self,
        mock_ydl_class: Mock,
    ) -> None:
        """Test 1080p download failure triggers 720p fallback."""
        # First call (main): raises format error
        # Second call (720p fallback): succeeds
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        call_count = 0

        def side_effect(*args, **kwargs):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DownloadError("Requested format is not available [1080]")
            # Second call succeeds

        mock_ydl_instance.download.side_effect = side_effect

        executor = DownloadExecutor()
        options = {
            "qmeta": {"type": "1080", "site": "youtube"},
        }
        success, error = executor.execute(["url"], options)
        assert success is True
        assert error == ""

    @patch("src.download_executor.YoutubeDL")
    def test_execute_sponsorblock_api_error_falls_back(
        self,
        mock_ydl_class: Mock,
    ) -> None:
        """Test SponsorBlock API error triggers fallback."""
        mock_ydl_instance = MagicMock()

        call_count = 0

        def side_effect(*args, **kwargs):  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise DownloadError("Unable to communicate with SponsorBlock API")
            # Second call (without SponsorBlock) succeeds

        mock_ydl_instance.download.side_effect = side_effect
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        with patch("src.download_executor.utils.remove_sponsorblock_postprocessor"):
            executor = DownloadExecutor()
            options = {
                "qmeta": {"type": "audio", "site": "youtube"},
                "postprocessors": [{"key": "SponsorBlock"}],
            }
            success, error = executor.execute(["url"], options)
            assert success is True
            assert error == ""

    @patch("src.download_executor.YoutubeDL")
    def test_execute_all_fallbacks_fail(self, mock_ydl_class: Mock) -> None:
        """Test failure when all fallbacks are exhausted."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.download.side_effect = DownloadError("Permanent failure")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        success, error = executor.execute(["url"], {"test": True})
        assert success is False
        assert "Permanent failure" in error
        assert "site: unknown" in error

    @patch("src.download_executor.YoutubeDL")
    def test_execute_preserves_metadata(self, mock_ydl_class: Mock) -> None:
        """Test execute preserves site and type metadata in errors."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.download.side_effect = DownloadError("Test error")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        options = {
            "qmeta": {"site": "nebula", "type": "720"},
        }
        success, error = executor.execute(["url"], options)
        assert success is False
        assert "site: nebula" in error
        assert "type: 720" in error

    def test_execute_with_message_callback(self) -> None:
        """Test execute emits messages via callback."""
        callback = Mock()
        executor = DownloadExecutor(message_callback=callback)

        with patch("src.download_executor.YoutubeDL") as mock_ydl_class:
            mock_ydl_instance = MagicMock()
            mock_ydl_instance.download.side_effect = DownloadError(
                "Requested format is not available",
            )
            mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

            options = {
                "qmeta": {"type": "1080", "site": "youtube"},
                "title": "Test",
            }
            executor.execute(["url"], options)

            # Should have emitted 720p fallback message
            assert any("720" in str(call) for call in callback.call_args_list)


class TestExecuteEdgeCases:
    """Tests for edge cases in download execution."""

    @patch("src.download_executor.YoutubeDL")
    def test_execute_extractor_error(self, mock_ydl_class: Mock) -> None:
        """Test handling of ExtractorError exceptions."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.download.side_effect = ExtractorError("Extractor failed")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        success, error = executor.execute(["url"], {"test": True})
        assert success is False
        assert "Extractor failed" in error

    @patch("src.download_executor.YoutubeDL")
    def test_execute_os_error(self, mock_ydl_class: Mock) -> None:
        """Test handling of OSError exceptions."""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.download.side_effect = OSError("Disk full")
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        success, error = executor.execute(["url"], {"test": True})
        assert success is False
        assert "Disk full" in error

    @patch("src.download_executor.YoutubeDL")
    def test_execute_with_empty_options(self, mock_ydl_class: Mock) -> None:
        """Test execute with minimal options."""
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        success, error = executor.execute(["url"], {})
        assert success is True
        assert error == ""

    @patch("src.download_executor.YoutubeDL")
    def test_execute_cache_cleared_on_each_attempt(
        self,
        mock_ydl_class: Mock,
    ) -> None:
        """Test yt-dlp cache is cleared before each download attempt."""
        mock_ydl_instance = MagicMock()
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        executor = DownloadExecutor()
        executor.execute(["url"], {"test": True})

        # Verify cache.remove() was called
        mock_ydl_instance.cache.remove.assert_called()
