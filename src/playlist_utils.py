"""Playlist and URL detection utilities."""

from .logging_utils import log_exception


def detect_site_from_urls(urls: list[str]) -> str:
    """
    Best-effort detection of site from a list of URLs.

    Args:
        urls: List of URLs to analyze.

    Returns:
        Site identifier ('youtube', 'nebula', or 'unknown').
    """
    all_urls = " ".join(urls or []).lower()
    if "youtube.com" in all_urls or "youtu.be" in all_urls:
        return "youtube"
    if "nebula" in all_urls or "watchnebula" in all_urls:
        return "nebula"
    return "unknown"


def is_primitive_technology(info: dict) -> bool:
    """
    Detect Primitive Technology channel videos.

    Prefer exact channel/uploader detection when available, and fall back to
    checking the common title prefix 'Primitive Technology:' when metadata is limited.

    Args:
        info: yt-dlp info dictionary.

    Returns:
        True if video is from Primitive Technology channel, False otherwise.
    """
    try:
        # Channel/uploader info when available
        channel = (info.get("channel") or info.get("channel_id") or "").lower()
        uploader = (info.get("uploader") or info.get("uploader_id") or "").lower()
        if "primitive technology" in channel or "primitive technology" in uploader:
            return True
        # Fallback on the well-known title prefix (case-insensitive, robust to whitespace)
        title = (info.get("title") or "").strip().lower()
        if title.startswith("primitive technology:"):
            return True
    except (AttributeError, TypeError) as exc:
        log_exception(exc, "Error detecting Primitive Technology channel")
        return False
    return False


def get_playlist_file_for_source(source: str) -> str | None:
    """
    Return the on-disk playlist file path for a given source key.

    Args:
        source: Source identifier ('1080playlists', '720playlists', 'audio_playlists').

    Returns:
        File path string or None if source is not recognized.
    """
    mapping = {
        "1080playlists": r"Z:\\misc\\dev\\vid downloader\\resources\\playlists\\playlists.txt",
        "720playlists": r"Z:\\misc\\dev\\vid downloader\\resources\\playlists\\720playlists.txt",
        "audio_playlists": r"Z:\\misc\\dev\\vid downloader\\resources\\playlists\\audio playlists.txt",
    }
    return mapping.get(source)
