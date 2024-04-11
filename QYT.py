from queue import Queue
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from yt_dlp import YoutubeDL
import logging
import pickle

logging.basicConfig(
    filename="logfile.txt", level=logging.ERROR, format="%(asctime)s %(message)s"
)


class QLogger(QObject):
    messageChanged = pyqtSignal(str)

    def __init__(self, downloadQueue: Queue) -> None:
        super().__init__()
        self.downloadQueue = downloadQueue
        self.daemon = True

    def debug(self, msg):
        logging.debug(msg)
        if "ETA" not in msg and "iB/s" not in msg:
            self.messageChanged.emit(msg)

    def warning(self, msg):
        logging.warning(msg)
        self.messageChanged.emit(msg)

    def error(self, msg):
        logging.error(msg)
        with ("persisted_queue.txt", "wb") as f:
            pickle.dump(self.downloadQueue)
        self.messageChanged.emit(msg)

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
    """
    A class that emits a signal when the info is changed.
    """

    infoChanged = pyqtSignal(dict)

    def __init__(self, parent=None):
        """
        Initialize the QHook object.

        Args:
            parent (QObject): The parent object. Default is None.
        """
        super().__init__(parent)

    def __call__(self, d: dict):
        """
        Call the QHook object.

        Args:
            d (dict): The dictionary containing the info.
        """
        self.infoChanged.emit(d.copy())


class QYTQueue(QThread):
    messageChanged = pyqtSignal(str)
    queueEmpty = pyqtSignal(bool)

    def __init__(self, downloadQueue):
        super().__init__()

        self.downloadQueue = downloadQueue
        self.daemon = True

    def run(self):
        while True:
            item = self.downloadQueue.get()
            self.messageChanged.emit(f"------  Downloading  ------\n{item[0]}")
            # Perform the download task
            self.download(item[0], item[1])
            self.messageChanged.emit(f"------  Finished downloading  ------\n{item[0]}")
            if self.downloadQueue.empty():
                self.queueEmpty.emit(True)

    def download(self, urls, options):
        with YoutubeDL(options) as ydl:
            ydl.cache.remove()
            ydl.download(urls)
        for hook in options.get("progress_hooks", []):
            if hasattr(hook, "infoChanged"):
                hook.deleteLater()
        logger = options.get("logger")
        if isinstance(logger, QLogger):
            logger.messageChanged.disconnect()
            logger.messageChanged.connect(self.messageChanged.emit)


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
