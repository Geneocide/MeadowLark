from threading import Thread
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from yt_dlp import YoutubeDL
import time

# import logging

# logging.basicConfig(filename="logfile.txt", level=logging.DEBUG)


class QLogger(QObject):
    messageChanged = pyqtSignal(str)

    def debug(self, msg):
        # logging.debug(msg)
        if "ETA" not in msg and "iB/s" not in msg:
            self.messageChanged.emit(msg)

    def warning(self, msg):
        # logging.warning(msg)
        self.messageChanged.emit(msg)

    def error(self, msg):
        # logging.error(msg)
        self.messageChanged.emit(msg)


class QHook(QObject):
    infoChanged = pyqtSignal(dict)

    def __call__(self, d):
        self.infoChanged.emit(d.copy())


class QYTQueue(QThread):
    messageChanged = pyqtSignal(str)
    queueEmpty = pyqtSignal(bool)

    def __init__(self, downloadQueue):
        super().__init__()
        self.downloadQueue = downloadQueue
        self.is_downloading = False
        self.daemon = True

    def run(self):
        while True:
            if not self.downloadQueue.empty():
                if self.is_downloading:
                    # Wait for the current download to finish
                    while self.is_downloading:
                        time.sleep(1)

                item = self.downloadQueue.get()
                self.is_downloading = True
                self.messageChanged.emit(
                    "\n".join(["------  Downloading  ------"] + item[0])
                )
                # Perform the download task
                self.download(item[0], item[1])
                self.messageChanged.emit(
                    "\n".join(["------  Finished downloading  ------"] + item[0])
                )
                self.is_downloading = False
            else:
                self.queueEmpty.emit(True)
                time.sleep(1)  # Check for new items in the queue periodically

    # def download(self, urls, options):
    #     Thread(target=self._execute, args=(urls, options), daemon=True).start()

    def download(self, urls, options):
        with YoutubeDL(options) as ydl:
            ydl.cache.remove()
            ydl.download(urls)
        for hook in options.get("progress_hooks", []):
            if isinstance(hook, QHook):
                hook.deleteLater()
        logger = options.get("logger")
        if isinstance(logger, QLogger):
            logger.deleteLater()


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
