"""Podcast filtering and categorization helpers for episode processing."""

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

import utils

HTTP_OK = 200


def parse_video_timestamp(entry: dict[str, Any]) -> float | None:
    """
    Extract timestamp from entry, trying 'timestamp' field then 'upload_date'.

    Args:
        entry: A yt-dlp entry dict with optional 'timestamp' or 'upload_date' fields.

    Returns:
        Timestamp as a float (seconds since epoch), or None if not found/parseable.
    """
    ts = entry.get("timestamp")
    if not ts and entry.get("upload_date"):
        try:
            ts = (
                datetime.strptime(entry.get("upload_date"), "%Y%m%d")
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
        except (ValueError, TypeError) as exc:
            ts = None
            utils.log_exception(exc, "Failed to parse upload_date timestamp")
    return ts


def load_downloaded_video_ids(archive_path: str | None) -> set[str]:
    """
    Load set of already-downloaded video IDs from archive file.

    Archive file format: lines like "youtube <video_id>" or similar.
    Only the last space-separated token (video_id) is extracted.

    Args:
        archive_path: Path to archive file, or None if not configured.

    Returns:
        Set of video IDs that have already been downloaded.
    """
    existing_ids: set[str] = set()
    if not archive_path:
        return existing_ids

    archive_file = Path(archive_path)
    if not archive_file.exists():
        return existing_ids

    try:
        with archive_file.open("r", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                parts = stripped_line.split()
                if parts:
                    existing_ids.add(parts[-1])
    except (OSError, UnicodeDecodeError) as exc:
        utils.log_exception(
            exc,
            "Failed to read download archive for podcast filtering",
        )

    return existing_ids


def format_timestamp_readable(ts: float | None) -> str:
    """
    Convert timestamp to human-readable date string.

    Args:
        ts: Timestamp as float (seconds since epoch), or None.

    Returns:
        Formatted date string like "2025-03-24", or "(unknown)" if ts is None.
    """
    if ts is None:
        return "(unknown)"
    try:
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return dt.strftime("%Y-%m-%d")
    except (OSError, ValueError):
        return "(unknown)"


def append_to_archive_and_mark_skipped(
    archive_path: str | None,
    vid: str,
    existing_ids: set[str],
    title: str,
    messages: list[str],
) -> None:
    """
    Append update-marked video to archive and add skip message.

    When a video title contains "(Update)", it is skipped and marked as archived
    to avoid re-processing it in future checks.

    Args:
        archive_path: Path to archive file, or None.
        vid: Video ID to add to archive.
        existing_ids: Set of already-archived IDs (modified in place).
        title: Video title for logging.
        messages: List of messages to append to (modified in place).
    """
    if archive_path:
        try:
            with Path(archive_path).open("a", encoding="utf-8") as f:
                if vid not in existing_ids:
                    f.write(f"youtube {vid}\n")
                    existing_ids.add(vid)
        except OSError as exc:
            utils.log_exception(
                exc,
                "Failed to write update marker to download archive",
            )

    timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    messages.append(
        f"Video skipped because of Update exception: '{title}' "
        f"(ID: {vid}) at {timestamp_str}",
    )


def parse_scheduled_time_from_error(error_str: str) -> float | None:
    """
    Extract scheduled start timestamp from error message.

    Handles patterns like:
    - "Premieres in X hours" or "Premieres in X days"
    - "Scheduled to begin YYYY-MM-DD HH:MM:SS UTC" or "YYYY-MM-DD HH:MM UTC"

    Args:
        error_str: Error message string from yt-dlp.

    Returns:
        Timestamp of scheduled start, or None if no pattern matches.
    """
    # Try "will begin in X hours" or "will begin in X days"
    match = re.search(r"will begin in (\d+)\s+(hours?|days?)", error_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2).lower()
        multiplier = 3600 if "hour" in unit else 86400
        return datetime.now(tz=timezone.utc).timestamp() + (value * multiplier)

    # Try "scheduled to begin" with date patterns
    match = re.search(r"scheduled to begin (.+?)(?:\s+UTC)?$", error_str)
    if match:
        date_str = match.group(1).strip()
        # Try date/time formats in order; avoid try-except in loop
        dt = _try_parse_datetime(date_str, ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"))
        if dt:
            return dt.timestamp()

    return None


def _try_parse_datetime(
    date_str: str,
    formats: tuple[str, ...],
) -> datetime | None:
    """
    Try parsing date string with multiple formats.

    Args:
        date_str: Date/time string to parse.
        formats: Tuple of format strings to try in order.

    Returns:
        Parsed datetime with UTC timezone, or None if no format matched.
    """
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).replace(
                tzinfo=timezone.utc,
            )
        except ValueError:  # noqa: PERF203
            continue
    return None


def check_sponsorblock_for_video_id(video_id: str) -> bool:
    """
    Check if SponsorBlock has segments for the given YouTube video ID.

    Args:
        video_id: YouTube video ID to check.

    Returns:
        True if SponsorBlock API returns segments (non-empty list), False otherwise.
        Also returns False on API errors.
    """
    try:
        url = f"https://sponsor.ajay.app/api/skipSegments?videoID={video_id}"
        r = requests.get(url, timeout=5)
        if r.status_code == HTTP_OK:
            data = r.json()
            return bool(data)
    except (requests.exceptions.RequestException, ValueError) as exc:
        utils.log_exception(exc, "SponsorBlock API check failed")
    return False
