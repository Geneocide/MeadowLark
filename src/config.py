"""Centralized configuration management for paths and constants with environment variable fallbacks."""

import os
import sys
from pathlib import Path
from typing import Final

# ============================================================================
# Exception Constants
# ============================================================================
# Import yt-dlp exceptions for consistent error handling
from yt_dlp.utils import DownloadError, ExtractorError, MaxDownloadsReached

# Exception tuples for consistent error handling across the application
YDL_COMMON_ERRORS: Final = (DownloadError, ExtractorError, OSError)
YDL_EXTRACTION_ERRORS: Final = (DownloadError, ExtractorError, OSError, ValueError)
YDL_DOWNLOAD_ERRORS: Final = (
    DownloadError,
    ExtractorError,
    MaxDownloadsReached,
    OSError,
    ValueError,
)

# ============================================================================
# Path Configuration
# ============================================================================


def _resolve_path(env_var: str, default: str | Path) -> Path:
    """
    Resolve a path from environment variable with fallback to default.

    Args:
        env_var: Environment variable name to check.
        default: Default path if env var not set.

    Returns:
        Resolved Path object.
    """
    env_value = os.getenv(env_var)
    if env_value:
        return Path(env_value)
    return Path(default)


# Log files
ERROR_LOG_PATH: Final[Path] = _resolve_path("VID_DL_ERROR_LOG", "error_log.txt")
HISTORY_LOG_PATH: Final[Path] = _resolve_path("VID_DL_HISTORY_LOG", "history_log.txt")

# Resource directories and files
RESOURCES_DIR: Final[Path] = _resolve_path("VID_DL_RESOURCES_DIR", "resources")
COOKIES_FILE: Final[Path] = _resolve_path(
    "VID_DL_COOKIES_FILE", RESOURCES_DIR / "cookies.txt"
)
LIVE_QUEUE_FILE: Final[Path] = RESOURCES_DIR / "live_queue.txt"

# Playlist files
PLAYLISTS_DIR: Final[Path] = RESOURCES_DIR / "playlists"
PLAYLISTS_FILE: Final[Path] = _resolve_path(
    "VID_DL_PLAYLISTS_FILE",
    PLAYLISTS_DIR / "playlists.txt",
)
PLAYLISTS_720_FILE: Final[Path] = _resolve_path(
    "VID_DL_PLAYLISTS_720_FILE",
    PLAYLISTS_DIR / "720playlists.txt",
)
PLAYLISTS_AUDIO_FILE: Final[Path] = _resolve_path(
    "VID_DL_PLAYLISTS_AUDIO_FILE",
    PLAYLISTS_DIR / "audio playlists.txt",
)

# External storage paths
ARCHIVE_PATH: Final[Path] = _resolve_path(
    "VID_DL_ARCHIVE_PATH",
    Path(__file__).parent.parent / "resources" / "archive.txt",
)
PODCAST_MISC_OUTPUT_DIR: Final[Path] = _resolve_path(
    "VID_DL_PODCAST_MISC_OUTPUT_DIR",
    Path.home() / "Music" / "Podcasts",
)
VIDEO_STORAGE_DIR: Final[Path] = _resolve_path(
    "VID_DL_VIDEO_STORAGE_DIR",
    Path.home() / "Videos",
)

# JavaScript runtime configuration
if getattr(sys, "frozen", False):
    VENV_SCRIPTS_DIR: Final[Path] = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    VENV_SCRIPTS_DIR: Final[Path] = _resolve_path(
        "VID_DL_VENV_SCRIPTS", ".venv/Scripts"
    )

# ============================================================================
# Timeout Configuration (seconds)
# ============================================================================

HTTP_TIMEOUT_SECONDS: Final[int] = int(
    os.getenv("VID_DL_HTTP_TIMEOUT", "120"),
)
SOCKET_TIMEOUT_SECONDS: Final[int] = int(
    os.getenv("VID_DL_SOCKET_TIMEOUT", "120"),
)

# HTTP request timeout for external API calls (e.g., SponsorBlock)
HTTP_REQUEST_TIMEOUT_SECONDS: Final[int] = int(
    os.getenv("VID_DL_HTTP_REQUEST_TIMEOUT", "5"),
)

# ============================================================================
# Download Configuration
# ============================================================================

MAX_FRAGMENT_RETRIES: Final[int] = int(
    os.getenv("VID_DL_MAX_FRAGMENT_RETRIES", "10"),
)

# HTTP status code
HTTP_OK: Final[int] = 200

# ============================================================================
# Podcast Configuration
# ============================================================================

# Minimum duration for podcast episodes (seconds)
PODCAST_MIN_DURATION_SECONDS: Final[int] = int(
    os.getenv("VID_DL_PODCAST_MIN_DURATION_SECONDS", "180"),
)

# SponsorBlock cache TTL (hours)
SPONSORBLOCK_CACHE_TTL_HOURS: Final[int] = int(
    os.getenv("VID_DL_SPONSORBLOCK_CACHE_TTL_HOURS", "6"),
)

# Live queue check interval (minutes)
LIVE_QUEUE_CHECK_INTERVAL_MINUTES: Final[int] = int(
    os.getenv("VID_DL_LIVE_QUEUE_CHECK_INTERVAL_MINUTES", "30"),
)

# Maximum attempts to fetch the latest accessible playlist entry
PODCAST_LOOKAHEAD_MAX_ATTEMPTS: Final[int] = int(
    os.getenv("VID_DL_PODCAST_LOOKAHEAD_MAX_ATTEMPTS", "5"),
)

PODCAST_AUTO_CHECK: Final[bool] = (
    os.getenv("VID_DL_PODCAST_AUTO_CHECK", "true").lower() == "true"
)
ALWAYS_ON_TOP: Final[bool] = (
    os.getenv("VID_DL_ALWAYS_ON_TOP", "true").lower() == "true"
)
APP_UPDATE_AUTO_CHECK: Final[bool] = (
    os.getenv("VID_DL_APP_UPDATE_AUTO_CHECK", "true").lower() == "true"
)
APP_UPDATE_LAST_CHECKED: Final[str] = os.getenv("VID_DL_APP_UPDATE_LAST_CHECKED", "")
PODCAST_CHECK_INTERVAL_MINUTES: Final[int] = int(
    os.getenv("VID_DL_PODCAST_CHECK_INTERVAL_MINUTES", "60"),
)

# ============================================================================
# Display Configuration
# ============================================================================

LABEL_OUTPUT_FONT_NAME: Final[str] = os.getenv("VID_DL_LABEL_OUTPUT_FONT", "Arial")
LABEL_OUTPUT_FONT_SIZE: Final[int] = int(
    os.getenv("VID_DL_LABEL_OUTPUT_FONT_SIZE", "16"),
)
LABEL_READY_TEXT: Final[str] = os.getenv("VID_DL_LABEL_READY_TEXT", "[ Ready ]")
LABEL_DROP_1080: Final[str] = os.getenv("VID_DL_LABEL_DROP_1080", "1080")
LABEL_DROP_720: Final[str] = os.getenv("VID_DL_LABEL_DROP_720", "720")
LABEL_DROP_AUDIO: Final[str] = os.getenv("VID_DL_LABEL_DROP_AUDIO", "audio")
LABEL_BTN_PLAYLISTS: Final[str] = os.getenv("VID_DL_LABEL_BTN_PLAYLISTS", "Playlists")
LABEL_BTN_720: Final[str] = os.getenv("VID_DL_LABEL_BTN_720", "720 Playlists")
LABEL_BTN_PODCASTS: Final[str] = os.getenv("VID_DL_LABEL_BTN_PODCASTS", "YT Podcasts")

# ============================================================================
# Post-Processing Configuration
# ============================================================================

DEFAULT_MERGE_OUTPUT_FORMAT: Final[str] = os.getenv(
    "VID_DL_MERGE_OUTPUT_FORMAT",
    "mp4",
)
DEFAULT_VIDEO_FORMAT: Final[str] = os.getenv("VID_DL_VIDEO_FORMAT", "mp4")
DEFAULT_AUDIO_FORMAT: Final[str] = os.getenv("VID_DL_AUDIO_FORMAT", "m4a")

# ============================================================================
# Debug Configuration
# ============================================================================

LOGFILE_MIGRATION_ENABLED: Final[bool] = (
    os.getenv("VID_DL_LOGFILE_MIGRATION", "true").lower() == "true"
)
