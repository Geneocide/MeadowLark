"""Path and label utilities for robust Windows file handling."""

import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .logging_utils import log_exception

# Constants for path sanitization
WINDOWS_INVALID_CHARS = '<>:"/\\|?*'
MIN_SLUG_LEN = 40
REQUIRED_FIELD_COUNT = 2  # for URL parts parsing
MAX_PATH_LENGTH = 240
HASH_LENGTH = 8

# Regex for collapsing whitespace
ESSENTIAL_WHITESPACE_RE = re.compile(r"\s+")


def sanitize_for_path(name: str) -> str:
    """
    Return a Windows-safe folder/file component.

    Args:
        name: Directory or file name to sanitize.

    Returns:
        Sanitized name safe for Windows paths, or 'misc' if empty.
    """
    if not name:
        return "misc"
    table = str.maketrans(dict.fromkeys(WINDOWS_INVALID_CHARS, "_"))
    cleaned = name.translate(table)
    # Remove control chars
    cleaned = re.sub(r"[\x00-\x1f]", "_", cleaned)
    # Collapse whitespace, strip trailing dots/spaces
    cleaned = ESSENTIAL_WHITESPACE_RE.sub(" ", cleaned).strip().rstrip(".")
    return cleaned or "misc"


def slugify_if_too_long(
    base_dir: str,
    playlist_label: str,
    filename_hint: str = "%(title)s.%(ext)s",
    max_total: int = MAX_PATH_LENGTH,
) -> str:
    """
    If the full path might exceed a safe Windows max, replace the label with a short slug.

    Windows MAX_PATH is ~260; we keep a margin for long titles at runtime.

    Args:
        base_dir: Base directory path.
        playlist_label: Human-readable playlist label.
        filename_hint: Template for filename (default: "%(title)s.%(ext)s").
        max_total: Maximum allowed path length (default: 240).

    Returns:
        Safe label that keeps full path under max_total, or a hash-based slug.
    """
    label = sanitize_for_path(playlist_label)
    tentative = str(Path(base_dir) / label / filename_hint)
    if len(tentative) <= max_total:
        return label
    base = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-")[:MIN_SLUG_LEN]
    h = hashlib.sha1(label.encode("utf-8")).hexdigest()[:HASH_LENGTH]  # noqa: S324
    slug = f"{base}-{h}" if base else h
    return slug or "misc"


def resolve_playlist_label(info: dict, url: str) -> str:
    """
    Derive a human-friendly playlist label from yt-dlp info or URL.

    Args:
        info: yt-dlp info dictionary potentially containing title or uploader.
        url: Playlist URL as fallback for label derivation.

    Returns:
        Sanitized label suitable for use as a folder name.
    """
    label = info.get("title") or info.get("uploader")
    if not label:
        try:
            u = urlparse(url)
            qs = parse_qs(u.query or "")
            if qs.get("list"):
                label = f"playlist-{qs['list'][0]}"
            else:
                segs = [s for s in (u.path or "").split("/") if s]
                label = segs[-1] if segs else url
        except (ValueError, AttributeError, TypeError) as exc:
            log_exception(exc, "Failed to resolve playlist label from URL")
            label = url
    return sanitize_for_path(label)
