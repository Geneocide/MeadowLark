"""Centralized configuration management for paths and constants with environment variable fallbacks."""

import os
import sys
from pathlib import Path
from subprocess import SubprocessError
from typing import Final

# ============================================================================
# Exception Constants
# ============================================================================
# Import yt-dlp exceptions for consistent error handling
from yt_dlp.utils import DownloadError, ExtractorError, MaxDownloadsReached

# Exception tuples for consistent error handling across the application.
# SubprocessError covers the helper processes yt-dlp shells out to mid-extraction
# -- notably the bgutil PO-token provider's Deno probe, which yt-dlp gives a hard
# 15s budget and which overruns it whenever Deno has to re-resolve the provider's
# npm deps over the network. That surfaces as subprocess.TimeoutExpired escaping
# ydl.download(); it is a failed download, not a bug in the app, so it must be
# caught wherever the yt-dlp errors are.
YDL_COMMON_ERRORS: Final = (DownloadError, ExtractorError, OSError, SubprocessError)
YDL_EXTRACTION_ERRORS: Final = (
    DownloadError,
    ExtractorError,
    OSError,
    SubprocessError,
    ValueError,
)
YDL_DOWNLOAD_ERRORS: Final = (
    DownloadError,
    ExtractorError,
    MaxDownloadsReached,
    OSError,
    SubprocessError,
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
FAILED_DOWNLOADS_FILE: Final[Path] = RESOURCES_DIR / "failed_downloads.json"
# Deferred downloads: live streams parked by match_filter plus premieres that were
# announced but had not aired at download time (see src/pending_queue.py). Supersedes
# LIVE_QUEUE_FILE, which is now read once and migrated.
PENDING_QUEUE_FILE: Final[Path] = RESOURCES_DIR / "pending_queue.json"

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

# Make the bundled Deno runtime discoverable on PATH. The yt-dlp PO-token
# provider (bgutil, script mode) locates node/deno via PATH, not via yt-dlp's
# js_runtimes. When the app is launched with pythonw.exe WITHOUT activating the
# venv, .venv/Scripts is not on PATH, so the provider silently becomes
# unavailable and 1080p downloads regress to HTTP 403 (see YOUTUBE_PLAYER_CLIENTS
# below). Prepend the (absolute) scripts dir once, only if it really exists.
_scripts_abs = str(VENV_SCRIPTS_DIR.resolve())
if VENV_SCRIPTS_DIR.exists() and _scripts_abs not in os.environ.get("PATH", "").split(
    os.pathsep
):
    os.environ["PATH"] = _scripts_abs + os.pathsep + os.environ.get("PATH", "")

# ============================================================================
# yt-dlp extractor behavior
# ============================================================================

# YouTube gates 1080p+ media URLs behind a per-video "GVS PO token" (SABR
# experiment, yt-dlp #12482), enforced per video on a rolling basis: a flagged
# video 403s on every tokenless URL for hours-to-days while others download
# fine. The bgutil provider (script mode via the bundled Deno runtime) mints
# that token, but only clients that *consume* it emit media URLs carrying
# "pot=". As of 2026-07, "web_safari" no longer qualifies -- YouTube forces
# SABR on it, so its https formats are skipped ("missing a URL") and every
# served format silently came from "tv", whose URLs carry NO token and 403 on
# flagged videos. "mweb" both requires and consumes the GVS token (the PO Token
# Guide's recommended client), so it is listed FIRST; "tv" stays as a tokenless
# fallback for formats mweb lacks. WITHOUT the provider, every 1080p download
# 403s regardless of client order -- reordering clients or clearing caches
# cannot substitute for the token.
# Order matters: the first client that supplies a given format id wins. Override
# with VID_DL_YT_PLAYER_CLIENT (comma-separated, in priority order).
YOUTUBE_PLAYER_CLIENTS: Final[str] = os.getenv(
    "VID_DL_YT_PLAYER_CLIENT", "mweb,tv"
)

# PO Token provider (bgutil "script-deno" mode) server home. In script mode the
# provider looks for {server_home}/src/generate_once.ts and {server_home}/
# node_modules (see yt_dlp_plugins.extractor.getpot_bgutil_script). The default is
# the vendored copy under vendor/bgutil-pot-provider/server (dev), or the bundled
# "bgutil-server" dir inside the PyInstaller bundle (frozen). node_modules is
# generated by scripts/setup_pot_provider.py. Override with VID_DL_POT_SERVER_HOME.
if getattr(sys, "frozen", False):
    _pot_default_home: Path = Path(sys._MEIPASS) / "bgutil-server"  # type: ignore[attr-defined]
else:
    _pot_default_home = (
        Path(__file__).parent.parent / "vendor" / "bgutil-pot-provider" / "server"
    )
POT_PROVIDER_SERVER_HOME: Final[Path] = _resolve_path(
    "VID_DL_POT_SERVER_HOME", _pot_default_home,
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
MARK_WATCHED: Final[bool] = (
    os.getenv("VID_DL_MARK_WATCHED", "false").lower() == "true"
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
