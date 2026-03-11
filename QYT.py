"""Provides PyQt-based classes for logging, progress signaling, and threaded download queue management using yt-dlp. Includes QLogger for emitting log messages, QHook for progress updates, and QYTQueue for managing and executing download tasks in a background thread with wake lock support."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from wakepy import keep
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError, MaxDownloadsReached

import utils

# Migrate prior logfile name to the new error log if present
try:
    if Path("logfile.txt").exists() and not Path("error_log.txt").exists():
        Path.replace("logfile.txt", "error_log.txt")
except Exception:
    # Never fail on migration
    pass

logging.basicConfig(
    filename="error_log.txt",
    level=logging.ERROR,
    format="%(asctime)s %(message)s",
)


class QLogger(QObject):
    """
    A PyQt-based logger class that emits log messages via the messageChanged signal.

    Integrates with a download queue and provides debug, warning, and error methods,
    emitting messages to connected slots, with filtering for debug messages containing 'ETA' or 'iB/s'.
    """

    message_changed = pyqtSignal(str)

    def __init__(self, download_queue: Queue) -> None:
        """
        Initialize the thread with a download queue and set it as a daemon thread.

        Args:
            download_queue (Queue): The queue containing download tasks.
        """
        super().__init__()
        self.downloadQueue = download_queue
        self.daemon = True

    def debug(self, msg: str) -> None:
        """Log a debug message using the module logger and emits the message via the message_changed signal, unless the message contains 'ETA' or 'iB/s'."""
        logger = logging.getLogger(__name__)
        logger.debug(msg)
        if "ETA" not in msg and "iB/s" not in msg:
            self.message_changed.emit(msg)

    def warning(self, msg: str) -> None:
        """
        Log a warning message using the module logger and emits the message via the message_changed signal.

        Args:
            msg (str): The warning message to log and emit.
        """
        logger = logging.getLogger(__name__)
        logger.warning(msg)
        self.message_changed.emit(msg)

    def error(self, msg: str) -> None:
        """
        Log an error message using the module logger and emits the message via the message_changed signal.

        Args:
            msg (str): The error message to log and emit.
        """
        logger = logging.getLogger(__name__)
        logger.error(msg)
        self.message_changed.emit(msg)

    def exception(self, msg: str) -> None:
        """
        Log an exception message using the module logger and emits the message via the message_changed signal.

        Args:
            msg (str): The exception message to log and emit.
        """
        logger = logging.getLogger(__name__)
        logger.exception(msg)
        self.message_changed.emit(msg)

    # def download(self, urls, options):
    #     with YoutubeDL(options) as ydl:
    #         ydl.cache.remove()
    #         try:
    #             ydl.download(urls)
    #         except Exception as e:
    #             return f"An error occurred during the download: {str(e)}"
    #     for hook in options.get("progress_hooks", []):
    #         if hasattr(hook, "deleteLater"):
    #             hook.deleteLater()
    #     logger = options.get("logger")
    #     if hasattr(logger, "messageChanged"):
    #         # Reuse logger for subsequent downloads
    #         logger.messageChanged.disconnect()
    #         logger.messageChanged.connect(self.messageChanged.emit)


class QHook(QObject):
    """A class that emits a signal when the info is changed."""

    info_changed = pyqtSignal(dict)

    def __init__(self, parent: QObject = None) -> None:
        """
        Initialize the QHook object.

        Args:
            parent (QObject): The parent object. Default is None.
        """
        super().__init__(parent)

    def __call__(self, d: dict) -> None:
        """
        Call the QHook object.

        Args:
            d (dict): The dictionary containing the info.
        """
        self.info_changed.emit(d.copy())


class HistoryLogger:
    """Writes human-readable download history entries to history_log.txt."""

    HISTORY_PATH = "history_log.txt"

    @staticmethod
    def _format_entry(dt: str, site: str, dtype: str, title: str, result: str) -> str:
        return (
            f"[{dt}] Site: {site} | Type: {dtype} | Title: {title} | Result: {result}\n"
        )

    @staticmethod
    def log(site: str, dtype: str, title: str, success: bool) -> None:
        dt = datetime.now(tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S",
        )
        result = "SUCCESS" if success else "FAIL"
        try:
            with Path.open(HistoryLogger.HISTORY_PATH, "a", encoding="utf-8") as f:
                f.write(HistoryLogger._format_entry(dt, site, dtype, title, result))
        except Exception:
            # Never allow history logging to crash downloading
            pass


class HistoryHook:
    """
    A yt-dlp progress hook that records per-item success into history_log.txt.

    Expects meta with keys: 'site' and 'type'. Deduplicates by video id and
    prefers logging on postprocessing merger completion; falls back to the
    first 'finished' event for cases without merging (e.g., audio-only).
    """

    def __init__(self, meta: dict | None) -> None:
        self.meta = meta or {}
        self._seen_ids: set[str] = set()

    def _infer_site(self, info: dict) -> str:
        site = (self.meta.get("site") or "").strip().lower()
        if not site or site == "unknown":
            ek = (info.get("extractor_key") or info.get("extractor") or "").lower()
            if "youtube" in ek:
                site = "youtube"
            elif "nebula" in ek:
                site = "nebula"
            elif ek:
                site = ek
            else:
                site = "unknown"
        return site

    def _vid_id(self, info: dict) -> str:
        return str(
            info.get("id")
            or info.get("_filename")
            or info.get("url")
            or info.get("playlist_id")
            or "unknown",
        )

    def __call__(self, d: dict) -> None:
        try:
            status = d.get("status")
            info = d.get("info_dict") or {}
            vid = self._vid_id(info)
            # If already recorded for this id, ignore further events
            if vid in self._seen_ids:
                return

            postproc = (d.get("postprocessor") or "").lower()
            title = (
                info.get("title")
                or info.get("_filename")
                or info.get("id")
                or "(unknown title)"
            )
            site = self._infer_site(info)
            dtype = self.meta.get("type") or self.meta.get("source") or "unknown"

            if status == "postprocessing":
                # Prefer logging when a merge or audio-extract postprocessor finishes
                if "merger" in postproc or "ffmpegextractaudio" in postproc:
                    HistoryLogger.log(site, dtype, title, True)
                    self._seen_ids.add(vid)
            elif status == "finished":
                # Fallback for non-merged items (e.g., audio-only) or if no postprocessing runs
                HistoryLogger.log(site, dtype, title, True)
                self._seen_ids.add(vid)
        except Exception:
            # Never let history logging break the download
            pass


class QYTQueue(QThread):
    """
    Manages a threaded download queue using QThread, emitting progress and completion signals.

    Handles download tasks from a queue, emits status updates via messageChanged, and signals when the queue is empty.
    Integrates with yt-dlp for downloading, supports progress hooks, and manages logger connections for error reporting.
    """

    message_changed = pyqtSignal(str)
    queue_empty = pyqtSignal()

    def __init__(self, download_queue: Queue) -> None:
        """
        Initialize the object with a given QThread-based download queue and sets the thread as a daemon.

        Args:
            download_queue (QThread): The thread managing the download queue.
        """
        super().__init__()

        self.downloadQueue = download_queue
        self.daemon = True

    def run(self) -> None:
        """Continuously processes download tasks from the queue in a background thread, emitting progress and completion messages, and signals when the queue becomes empty. Keeps the system awake during execution using a wake lock."""
        with keep.running():
            while True:
                item = self.downloadQueue.get()
                self.message_changed.emit(f"------  Downloading  ------\n{item[0]}")
                # Perform the download task
                self.download(item[0], item[1])
                self.message_changed.emit(
                    f"------  Finished downloading  ------\n{item[0]}",
                )
                if self.downloadQueue.empty():
                    self.queue_empty.emit()

    def download(self, urls: list, options: dict) -> None:
        """
        Download videos from the provided URLs using yt-dlp with the given options.

        Handles download errors by emitting error messages and logging exceptions via QLogger.
        Cleans up progress hooks and ensures logger signal connections are properly managed.

        Args:
            urls (list): List of URLs to download.
            options (dict): yt-dlp options, including logger and progress_hooks.
        """
        try:
            # Ensure history hook is attached with metadata
            progress_hooks = list(options.get("progress_hooks", []))
            progress_hooks.append(HistoryHook(options.get("qmeta")))
            options["progress_hooks"] = progress_hooks

            with YoutubeDL(options) as ydl:
                ydl.cache.remove()
                ydl.download(urls)
        except (
            DownloadError,
            ExtractorError,
            MaxDownloadsReached,
            OSError,
            ValueError,
        ) as e:
            # Extract title for error logging
            title = urls[0] if urls else "(unknown)"
            try:
                with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                    info = ydl.extract_info(urls[0], download=False)
                    title = info.get("title", title)
            except Exception:
                pass

            error_str = str(e)
            meta = options.get("qmeta") or {}
            site = meta.get("site", "unknown")
            dtype = meta.get("type", meta.get("source", "unknown"))

            # If requested 1080 and the format is unavailable, try 720 once before failing
            if (
                "Requested format is not available" in error_str
                and dtype == "1080"
                and not options.get("_tried_720_fallback")
            ):
                self.message_changed.emit(
                    f"Requested 1080 format not available for '{title}'; retrying at 720...",
                )
                # Prepare fallback options (shallow copy is sufficient)
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
                    # Success on fallback; log and return
                    HistoryLogger.log(site, "720", title, success=True)
                    return
                except Exception as e2:  # noqa: BLE001
                    # Continue with original failure path using the new exception
                    e = e2
                    error_str = str(e)

            # If SponsorBlock is down (503 / service unavailable) retry once without it
            if (
                "Unable to communicate with SponsorBlock API" in error_str
                and not options.get("_tried_without_sponsorblock")
            ):
                self.message_changed.emit(
                    "SponsorBlock API unavailable; retrying download without SponsorBlock...",
                )
                fallback = utils.remove_sponsorblock_postprocessor(options)
                fallback["_tried_without_sponsorblock"] = True
                try:
                    with YoutubeDL(fallback) as ydl:
                        ydl.cache.remove()
                        ydl.download(urls)
                    # Success on retry; log and return
                    HistoryLogger.log(site, dtype, title, success=True)
                    return
                except Exception as e2:  # noqa: BLE001
                    # Continue with original failure path using the new exception
                    e = e2
                    error_str = str(e)

            error_message = (
                f"Error downloading '{title}' (site: {site}, type: {dtype}): {e!s}"
            )
            self.message_changed.emit(error_message)
            logger = options.get("logger")
            if isinstance(logger, QLogger):
                logger.exception(error_message)
            # Attempt to record a failure entry for the batch when title is unknown
            HistoryLogger.log(site, dtype, title, success=False)
        finally:
            for hook in options.get("progress_hooks", []):
                if hasattr(hook, "infoChanged"):
                    hook.deleteLater()
            logger = options.get("logger")
            if isinstance(logger, QLogger):
                logger.message_changed.disconnect()
                logger.message_changed.connect(self.message_changed.emit)


# class QYT(QObject):
#     def download(self, urls, options):
#         Thread(target=self._execute, args=(urls, options), daemon=True).start()

#     def _execute(self, urls, options):
#         with YoutubeDL(options) as ydl:
#             ydl.download(urls)
#         for hook in options.get("progress_hooks", []):
#             if isinstance(hook, QHook):
#                 hook.deleteLater()
#         logger = options.get("logger")
#         if isinstance(logger, QLogger):
#             logger.deleteLater()
