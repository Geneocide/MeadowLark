"""URL parsing utilities."""

from urllib.parse import parse_qs, urlparse


def extract_playlist_id(url: str) -> str | None:
    """Return the YouTube playlist ID from a URL's `list` query parameter, or None."""
    try:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query or "")
        ids = qs.get("list")
        return ids[0] if ids else None
    except (ValueError, AttributeError, TypeError):
        return None
