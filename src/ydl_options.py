"""Centralized yt-dlp option builders and constants."""

from pathlib import Path
from typing import Any

from .dict_utils import _default_postprocessors

# Constants for yt-dlp configuration
HTTP_TIMEOUT_SECONDS = 120
MAX_FRAGMENT_RETRIES = 10
SOCKET_TIMEOUT_SECONDS = 120

# JavaScript runtimes configuration
JS_RUNTIMES_CONFIG = {
    "deno": {
        "path": Path(".venv/Scripts"),
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
        "cookiefile": r"resources\cookies.txt",
        "postprocessors": _default_postprocessors(),
        "js_runtimes": JS_RUNTIMES_CONFIG,
        "remote_components": ["ejs:github"],
    }
