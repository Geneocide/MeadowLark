"""YDL utility functions for common yt-dlp operations."""

import yt_dlp

_QUIET_YDL_OPTS: dict[str, bool] = {"quiet": True, "no_warnings": True}


def extract_playlist_info(
    url: str,
    playlistend: int | None = None,
    ydl_class: type | None = None,
) -> dict:
    """
    Extract playlist/video info with standard quiet options.

    Args:
        url: The URL to extract info from.
        playlistend: Optional limit on number of entries to extract.
        ydl_class: Optional custom YoutubeDL class for injection.

    Returns:
        Dictionary containing extracted info.
    """
    if ydl_class is None:
        ydl_class = yt_dlp.YoutubeDL
    opts: dict = {**_QUIET_YDL_OPTS}
    if playlistend:
        opts["playlistend"] = playlistend
    with ydl_class(opts) as ydl:
        return ydl.extract_info(url, download=False)


def extract_video_entries(
    url: str,
    extract_flat: bool | str = True,
    ydl_class: type | None = None,
) -> list:
    """
    Extract entries from URL (playlist or video).

    Args:
        url: The URL to extract entries from.
        extract_flat: Whether to extract flat info (True) or full info (False).
        ydl_class: Optional custom YoutubeDL class for injection.

    Returns:
        List of entry dictionaries.
    """
    if ydl_class is None:
        ydl_class = yt_dlp.YoutubeDL
    opts = {**_QUIET_YDL_OPTS, "extract_flat": extract_flat}
    with ydl_class(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("entries", [info])
