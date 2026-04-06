"""Custom exception classes for the video downloader application."""


class VideoDownloaderError(Exception):
    """Base exception for all video downloader errors."""


class PodcastResolutionError(VideoDownloaderError):
    """Raised when unable to resolve a podcast entry (e.g., all videos are private)."""

    MSG = "Unable to resolve latest accessible entry"

    def __init__(self, message: str | None = None) -> None:
        """
        Initialize PodcastResolutionError with optional custom message.

        Args:
            message: Optional custom error message. Defaults to MSG if not provided.
        """
        super().__init__(message or self.MSG)


class PlaylistExtractionError(VideoDownloaderError):
    """Raised when unable to extract playlist information from a URL."""

    MSG = "Failed to extract playlist information"

    def __init__(
        self, message: str | None = None, original_exc: Exception | None = None
    ) -> None:
        """
        Initialize PlaylistExtractionError with optional message and original exception.

        Args:
            message: Optional custom error message. Defaults to MSG if not provided.
            original_exc: Optional original exception that caused this error.
        """
        self.original_exc = original_exc
        super().__init__(message or self.MSG)
