"""Centralized configuration management for paths and constants with environment variable fallbacks."""

import os
from pathlib import Path
from typing import Final

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
COOKIES_FILE: Final[Path] = RESOURCES_DIR / "cookies.txt"
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

# JavaScript runtime configuration
VENV_SCRIPTS_DIR: Final[Path] = _resolve_path("VID_DL_VENV_SCRIPTS", ".venv/Scripts")

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

# ============================================================================
# Display Configuration
# ============================================================================

LABEL_OUTPUT_FONT_NAME: Final[str] = os.getenv("VID_DL_LABEL_OUTPUT_FONT", "Arial")
LABEL_OUTPUT_FONT_SIZE: Final[int] = int(
    os.getenv("VID_DL_LABEL_OUTPUT_FONT_SIZE", "16"),
)
LABEL_READY_TEXT: Final[str] = os.getenv("VID_DL_LABEL_READY_TEXT", "[ Ready ]")

# ============================================================================
# Post-Processing Configuration
# ============================================================================

DEFAULT_MERGE_OUTPUT_FORMAT: Final[str] = os.getenv(
    "VID_DL_MERGE_OUTPUT_FORMAT",
    "mp4",
)

# ============================================================================
# Debug Configuration
# ============================================================================

LOGFILE_MIGRATION_ENABLED: Final[bool] = (
    os.getenv("VID_DL_LOGFILE_MIGRATION", "true").lower() == "true"
)
