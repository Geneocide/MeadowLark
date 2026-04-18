"""
DownloadService - Handles download request processing, queue management, and podcast triggering.

This module provides the DownloadService class that encapsulates the logic for processing download requests,
managing the download queue, and triggering podcast checks. It extracts this functionality from the MyWindow class
to improve testability and separation of concerns.
"""

from collections.abc import Callable
from pathlib import Path
from queue import Queue
from typing import Any

import yt_dlp

import QYT
import utils
from src import live_queue
from src.config import (
    ARCHIVE_PATH,
    LIVE_QUEUE_FILE,
    PLAYLISTS_720_FILE,
    PLAYLISTS_AUDIO_FILE,
    PLAYLISTS_FILE,
    YDL_EXTRACTION_ERRORS,
)
from src.match_filter import build_match_filter
from src.playlist_utils import load_playlist_urls
from src.podcast_filtering import load_downloaded_video_ids


class DownloadService:
    """
    Service class for handling download requests, queue management, and podcast triggering.

    This class extracts the download logic from MyWindow to provide a testable, modular component
    that manages download requests, builds options, handles playlists, and coordinates podcast checks.
    """

    def __init__(
        self,
        download_queue: Queue,
        ignore_archive_callback: Callable[[], bool],
        skip_download_callback: Callable[[], bool],
        label_output_set_text_callback: Callable[[str], None],
        log_edit_append_callback: Callable[[str], None],
        bar_progress_set_range_callback: Callable[[int, int], None],
        bar_progress_set_value_callback: Callable[[int], None],
        handle_info_changed_callback: Callable[[Any], None],
        handle_log_entry_callback: Callable[[str], None],
        handle_queue_empty_callback: Callable[[], None],
        do_updates_callback: Callable[[], None],
        add_to_live_queue_callback: Callable[[str, str, str | None], None],
        qhook_factory: Callable[[], QYT.QHook],
        qlogger_factory: Callable[[], QYT.QLogger],
    ) -> None:
        """
        Initialize the DownloadService with necessary callbacks and dependencies.

        Args:
            download_queue: The download queue to use for queuing downloads.
            ignore_archive_callback: Callback to check if archive should be ignored.
            skip_download_callback: Callback to check if download should be skipped.
            label_output_set_text_callback: Callback to set label output text.
            log_edit_append_callback: Callback to append to log edit.
            bar_progress_set_range_callback: Callback to set progress bar range.
            bar_progress_set_value_callback: Callback to set progress bar value.
            handle_info_changed_callback: Callback to handle info changed.
            handle_log_entry_callback: Callback to handle log entry.
            handle_queue_empty_callback: Callback to handle queue empty.
            do_updates_callback: Callback to perform updates.
            add_to_live_queue_callback: Callback to add to live queue (url, source, playlist_id).
            qhook_factory: Factory for QHook.
            qlogger_factory: Factory for QLogger.
        """
        self.download_queue = download_queue
        self.ignore_archive_callback = ignore_archive_callback
        self.skip_download_callback = skip_download_callback
        self.label_output_set_text_callback = label_output_set_text_callback
        self.log_edit_append_callback = log_edit_append_callback
        self.bar_progress_set_range_callback = bar_progress_set_range_callback
        self.bar_progress_set_value_callback = bar_progress_set_value_callback
        self.handle_info_changed_callback = handle_info_changed_callback
        self.handle_log_entry_callback = handle_log_entry_callback
        self.handle_queue_empty_callback = handle_queue_empty_callback
        self.do_updates_callback = do_updates_callback
        self.add_to_live_queue_callback = add_to_live_queue_callback
        self.qhook_factory = qhook_factory
        self.qlogger_factory = qlogger_factory

        self.live_queue_path = LIVE_QUEUE_FILE

    def request_detected(self, urls: list, source: str) -> tuple[str, list, dict]:
        """
        Handle a detected download request by preparing options, updating URLs if needed, and returning action.

        Args:
            urls (list): List of URLs to process.
            source (str): The source type or action (e.g., playlist type or 'Update').

        Returns:
            tuple: (action, urls, ydl_opts) where action is 'update', 'skip', 'queue', 'podcast_check'
        """
        if source == "Update":
            self.do_updates_callback()
            return ("update", [], {})

        # Load playlist URLs if applicable
        if not urls:  # Only load from file if no URLs provided
            playlist_urls = self._load_playlist_urls(source)
            if playlist_urls is not None:
                urls = playlist_urls

        properties = self.get_options(urls, source)
        if properties is None:
            return ("skip", [], {})

        ydl_opts = utils.build_base_ydl_opts(None, None)
        ydl_opts = self.append_properties(ydl_opts, properties)
        ydl_opts["qmeta"] = {
            "site": utils.detect_site_from_urls(urls),
            "type": source,
        }

        if source == "audio_playlists":
            return ("podcast_check", urls, ydl_opts)
        return ("queue", urls, ydl_opts)

    def _load_playlist_urls(self, source: str) -> list[str] | None:
        """Load playlist URLs from the appropriate file based on the source."""
        playlist_files = {
            "1080playlists": PLAYLISTS_FILE,
            "720playlists": PLAYLISTS_720_FILE,
            "audio_playlists": PLAYLISTS_AUDIO_FILE,
        }
        if source not in playlist_files:
            return None
        return load_playlist_urls(Path(playlist_files[source])) or None

    def get_options(self, urls: list, source: str) -> dict | None:
        """
        Build yt-dlp options dict based on URLs and source type.

        Args:
            urls: List of URLs to process.
            source: The source type (e.g., "1080playlists", "audio").

        Returns:
            Dict of yt-dlp options, or None if download should be skipped/cancelled.
        """
        if self.skip_download_callback():
            self.skip_downloading(urls, source)
            return None

        # If a playlist file contained no URLs, bail out early to avoid errors
        if not urls:
            self.log_edit_append_callback(f"No URLs found for source: {source}")
            return None

        properties = utils.get_source_options(source)

        # ignore archive checkbox
        if not self.ignore_archive_callback():
            properties["download_archive"] = str(ARCHIVE_PATH)

        # detect if YT
        if "youtube.com" in urls[0]:
            # Use a custom match_filter that records live videos for later
            properties["match_filter"] = self.make_match_filter(source)

        # strip out unnecessary parts of URL if dropping from Watch Later
        if "youtube.com/watch" in urls[0] and "&list=" in urls[0]:
            urls[0] = urls[0].split("&list=")[0]

        return properties

    def append_properties(self, ydl_opts: dict, properties: dict) -> dict | None:
        """
        Append additional properties to yt-dlp options.

        Args:
            ydl_opts (dict): Base yt-dlp options.
            properties (dict): Additional properties to append.

        Returns:
            dict: Updated yt-dlp options, or None if cancelled.
        """
        ydl_opts.update(properties)
        return ydl_opts

    def skip_downloading(self, urls: list, source: str) -> None:
        """Skip downloading the given URLs for the source."""
        self.label_output_set_text_callback("Skipping downloads.")
        qlogger = self.qlogger_factory()
        total_added = 0
        archive_path = ARCHIVE_PATH
        existing_ids = load_downloaded_video_ids(str(ARCHIVE_PATH))
        for url in urls:
            # Use extract_flat="in_playlist" for playlists, True for single videos
            ydl_opts = {
                "extract_flat": "in_playlist" if "lists" in source else True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                entries = info.get("entries", [info])
                with archive_path.open("a", encoding="utf-8") as archive:
                    for entry in entries:
                        video_id = entry.get("id")
                        if video_id and video_id not in existing_ids:
                            archive.write(f"youtube {video_id}\n")
                            total_added += 1
                            qlogger.debug("Added to archive: youtube %(video_id)s")
        self.label_output_set_text_callback("IDs added to archive.")
        self.bar_progress_set_range_callback(0, 1)
        self.bar_progress_set_value_callback(1)
        self.log_edit_append_callback(
            f"Archive-only mode: {total_added} IDs written.",
        )
        self.handle_queue_empty_callback()

    def make_match_filter(self, source: str) -> Callable:
        """Build a match_filter that skips live/upcoming videos and queues them."""
        return build_match_filter(
            source,
            add_to_queue_fn=self.add_to_live_queue_callback,
            log_fn=self.log_edit_append_callback,
        )

    def load_live_queue(self) -> live_queue.LiveQueueEntries:
        """Load live queue entries; returns {url: (source, playlist_id)}."""
        return live_queue.load_live_queue(self.live_queue_path)

    def save_live_queue(self, entries: live_queue.LiveQueueEntries) -> None:
        """Save the live queue entries to file."""
        live_queue.save_live_queue(self.live_queue_path, entries)

    def add_to_live_queue(self, url: str, source: str, playlist_id: str | None = None) -> None:
        """Add a URL to the live queue."""
        live_queue.add_to_live_queue(self.live_queue_path, url, source, playlist_id)

    def check_live_queue(self) -> None:
        """Check the live queue for ended lives and queue them for download."""
        entries = self.load_live_queue()
        if not entries:
            return
        remaining: dict[str, tuple[str, str | None]] = {}
        for url, (source, playlist_id) in entries.items():
            try:
                with yt_dlp.YoutubeDL(
                    {
                        "quiet": True,
                        "skip_download": True,
                        "cookiefile": r"resources\cookies.txt",
                        "extract_flat": True,
                    },
                ) as ydl:
                    info = ydl.extract_info(url, download=False)
                is_live = info.get("is_live")
                live_status = info.get("live_status")
                if is_live or live_status in ("is_live", "is_upcoming"):
                    # Still live; keep it in the queue
                    remaining[url] = (source, playlist_id)
                else:
                    self.log_edit_append_callback(
                        f"Live ended, queued: {url} [{source}]",
                    )
                    qhook = self.qhook_factory()
                    qlogger = self.qlogger_factory()
                    ydl_opts = utils.build_base_ydl_opts(qlogger, qhook)
                    properties = self.get_options([url], source)
                    if properties:
                        # Don't re-apply match_filter: stream already confirmed ended
                        properties.pop("match_filter", None)
                        ydl_opts = self.append_properties(ydl_opts, properties)
                        qmeta: dict = {
                            "site": utils.detect_site_from_urls([url]),
                            "type": source,
                        }
                        if playlist_id:
                            playlist_comments = utils.load_playlist_comments_for_source(source)
                            if playlist_comments:
                                qmeta["playlist_comments"] = playlist_comments
                                qmeta["playlist_id"] = playlist_id
                        ydl_opts["qmeta"] = qmeta

                        self.download_queue.put(([url], ydl_opts))
                        qhook.info_changed.connect(self.handle_info_changed_callback)
                        qlogger.message_changed.connect(self.handle_log_entry_callback)
                        self.bar_progress_set_range_callback(0, 1)
            except YDL_EXTRACTION_ERRORS as e:
                # If any error in checking, keep it for later
                remaining[url] = (source, playlist_id)
                self.log_edit_append_callback(
                    f"Error checking live queue: {e}",
                )
        self.save_live_queue(remaining)
