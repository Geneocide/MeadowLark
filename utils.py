import re

import requests
import yt_dlp


def normalize_version(version: str) -> tuple:
    """
    Normalize a version string like '2025.08.27' or '2025.8.27' to a tuple of ints, e.g., (2025, 8, 27).

    Non-integer parts will be handled as zeroes.
    """
    if not isinstance(version, str):
        return ()
    # Match all dot-separated numeric sequences
    parts = re.findall(r"\d+", version)
    return tuple(int(x) for x in parts)


def get_current_yt_dlp_version() -> str | None:
    """Safely gets the installed yt-dlp version."""
    try:
        try:
            return yt_dlp.version.__version__
        except AttributeError:
            return yt_dlp.__version__
    except ImportError:
        return None


def get_latest_yt_dlp_version() -> str | None:
    """Fetch the latest yt-dlp version from PyPI."""
    try:
        r = requests.get("https://pypi.org/pypi/yt-dlp/json", timeout=3)
        if r.status_code == 200:  # noqa: PLR2004
            return r.json()["info"]["version"]
        return None  # noqa: TRY300
    except requests.exceptions.RequestException:
        return None


def is_yt_dlp_update_available() -> tuple[bool, str | None, str | None]:
    """
    Check whether a newer yt-dlp version is available.

    Returns:
        (update_available: bool, current_version: str, latest_version: str)
    """
    current = normalize_version(get_current_yt_dlp_version())
    latest = normalize_version(get_latest_yt_dlp_version())
    update = (current is not None) and (latest is not None) and (current != latest)
    return update, current, latest
