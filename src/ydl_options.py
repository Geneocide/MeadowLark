"""Centralized yt-dlp option builders and constants."""

from pathlib import Path
from typing import Any

from .config import (
    COOKIES_FILE,
    MAX_FRAGMENT_RETRIES,
    PODCAST_MISC_OUTPUT_DIR,
    SOCKET_TIMEOUT_SECONDS,
    VENV_SCRIPTS_DIR,
    VIDEO_STORAGE_DIR,
)
from .dict_utils import DEFAULT_POSTPROCESSORS
from .qt_protocols import YdlLogger, YdlProgressHook
from .settings_dialog import get_setting

# JavaScript runtimes configuration
JS_RUNTIMES_CONFIG = {
    "deno": {
        "path": VENV_SCRIPTS_DIR,
    },
}


def build_base_ydl_opts(logger: YdlLogger, qhook: YdlProgressHook) -> dict[str, Any]:
    """
    Centralize common yt-dlp options used across the app.

    Args:
        logger: Logger instance with debug/warning/error/exception methods.
        qhook: Progress hook callable that emits info_changed signal.

    Returns:
        Dictionary of base yt-dlp options suitable for most downloads.
    """
    opts: dict[str, Any] = {
        "logger": logger,
        "progress_hooks": [qhook],
        "windowsfilenames": True,
        "socket-timeout": SOCKET_TIMEOUT_SECONDS,
        "max_fragment_retries": MAX_FRAGMENT_RETRIES,
        "mtime": True,
        # Custom match_filter will be set per-source by callers
        "cookiefile": get_setting("VID_DL_COOKIES_FILE") or str(COOKIES_FILE),
        "postprocessors": list(DEFAULT_POSTPROCESSORS),
        "js_runtimes": JS_RUNTIMES_CONFIG,
        "remote_components": ["ejs:github"],
    }
    if get_setting("VID_DL_MARK_WATCHED"):
        opts["mark_watched"] = True
    return opts


def _build_video_format_selector(height: int | None, vfmt: str) -> str:
    h = f"[height={height}]" if height else ""
    if vfmt == "webm":
        # Only allow webm-native streams: VP9/VP8 video + Opus/Vorbis audio.
        # Mixed-codec fallbacks (e.g. VP9+AAC) cannot be stream-copied into webm
        # and would trigger an ffmpeg postprocessing error.
        # If the exact height has no VP9 stream, fall back to the best webm at
        # any height up to the requested height rather than failing entirely.
        lte = f"[height<={height}]" if height else ""
        return (
            f"bestvideo*{h}[ext=webm]+bestaudio[ext=webm]/"
            f"bestvideo*{lte}[ext=webm]+bestaudio[ext=webm]"
        )
    return (
        f"bestvideo*{h}[ext=mp4]+bestaudio[ext=m4a]/"
        f"bestvideo*{h}+bestaudio/"
        f"best{h}/best"
    )


def get_source_options(source: str) -> dict[str, Any]:
    """
    Return yt-dlp properties for a given source type.

    Args:
        source: The download source identifier.

    Returns:
        A dictionary of yt-dlp options specific to the source.
    """
    vfmt = str(get_setting("VID_DL_VIDEO_FORMAT") or "mp4")
    afmt = str(get_setting("VID_DL_AUDIO_FORMAT") or "m4a")
    video_dir = Path(get_setting("VID_DL_VIDEO_STORAGE_DIR") or str(VIDEO_STORAGE_DIR))
    podcast_dir = Path(get_setting("VID_DL_PODCAST_MISC_OUTPUT_DIR") or str(PODCAST_MISC_OUTPUT_DIR))

    source_options = {
        "audio": {
            "format": f"{afmt}/bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": afmt},
            ],
            "outtmpl": (podcast_dir / "%(title)s.%(ext)s").as_posix(),
        },
        "audio_playlists": {
            "format": f"{afmt}/bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": afmt},
            ],
            "outtmpl": (podcast_dir / "%(title)s.%(ext)s").as_posix(),
            "ignoreerrors": "only_download",
        },
        "720playlists": {
            "format": _build_video_format_selector(720, vfmt),
            "merge_output_format": vfmt,
            "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": vfmt}],
            "outtmpl": (
                video_dir
                / "%(playlist)s"
                / "%(playlist_index)s - %(title)s.%(ext)s"
            ).as_posix(),
            "ignoreerrors": "only_download",
        },
        "1080playlists": {
            "format": _build_video_format_selector(1080, vfmt),
            "merge_output_format": vfmt,
            "postprocessors": [{"key": "FFmpegVideoRemuxer", "preferedformat": vfmt}],
            "outtmpl": (
                video_dir
                / "%(playlist)s"
                / "%(playlist_index)s - %(title)s.%(ext)s"
            ).as_posix(),
            "ignoreerrors": "only_download",
        },
    }

    if source in source_options:
        return source_options[source].copy()

    try:
        height = int(source)
    except ValueError:
        height = None

    if height and height > 0:
        format_string = _build_video_format_selector(height, vfmt)
    else:
        format_string = "bestvideo*+bestaudio/best"

    return {
        "format": format_string,
        "merge_output_format": vfmt,
        "outtmpl": (video_dir / "%(title)s.%(ext)s").as_posix(),
        "postprocessors": [
            *DEFAULT_POSTPROCESSORS,
            {"key": "FFmpegVideoRemuxer", "preferedformat": vfmt},
        ],
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
    return get_source_options(source).get(
        "postprocessors", list(DEFAULT_POSTPROCESSORS)
    )
