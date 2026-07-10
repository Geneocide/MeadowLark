"""Download execution logic extracted from QYTQueue for testability and reusability."""

from collections.abc import Callable

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError, MaxDownloadsReached

import utils

from .config import YDL_EXTRACTION_ERRORS
from .path_utils import rename_playlist_folders_from_comments
from .settings_dialog import get_setting
from .ydl_options import _build_video_format_selector
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

    def _run_download(self, opts: dict, urls: list) -> None:
        """
        Run a yt-dlp download.

        Note: we deliberately do NOT wipe ``ydl.cache`` here. Recent yt-dlp
        caches the YouTube JS-challenge solver library (and player data) under
        ~/.cache/yt-dlp; blanket-clearing it every run forced a fresh GitHub
        fetch of the solver on each download, turning a transient upstream blip
        (e.g. HTTP 504) into a hard "Requested format is not available" failure.
        yt-dlp keys its cache by player URL/version and self-invalidates.
        """
        with YoutubeDL(opts) as ydl:
            ydl.download(urls)

    def _extract_title(self, urls: list, options: dict | None = None) -> str:
        """
        Extract video title from first URL for error logging.

        Args:
            urls: List of URLs to extract from.
            options: Optional yt-dlp options from the download context.
                     ``cookiefile`` is forwarded so age-restricted lookups succeed.

        Returns:
            Video title or '(unknown)' if extraction fails.
        """
        if not urls:
            return "(unknown)"

        title = urls[0]
        extra_opts: dict | None = None
        if options and (cookiefile := options.get("cookiefile")):
            extra_opts = {"cookiefile": cookiefile}
        try:
            info = extract_playlist_info(urls[0], ydl_class=YoutubeDL, extra_opts=extra_opts)
            title = info.get("title", title)
        except YDL_EXTRACTION_ERRORS as exc:
            utils.log_exception(exc, "Failed to extract title for error logging")
        return title

    def _try_fallback(
        self,
        urls: list,
        options: dict,
        tried_flag: str,
        trigger_phrase: str | tuple[str, ...],
        error_str: str,
        message: str,
        options_modifier: Callable[[dict], dict],
        log_context: str,
    ) -> tuple[bool, str]:
        """Attempt a generic fallback download if a trigger phrase is present and not yet tried."""
        phrases = (trigger_phrase,) if isinstance(trigger_phrase, str) else trigger_phrase
        if not any(phrase in error_str for phrase in phrases) or options.get(tried_flag):
            return False, error_str
        self._emit_message(message)
        fallback = options_modifier(options)
        fallback[tried_flag] = True
        try:
            self._run_download(fallback, urls)
            return True, error_str
        except YDL_EXTRACTION_ERRORS as e2:
            utils.log_exception(e2, log_context)
            return False, str(e2)

    def _try_720_fallback(
        self,
        urls: list,
        options: dict,
        title: str,
        site: str,
        error_str: str,
    ) -> tuple[bool, str]:
        """Try downloading at 720p if 1080p format unavailable."""

        def _modify(opts: dict) -> dict:
            vfmt = str(get_setting("VID_DL_VIDEO_FORMAT") or "mp4")
            fallback = opts.copy()
            fallback["format"] = _build_video_format_selector(720, vfmt)
            fallback.setdefault("merge_output_format", vfmt)
            pps = list(fallback.get("postprocessors") or [])
            if not any(pp.get("key") == "FFmpegVideoRemuxer" for pp in pps):
                pps.append({"key": "FFmpegVideoRemuxer", "preferedformat": vfmt})
            fallback["postprocessors"] = pps
            fq = dict(fallback.get("qmeta", {}))
            fq["type"] = "720"
            fallback["qmeta"] = fq
            return fallback

        return self._try_fallback(
            urls=urls,
            options=options,
            tried_flag="_tried_720_fallback",
            # 403 / "unable to download video data": YouTube gated the selected
            # 1080 media URL (e.g. SABR/PO-token experiment, #12482). A lower
            # rung often resolves to a still-servable format on the tv client.
            trigger_phrase=(
                "Requested format is not available",
                "unable to download video data",
                "HTTP Error 403",
            ),
            error_str=error_str,
            message=f"1080 format unavailable or blocked for '{title}'; retrying at 720...",
            options_modifier=_modify,
            log_context="720p fallback attempt failed",
        )

    def _try_without_sponsorblock(
        self,
        urls: list,
        options: dict,
        title: str,
        site: str,
        dtype: str,
        error_str: str,
    ) -> tuple[bool, str]:
        """Try downloading without SponsorBlock if API unavailable."""
        return self._try_fallback(
            urls=urls,
            options=options,
            tried_flag="_tried_without_sponsorblock",
            trigger_phrase="Unable to communicate with SponsorBlock API",
            error_str=error_str,
            message="SponsorBlock API unavailable; retrying download without SponsorBlock...",
            options_modifier=utils.remove_sponsorblock_postprocessor,
            log_context="SponsorBlock removal retry failed",
        )

    def _extract_base_output_dir(self, options: dict) -> str | None:
        """Extract the base output directory from the outtmpl option, or None if not determinable."""
        outtmpl = options.get("outtmpl", "")
        outtmpl_str: str | None = None

        if isinstance(outtmpl, str):
            outtmpl_str = outtmpl
        elif isinstance(outtmpl, dict):
            outtmpl_str = outtmpl.get("default")
            if not isinstance(outtmpl_str, str) or not outtmpl_str:
                for value in outtmpl.values():
                    if isinstance(value, str) and value:
                        outtmpl_str = value
                        break

        if not outtmpl_str:
            return None

        # outtmpl is like "E:/vid storage/%(playlist)s/..." — take all but last segment
        parts = outtmpl_str.split("/")
        return "/".join(parts[:-1]) or None if len(parts) >= 2 else None

    def _rename_na_folder_if_needed(self, options: dict, urls: list) -> None:
        """Rename 'NA' playlist folders using comment metadata after a successful download."""
        meta = options.get("qmeta") or {}
        playlist_comments = meta.get("playlist_comments")
        if not playlist_comments:
            return
        base_output_dir = self._extract_base_output_dir(options)
        if not base_output_dir:
            return
        rename_playlist_folders_from_comments(
            base_output_dir,
            urls,
            playlist_comments,
            direct_playlist_id=meta.get("playlist_id"),
        )

    def execute(self, urls: list, options: dict) -> tuple[bool, str]:
        """
        Execute download with fallback strategies.

        Attempts fallbacks for 720p (if 1080p unavailable) and without
        SponsorBlock (if API down) before reporting final failure.

        Returns (success: bool, error_message: str).
        """
        try:
            self._run_download(options, urls)
            self._rename_na_folder_if_needed(options, urls)
        except (
            DownloadError,
            ExtractorError,
            MaxDownloadsReached,
            OSError,
            ValueError,
        ) as e:
            title = self._extract_title(urls, options)
            error_str = str(e)
            meta = options.get("qmeta") or {}
            site = meta.get("site", "unknown")
            dtype = meta.get("type", meta.get("source", "unknown"))

            if dtype == "1080":
                success, error_str = self._try_720_fallback(
                    urls, options, title, site, error_str
                )
                if success:
                    return True, ""

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

            return (
                False,
                f"Error downloading '{title}' (site: {site}, type: {dtype}): {e!s}",
            )
        else:
            return True, ""
