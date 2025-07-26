"""Provides PyQt-based classes for logging, progress signaling, and threaded download queue management using yt-dlp. Includes QLogger for emitting log messages, QHook for progress updates, and QYTQueue for managing and executing download tasks in a background thread with wake lock support."""

import logging
from queue import Queue

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from wakepy import keep
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError, MaxDownloadsReached

logging.basicConfig(
    filename="logfile.txt",
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
            error_message = f"Error downloading {urls}: {e!s}"
            self.message_changed.emit(error_message)
            logger = options.get("logger")
            if isinstance(logger, QLogger):
                logger.exception(error_message)
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
