"""YDL utility functions for common yt-dlp operations."""

import yt_dlp

from .ydl_options import build_shared_extraction_opts

_QUIET_YDL_OPTS: dict[str, bool] = {"quiet": True, "no_warnings": True}


def extract_playlist_info(
    url: str,
    playlistend: int | None = None,
    ydl_class: type | None = None,
    extra_opts: dict | None = None,
) -> dict:
    """
    Extract playlist/video info with standard quiet options.

    Includes the shared PO-token provider wiring (see
    ``build_shared_extraction_opts``) so metadata-only lookups -- e.g.
    ``meadowlark.pyw``'s on-demand "open latest episode" resolution and
    ``DownloadExecutor._extract_title``'s error-path title lookup -- don't
    fall back to the bgutil provider's stale default server_home and hit its
    cold-cache Deno probe budget.

    Args:
        url: The URL to extract info from.
        playlistend: Optional limit on number of entries to extract.
        ydl_class: Optional custom YoutubeDL class for injection.
        extra_opts: Optional extra options merged after the quiet baseline
            (e.g. ``{"cookiefile": "/path/to/cookies.txt"}``).

    Returns:
        Dictionary containing extracted info.
    """
    if ydl_class is None:
        ydl_class = yt_dlp.YoutubeDL
    opts: dict = {**build_shared_extraction_opts(), **_QUIET_YDL_OPTS}
    if extra_opts:
        opts.update(extra_opts)
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

    Includes the shared PO-token provider wiring (see
    ``build_shared_extraction_opts``); see ``extract_playlist_info`` for why.

    Args:
        url: The URL to extract entries from.
        extract_flat: Whether to extract flat info (True) or full info (False).
        ydl_class: Optional custom YoutubeDL class for injection.

    Returns:
        List of entry dictionaries.
    """
    if ydl_class is None:
        ydl_class = yt_dlp.YoutubeDL
    opts = {
        **build_shared_extraction_opts(),
        **_QUIET_YDL_OPTS,
        "extract_flat": extract_flat,
    }
    with ydl_class(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("entries", [info])
