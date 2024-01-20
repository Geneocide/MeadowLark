from threading import Thread
from PyQt6.QtCore import QObject, pyqtSignal
from yt_dlp import YoutubeDL
import time


class QLogger(QObject):
    messageChanged = pyqtSignal(str)

    def debug(self, msg):
        if "ETA" not in msg and "iB/s" not in msg:
            self.messageChanged.emit(msg)

    def warning(self, msg):
        self.messageChanged.emit(msg)

    def error(self, msg):
        self.messageChanged.emit(msg)


class QHook(QObject):
    infoChanged = pyqtSignal(dict)

    def __call__(self, d):
        self.infoChanged.emit(d.copy())


class QYTQueue(Thread):
    def __init__(self, download_queue):
        super().__init__()
        self.download_queue = download_queue
        self.is_downloading = False
        self.daemon = True

    def run(self):
        while True:
            if not self.download_queue.empty():
                if self.is_downloading:
                    # Wait for the current download to finish
                    while self.is_downloading:
                        time.sleep(1)

                item = self.download_queue.get()
                self.is_downloading = True
                print(f"Downloading {item[0]}")
                # Perform the download task
                self.download(item[0], item[1])
                print(f"Download finished for {item[0]}")
                self.is_downloading = False
            else:
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


class QYT(QObject):
    def download(self, urls, options):
        Thread(target=self._execute, args=(urls, options), daemon=True).start()

    def _execute(self, urls, options):
        with YoutubeDL(options) as ydl:
            ydl.download(urls)
        for hook in options.get("progress_hooks", []):
            if isinstance(hook, QHook):
                hook.deleteLater()
        logger = options.get("logger")
        if isinstance(logger, QLogger):
            logger.deleteLater()
