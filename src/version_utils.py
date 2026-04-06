"""Version checking and comparison utilities for yt-dlp."""

import re

import requests
import yt_dlp


def normalize_version(version: str) -> tuple[int, ...]:
    """
    Normalize a version string like '2025.08.27' or '2025.8.27' to a tuple of ints.

    Args:
        version: Version string to normalize (e.g., '2025.08.27').

    Returns:
        Tuple of integers, e.g., (2025, 8, 27). Returns empty tuple if not a string.
    """
    if not isinstance(version, str):
        return ()
    # Match all dot-separated numeric sequences
    parts = re.findall(r"\d+", version)
    return tuple(int(x) for x in parts)


def get_current_yt_dlp_version() -> str | None:
    """
    Safely get the installed yt-dlp version.

    Returns:
        Version string (e.g., '2025.08.27') or None if unable to determine.
    """
    try:
        try:
            return yt_dlp.version.__version__
        except AttributeError:
            return yt_dlp.__version__
    except ImportError:
        return None


def get_latest_yt_dlp_version() -> str | None:
    """
    Fetch the latest yt-dlp version from PyPI.

    Returns:
        Latest version string or None if unable to fetch.
    """
    try:
        r = requests.get("https://pypi.org/pypi/yt-dlp/json", timeout=3)
        if r.status_code == 200:  # noqa: PLR2004
            return r.json()["info"]["version"]
        return None  # noqa: TRY300
    except requests.exceptions.RequestException:
        return None


def is_yt_dlp_update_available() -> tuple[
    bool, tuple[int, ...] | None, tuple[int, ...] | None
]:
    """
    Check whether a newer yt-dlp version is available.

    Returns:
        Tuple of (update_available: bool, current_version: tuple, latest_version: tuple).
    """
    current = normalize_version(get_current_yt_dlp_version() or "")
    latest = normalize_version(get_latest_yt_dlp_version() or "")
    update = (current and latest) and (current != latest)
    return update, current if current else None, latest if latest else None
