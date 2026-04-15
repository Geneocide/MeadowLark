"""Centralized yt-dlp option builders and constants."""

from typing import Any

from .config import (
    COOKIES_FILE,
    MAX_FRAGMENT_RETRIES,
    SOCKET_TIMEOUT_SECONDS,
    VENV_SCRIPTS_DIR,
)
from .dict_utils import _default_postprocessors

# JavaScript runtimes configuration
JS_RUNTIMES_CONFIG = {
    "deno": {
        "path": VENV_SCRIPTS_DIR,
    },
}


def build_base_ydl_opts(logger: Any, qhook: Any) -> dict[str, Any]:  # noqa: ANN401
    """
    Centralize common yt-dlp options used across the app.

    Args:
        logger: Logger instance with debug/warning/error/exception methods.
        qhook: Progress hook callable that emits info_changed signal.

    Returns:
        Dictionary of base yt-dlp options suitable for most downloads.
    """
    return {
        "logger": logger,
        "progress_hooks": [qhook],
        "windowsfilenames": True,
        "socket-timeout": SOCKET_TIMEOUT_SECONDS,
        "max_fragment_retries": MAX_FRAGMENT_RETRIES,
        "mtime": True,
        # Custom match_filter will be set per-source by callers
        "cookiefile": str(COOKIES_FILE),
        "postprocessors": _default_postprocessors(),
        "js_runtimes": JS_RUNTIMES_CONFIG,
        "remote_components": ["ejs:github"],
    }


def get_source_options(source: str) -> dict[str, Any]:
    """
    Return yt-dlp properties for a given source type.

    Args:
        source: The download source identifier.

    Returns:
        A dictionary of yt-dlp options specific to the source.
    """
    source_options = {
        "audio": {
            "format": "m4a/bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
            ],
            "outtmpl": (
                "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/misc/%(title)s.%(ext)s"
            ),
        },
        "audio_playlists": {
            "format": "m4a/bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "m4a"},
            ],
            "outtmpl": (
                "C:/Users/etreq/OneDrive/Desktop/scripts/manual podcasts/misc/%(title)s.%(ext)s"
            ),
            "ignoreerrors": "only_download",
        },
        "720playlists": {
            "format": (
                "bestvideo*[height=720][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo*[height=720]+bestaudio/"
                "best[height=720]/best"
            ),
            "merge_output_format": "mp4",
            "outtmpl": (
                "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s"
            ),
            "ignoreerrors": "only_download",
        },
        "1080playlists": {
            "format": (
                "bestvideo*[height=1080][ext=mp4]+bestaudio[ext=m4a]/"
                "bestvideo*[height=1080]+bestaudio/"
                "best[height=1080]/best"
            ),
            "merge_output_format": "mp4",
            "outtmpl": (
                "E:/vid storage/%(playlist)s/%(playlist_index)s - %(title)s.%(ext)s"
            ),
            "ignoreerrors": "only_download",
        },
    }

    if source in source_options:
        return source_options[source].copy()

    try:
        height = int(source)
    except ValueError:
        height = None

    if height:
        format_string = (
            f"bestvideo*[height={height}][ext=mp4]+bestaudio[ext=m4a]/"
            f"bestvideo*[height={height}]+bestaudio/"
            f"best[height={height}]/best"
        )
    else:
        format_string = "bestvideo*+bestaudio/best"

    return {
        "format": format_string,
        "merge_output_format": "mp4",
        "outtmpl": "E:/vid storage/%(title)s.%(ext)s",
        "postprocessors": _default_postprocessors(),
    }


def get_output_template(source: str) -> str:
    """
    Return the output filename template for the source.

    Args:
        source: The source identifier.

    Returns:
        The yt-dlp output template string.
    """
    return get_source_options(source)["outtmpl"]


def get_postprocessors(source: str) -> list[dict[str, Any]]:
    """
    Return the postprocessors list for the source.

    Args:
        source: The source identifier.

    Returns:
        A list of yt-dlp postprocessor dictionaries.
    """
    return get_source_options(source).get("postprocessors", _default_postprocessors())
