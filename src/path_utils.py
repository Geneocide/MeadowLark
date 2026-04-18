"""Path and label utilities for robust Windows file handling."""

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

from .logging_utils import log_exception
from .url_utils import extract_playlist_id

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
        pl_id = extract_playlist_id(url)
        if pl_id:
            label = f"playlist-{pl_id}"
        else:
            try:
                segs = [s for s in (urlparse(url).path or "").split("/") if s]
                label = segs[-1] if segs else url
            except (ValueError, AttributeError, TypeError):
                label = url
    return sanitize_for_path(label)


def rename_playlist_folders_from_comments(
    base_output_dir: str,
    urls: list[str],
    playlist_comments: dict[str, str] | None = None,
    direct_playlist_id: str | None = None,
) -> None:
    """Rename 'NA' playlist folders using comment-based names when available.

    Args:
        base_output_dir: Base directory where playlists are downloaded (e.g., "E:/vid storage").
        urls: List of playlist URLs that were downloaded.
        playlist_comments: Dict mapping playlist_id -> comment_text. If None or empty, no renaming.
        direct_playlist_id: Fallback playlist ID to use when urls contain no list= param.
    """
    if not playlist_comments:
        return

    try:
        base_path = Path(base_output_dir)
        if not base_path.exists():
            return

        # Build a mapping of playlist_ids from URLs
        playlist_ids: dict[str, str] = {}
        for url in urls:
            pl_id = extract_playlist_id(url)
            if pl_id:
                playlist_ids[pl_id] = pl_id

        # Fall back to direct_playlist_id when no list= param found in URLs
        if not playlist_ids and direct_playlist_id:
            playlist_ids[direct_playlist_id] = direct_playlist_id

        # Check for 'NA' folder and rename it if we have a matching comment
        na_folder = base_path / "NA"
        if na_folder.exists() and na_folder.is_dir():
            for pl_id in playlist_ids:
                if pl_id in playlist_comments:
                    new_name = sanitize_for_path(playlist_comments[pl_id])
                    new_folder = base_path / new_name
                    try:
                        if not new_folder.exists():
                            na_folder.rename(new_folder)
                            return
                    except (OSError, PermissionError) as exc:
                        log_exception(
                            exc,
                            f"Failed to rename NA folder to {new_name}",
                        )
    except Exception as exc:  # noqa: BLE001
        log_exception(exc, "Error during playlist folder renaming from comments")
