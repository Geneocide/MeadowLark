"""Podcast filtering logic extraction for testable episode evaluation."""

from datetime import datetime, timezone
from typing import Any

import QYT
import utils
from src.config import PODCAST_MIN_DURATION_SECONDS
from src.podcast_filtering import (
    append_to_archive_and_mark_skipped,
    check_sponsorblock_for_video_id,
    format_timestamp_readable,
    load_downloaded_video_ids,
    parse_video_timestamp,
)


class PodcastFilterExecutor:
    """
    Encapsulates podcast filtering logic for evaluating episodes.

    Evaluates playlist entries and determines their status: Downloaded, Ready,
    Pending (SponsorBlock), Upcoming, Skipped, or Error.

    Attributes:
        archive_path: Path to yt-dlp download archive file, or None.
        messages: List of status/skip messages to populate.
        bypass_sponsorblock_wait: If True, skip SponsorBlock wait for recent episodes.
    """

    def __init__(
        self,
        archive_path: str | None = None,
        messages: list[str] | None = None,
        bypass_sponsorblock_wait: bool = False,
    ) -> None:
        """
        Initialize the podcast filter executor.

        Args:
            archive_path: Path to yt-dlp download archive file, or None.
            messages: List to populate with filtering messages. If None, creates new list.
            bypass_sponsorblock_wait: If True, skip the SponsorBlock wait requirement.
        """
        self.archive_path = archive_path
        self.messages = messages if messages is not None else []
        self.bypass_sponsorblock_wait = bypass_sponsorblock_wait
        self.existing_ids = load_downloaded_video_ids(archive_path)
        self.now_ts = datetime.now(tz=timezone.utc).timestamp()

    def evaluate_playlist_urls(
        self,
        entries: list[dict[str, Any]],
    ) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, str]]:
        """
        Evaluate a list of playlist entries and categorize them by status.

        Args:
            entries: List of yt-dlp entry dicts from a playlist.

        Returns:
            Tuple of (to_download, pending_sponsorblock, status_entry) where:
            - to_download: List of entries ready for download
            - pending_sponsorblock: List of new entries awaiting SponsorBlock data
            - status_entry: Dict with latest entry status information
        """
        to_download: list[dict[str, str]] = []
        pending: list[dict[str, str]] = []
        status_entry: dict[str, str] = {
            "latest_date": "(unknown)",
            "status": "(unknown)",
        }

        for entry in entries:
            vid = entry.get("id") or entry.get("url")
            webpage = entry.get("webpage_url") or entry.get("url")

            if not vid or not webpage:
                continue

            status_entry["latest_url"] = webpage
            status_entry["latest_ts"] = parse_video_timestamp(entry)

            # Check if already downloaded
            if self._is_already_archived(vid):
                status_entry["status"] = "Downloaded"
                break

            title = entry.get("title", "") or ""

            # Check for special "(Update)" titles
            if self._should_skip_update_exception(title, vid, webpage):
                status_entry["status"] = "Skipped (Update)"
                break

            # Check if episode is too short
            duration = entry.get("duration")
            if self._should_skip_short_duration(duration, title, vid, webpage):
                status_entry["status"] = "Skipped Short"
                break

            # Determine status based on timestamp and SponsorBlock
            ts = parse_video_timestamp(entry)
            status, download_urls = self._evaluate_episode_status(
                ts,
                title,
                vid,
                webpage,
            )
            status_entry["status"] = status

            # Populate download lists based on status
            if status == "Ready":
                to_download.extend(download_urls)
            elif status == "Pending SponsorBlock":
                pending.extend(download_urls)

            # Update latest date
            status_entry["latest_date"] = format_timestamp_readable(ts)
            break

        return to_download, pending, status_entry

    def _is_already_archived(self, vid: str) -> bool:
        """Check if video ID is already in the download archive."""
        return vid in self.existing_ids

    def _should_skip_update_exception(
        self,
        title: str,
        vid: str,
        webpage: str,
    ) -> bool:
        """
        Check if episode should be skipped due to "(Update)" in title.

        Args:
            title: Episode title to check.
            vid: Video ID for archiving.
            webpage: Webpage URL for site detection.

        Returns:
            True if episode has "(Update)" title and was skipped, False otherwise.
        """
        if "(Update)" not in title:
            return False

        append_to_archive_and_mark_skipped(
            self.archive_path,
            vid,
            self.existing_ids,
            title,
            self.messages,
        )
        site = utils.detect_site_from_urls([webpage])
        QYT.HistoryLogger.log_skip(
            site=site,
            dtype="audio_playlists",
            title=title,
            reason="Update exception",
        )
        return True

    def _should_skip_short_duration(
        self,
        duration: int | None,
        title: str,
        vid: str,
        webpage: str,
    ) -> bool:
        """
        Check if episode should be skipped due to short duration (< 3 minutes).

        Args:
            duration: Episode duration in seconds, or None if not available.
            title: Episode title for logging.
            vid: Video ID for archiving.
            webpage: Webpage URL for site detection.

        Returns:
            True if episode is too short and was skipped, False otherwise.
        """
        if duration is None or duration >= PODCAST_MIN_DURATION_SECONDS:
            return False

        append_to_archive_and_mark_skipped(
            self.archive_path,
            vid,
            self.existing_ids,
            title,
            self.messages,
            reason="Short duration (<3 min)",
        )
        site = utils.detect_site_from_urls([webpage])
        QYT.HistoryLogger.log_skip(
            site=site,
            dtype="audio_playlists",
            title=title,
            reason="Short duration (<3 min)",
        )
        return True

    def _evaluate_episode_status(
        self,
        ts: float | None,
        title: str,
        vid: str,
        webpage: str,
    ) -> tuple[str, list[dict[str, str]]]:
        """
        Determine episode status and download readiness based on timestamp.

        Evaluates:
        - Upcoming scheduled episodes (future timestamp)
        - Recent episodes with SponsorBlock data (< 24h + SponsorBlock segments)
        - Recent episodes pending SponsorBlock (< 24h but no SponsorBlock)
        - Older episodes (>= 24h old)
        - Episodes without timestamp

        Args:
            ts: Upload timestamp (seconds since epoch), or None.
            title: Episode title for logging.
            vid: Video ID for SponsorBlock checks.
            webpage: Webpage URL for download queue.

        Returns:
            Tuple of (status_str, download_urls_list) where:
            - status_str: One of "Upcoming", "Ready", "Pending SponsorBlock"
            - download_urls_list: List with entry dict if "Ready", empty list otherwise
        """
        download_url = {"url": webpage, "playlist": ""}

        if ts is None:
            # No timestamp: be permissive and download
            return "Ready", [download_url]

        if ts > self.now_ts:
            # Future timestamp: upcoming scheduled episode
            return "Upcoming", []

        age_seconds = self.now_ts - ts
        age_24h = 24 * 60 * 60

        if self.bypass_sponsorblock_wait:
            # Bypass SponsorBlock wait entirely
            return "Ready", [download_url]

        if age_seconds < age_24h:
            # New episode (< 24h): check SponsorBlock for YouTube
            site = utils.detect_site_from_urls([webpage])
            if site == "youtube":
                if check_sponsorblock_for_video_id(vid):
                    return "Ready", [download_url]
                return "Pending SponsorBlock", [download_url]

            # Non-YouTube: no SponsorBlock requirement
            return "Ready", [download_url]

        # Older than 24h: download
        return "Ready", [download_url]
