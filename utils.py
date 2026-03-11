import re
from pathlib import Path
from typing import Any

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


# -----------------
# Shared helpers to reduce duplication across the app
# -----------------


def merge_dicts_recursive(base: dict, overrides: dict) -> dict:
    """
    Recursively merge overrides into base without mutating inputs.

    - Dicts are merged recursively
    - Lists are extended when both sides are lists
    - Other values are replaced by overrides
    """

    def _merge(a: Any, b: Any) -> Any:
        if isinstance(a, dict) and isinstance(b, dict):
            out = dict(a)
            for k, v in b.items():
                if k in out:
                    out[k] = _merge(out[k], v)
                else:
                    out[k] = v
            return out
        if isinstance(a, list) and isinstance(b, list):
            return [*a, *b]
        return b if b is not None else a

    return _merge(base, overrides)


def _default_postprocessors() -> list[dict]:
    return [
        {"key": "SponsorBlock"},
        {
            "key": "ModifyChapters",
            "remove_sponsor_segments": ["sponsor", "selfpromo"],
        },
    ]


def remove_sponsorblock_postprocessor(opts: dict) -> dict:
    """
    Return a copy of yt-dlp options with SponsorBlock postprocessing removed.

    This allows downloads to succeed even when SponsorBlock is temporarily
    unavailable (e.g., API 503).
    """
    # Shallow copy to avoid mutating caller's dict
    opts_copy = dict(opts)
    postprocs = opts_copy.get("postprocessors")
    if not isinstance(postprocs, list):
        return opts_copy

    opts_copy["postprocessors"] = [
        pp
        for pp in postprocs
        if not (isinstance(pp, dict) and pp.get("key") == "SponsorBlock")
    ]
    return opts_copy


def build_base_ydl_opts(logger: Any, qhook: Any) -> dict:
    js_runtimes_config = {
        "deno": {
            "path": Path(".venv/Scripts"),
        },
    }
    """Centralize common yt-dlp options used across the app."""
    return {
        "logger": logger,
        "progress_hooks": [qhook],
        "windowsfilenames": True,
        "socket-timeout": 120,
        "max_fragment_retries": 10,
        "mtime": True,
        # Custom match_filter will be set per-source by callers
        "cookiefile": r"resources\cookies.txt",
        "postprocessors": _default_postprocessors(),
        "js_runtimes": js_runtimes_config,
        "remote_components": ["ejs:github"],
    }


def detect_site_from_urls(urls: list[str]) -> str:
    """Best-effort detection of site from a list of URLs."""
    all_urls = " ".join(urls or []).lower()
    if "youtube.com" in all_urls or "youtu.be" in all_urls:
        return "youtube"
    if "nebula" in all_urls or "watchnebula" in all_urls:
        return "nebula"
    return "unknown"


def is_primitive_technology(info: dict) -> bool:
    """
    Detect Primitive Technology channel videos.

    Prefer exact channel/uploader detection when available, and fall back to
    checking the common title prefix 'Primitive Technology:' when metadata is limited.
    """
    try:
        # Channel/uploader info when available
        channel = (info.get("channel") or info.get("channel_id") or "").lower()
        uploader = (info.get("uploader") or info.get("uploader_id") or "").lower()
        if "primitive technology" in channel or "primitive technology" in uploader:
            return True
        # Fallback on the well-known title prefix (case-insensitive, robust to whitespace)
        title = (info.get("title") or "").strip().lower()
        if title.startswith("primitive technology:"):
            return True
    except Exception:
        return False
    return False


def get_playlist_file_for_source(source: str) -> str | None:
    """Return the on-disk playlist file path for a given source key, if any."""
    mapping = {
        "1080playlists": r"Z:\\misc\\dev\\vid downloader\\resources\\playlists\\playlists.txt",
        "720playlists": r"Z:\\misc\\dev\\vid downloader\\resources\\playlists\\720playlists.txt",
        "audio_playlists": r"Z:\\misc\\dev\\vid downloader\\resources\\playlists\\audio playlists.txt",
    }
    return mapping.get(source)


# -----------------
# Path/label helpers for robust audio playlist handling
# -----------------
import hashlib
import os
from urllib.parse import parse_qs, urlparse

WINDOWS_INVALID = '<>:"/\\|?*'


essential_whitespace_re = re.compile(r"\s+")


def sanitize_for_path(name: str) -> str:
    """Return a Windows-safe folder/file component, or 'misc' if empty."""
    if not name:
        return "misc"
    table = str.maketrans(dict.fromkeys(WINDOWS_INVALID, "_"))
    cleaned = name.translate(table)
    # Remove control chars
    cleaned = re.sub(r"[\x00-\x1f]", "_", cleaned)
    # Collapse whitespace, strip trailing dots/spaces
    cleaned = essential_whitespace_re.sub(" ", cleaned).strip().rstrip(".")
    return cleaned or "misc"


def slugify_if_too_long(
    base_dir: str,
    playlist_label: str,
    filename_hint: str = "%(title)s.%(ext)s",
    max_total: int = 240,
) -> str:
    """
    If the full path might exceed a safe Windows max, replace the label with a short slug.

    Windows MAX_PATH is ~260; we keep a margin for long titles at runtime.
    """
    label = sanitize_for_path(playlist_label)
    tentative = os.path.join(base_dir, label, filename_hint)
    if len(tentative) <= max_total:
        return label
    base = re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-")[:40]
    h = hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]
    slug = f"{base}-{h}" if base else h
    return slug or "misc"


def resolve_playlist_label(info: dict, url: str) -> str:
    """Derive a human-friendly playlist label from yt-dlp info or URL."""
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
        except Exception:
            label = url
    return sanitize_for_path(label)
