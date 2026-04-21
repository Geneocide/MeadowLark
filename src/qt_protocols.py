"""Structural protocols for yt-dlp integration objects."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class YdlLogger(Protocol):
    """Interface expected by yt-dlp for a logger object."""

    def debug(self, msg: str) -> None:
        """Log a debug message."""
        ...

    def warning(self, msg: str) -> None:
        """Log a warning message."""
        ...

    def error(self, msg: str) -> None:
        """Log an error message."""
        ...


class YdlProgressHook(Protocol):
    """Interface expected by yt-dlp for a progress hook callable."""

    def __call__(self, d: dict) -> None:
        """Receive a yt-dlp progress info dict."""
        ...
