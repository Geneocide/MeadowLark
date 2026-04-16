"""Download execution logic extracted from QYTQueue for testability and reusability."""

from collections.abc import Callable

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError, MaxDownloadsReached

import utils

from .config import YDL_EXTRACTION_ERRORS
from .path_utils import rename_playlist_folders_from_comments
from .ydl_utils import extract_playlist_info

YoutubeDL = yt_dlp.YoutubeDL


class DownloadExecutor:
    """
    Manages download execution with fallback strategies.

    Encapsulates download logic including title extraction, format fallbacks,
    and error recovery. Designed for testability with dependency injection.
    """

    def __init__(
        self,
        message_callback: Callable[[str], None] | None = None,
    ) -> None:
        """
        Initialize the download executor.

        Args:
            message_callback: Optional callback for emitting status messages.
                             Called with string messages during execution.
        """
        self.message_callback = message_callback or (lambda _: None)

    def _emit_message(self, message: str) -> None:
        """Emit a status message via callback."""
        self.message_callback(message)

    def _extract_title(self, urls: list) -> str:
        """
        Extract video title from first URL for error logging.

        Args:
            urls: List of URLs to extract from.

        Returns:
            Video title or '(unknown)' if extraction fails.
        """
        if not urls:
            return "(unknown)"

        title = urls[0]
        try:
            info = extract_playlist_info(urls[0], ydl_class=YoutubeDL)
            title = info.get("title", title)
        except YDL_EXTRACTION_ERRORS as exc:
            utils.log_exception(exc, "Failed to extract title for error logging")
        return title

    def _try_720_fallback(
        self,
        urls: list,
        options: dict,
        title: str,
        site: str,
        error_str: str,
    ) -> tuple[bool, str]:
        """
        Try downloading at 720p if 1080p format unavailable.

        Args:
            urls: URLs to download.
            options: yt-dlp options.
            title: Video title for logging.
            site: Source site for logging.
            error_str: Error message text.

        Returns:
            (success: bool, new_error_str: str)
        """
        if "Requested format is not available" not in error_str or options.get(
            "_tried_720_fallback",
        ):
            return False, error_str

        self._emit_message(
            f"Requested 1080 format not available for '{title}'; retrying at 720...",
        )
        fallback = options.copy()
        fallback["_tried_720_fallback"] = True
        fallback["format"] = (
            "bestvideo*[height=720][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo*[height=720]+bestaudio/"
            "best[height=720]/best"
        )
        fallback.setdefault("merge_output_format", "mp4")
        fq = dict(fallback.get("qmeta", {}))
        fq["type"] = "720"
        fallback["qmeta"] = fq
        try:
            with YoutubeDL(fallback) as ydl:
                ydl.cache.remove()
                ydl.download(urls)
            return True, error_str  # noqa: TRY300
        except YDL_EXTRACTION_ERRORS as e2:
            utils.log_exception(e2, "720p fallback attempt failed")
            return False, str(e2)

    def _try_without_sponsorblock(  # noqa: PLR0913
        self,
        urls: list,
        options: dict,
        title: str,
        site: str,
        dtype: str,
        error_str: str,
    ) -> tuple[bool, str]:
        """
        Try downloading without SponsorBlock if API unavailable.

        Args:
            urls: URLs to download.
            options: yt-dlp options.
            title: Video title for logging.
            site: Source site for logging.
            dtype: Download type for logging.
            error_str: Error message text.

        Returns:
            (success: bool, new_error_str: str)
        """
        if (
            "Unable to communicate with SponsorBlock API" not in error_str
            or options.get("_tried_without_sponsorblock")
        ):
            return False, error_str

        self._emit_message(
            "SponsorBlock API unavailable; retrying download without SponsorBlock...",
        )
        fallback = utils.remove_sponsorblock_postprocessor(options)
        fallback["_tried_without_sponsorblock"] = True
        try:
            with YoutubeDL(fallback) as ydl:
                ydl.cache.remove()
                ydl.download(urls)
            return True, error_str  # noqa: TRY300
        except YDL_EXTRACTION_ERRORS as e2:
            utils.log_exception(e2, "SponsorBlock removal retry failed")
            return False, str(e2)

    def execute(self, urls: list, options: dict) -> tuple[bool, str]:
        """
        Execute download with fallback strategies.

        Attempts fallbacks for 720p (if 1080p unavailable) and without
        SponsorBlock (if API down) before reporting final failure.

        Args:
            urls: List of URLs to download.
            options: yt-dlp options, including logger and progress_hooks.

        Returns:
            (success: bool, error_message: str)
            - If success is True, error_message is empty
            - If success is False, error_message contains the error details
        """
        try:
            with YoutubeDL(options) as ydl:
                ydl.cache.remove()
                ydl.download(urls)

            # After successful download, try to rename 'NA' folders using comments
            meta = options.get("qmeta") or {}
            playlist_comments = meta.get("playlist_comments")
            if playlist_comments:
                # Extract base output directory from outtmpl
                # outtmpl can be a string or dict (yt-dlp supports both)
                outtmpl = options.get("outtmpl", "")
                outtmpl_str = None

                if isinstance(outtmpl, str):
                    outtmpl_str = outtmpl
                elif isinstance(outtmpl, dict):
                    # Try to extract a string path from dict
                    # Prefer 'default' key, then any string value
                    outtmpl_str = outtmpl.get("default")
                    if not isinstance(outtmpl_str, str):
                        for key, value in outtmpl.items():
                            if isinstance(value, str):
                                outtmpl_str = value
                                break

                if outtmpl_str:
                    # outtmpl is like "E:/vid storage/%(playlist)s/..."
                    # Extract the base directory (first part before %(...)s)
                    parts = outtmpl_str.split("/")
                    if len(parts) >= 2:
                        base_output_dir = "/".join(parts[:-1])
                        rename_playlist_folders_from_comments(
                            base_output_dir,
                            urls,
                            playlist_comments,
                        )

            return True, ""
        except (
            DownloadError,
            ExtractorError,
            MaxDownloadsReached,
            OSError,
            ValueError,
        ) as e:
            # Extract title for error logging
            title = self._extract_title(urls)
            error_str = str(e)
            meta = options.get("qmeta") or {}
            site = meta.get("site", "unknown")
            dtype = meta.get("type", meta.get("source", "unknown"))

            # Try 720p fallback if 1080p not available
            if dtype == "1080":
                success, error_str = self._try_720_fallback(
                    urls,
                    options,
                    title,
                    site,
                    error_str,
                )
                if success:
                    return True, ""

            # Try without SponsorBlock if API is down
            success, error_str = self._try_without_sponsorblock(
                urls,
                options,
                title,
                site,
                dtype,
                error_str,
            )
            if success:
                return True, ""

            # All retries failed
            error_message = (
                f"Error downloading '{title}' (site: {site}, type: {dtype}): {e!s}"
            )
            return False, error_message
