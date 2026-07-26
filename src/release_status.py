"""Classification and time handling for downloads that are announced but not yet released."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Final

NOT_YET_RELEASED_MARKERS: Final[tuple[str, ...]] = (
    "premieres in",
    "premieres on",
    "premiere will begin in",
    "this live event will begin in",
    "live event will begin in",
    "this video will be available",
    "video will begin in",
)
"""Lowercased substrings of yt-dlp error text meaning "announced, not yet available".

These come from YouTube's own ``playabilityStatus.reason``, surfaced verbatim by
``raise_no_formats`` in yt_dlp/extractor/youtube/_video.py. Extraction fails before any
info_dict exists, so the app's match_filter never gets a chance to park the item -- the
error string is the only signal available.
"""

_RELATIVE_RE: Final = re.compile(
    r"\bin\s+(?P<count>\d+)\s+(?P<unit>second|minute|hour|day|week|month)s?\b",
    re.IGNORECASE,
)

_UNIT_SECONDS: Final[dict[str, int]] = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
    "day": 86400,
    "week": 604800,
    "month": 2592000,  # 30 days; YouTube never renders months for near-term premieres
}


def is_not_yet_released(error: str | None) -> bool:
    """Return True when an error message means the item exists but has not aired yet."""
    if not error:
        return False
    lowered = error.lower()
    return any(marker in lowered for marker in NOT_YET_RELEASED_MARKERS)


def parse_relative_release(text: str | None, now: datetime | None = None) -> datetime | None:
    """
    Best-effort aware datetime from an "in N <unit>" phrase, e.g. "Premieres in 6 hours".

    Coarse by design -- it exists only so the UI has something to show before the first
    metadata probe replaces it with the exact ``release_timestamp``. Returns None when no
    relative phrase is present (e.g. "Premieres on Jul 30, 2026"), and also when the count
    is absurdly large (YouTube's own text is untrusted input here -- a bogus multi-digit
    count must not crash the app via ``timedelta``/``datetime`` overflow).
    """
    if not text:
        return None
    match = _RELATIVE_RE.search(text)
    if not match:
        return None
    seconds = int(match.group("count")) * _UNIT_SECONDS[match.group("unit").lower()]
    base = now or datetime.now().astimezone()
    if base.tzinfo is None:
        base = base.astimezone()
    try:
        return base + timedelta(seconds=seconds)
    except OverflowError:
        return None


def release_at_from_timestamp(timestamp: float | None) -> str | None:
    """Convert yt-dlp's POSIX ``release_timestamp`` to a local ISO-8601 string with offset."""
    if timestamp is None:
        return None
    try:
        aware_utc = datetime.fromtimestamp(float(timestamp), tz=UTC)
    except (OverflowError, OSError, TypeError, ValueError):
        return None
    return aware_utc.astimezone().isoformat(timespec="seconds")


def to_release_at(value: datetime | None) -> str | None:
    """Serialize an aware datetime to the store's ISO-8601 form; naive input is localized."""
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.astimezone()
    return aware.isoformat(timespec="seconds")


def parse_release_at(value: str | None) -> datetime | None:
    """Parse a stored ISO-8601 release time back to an aware datetime; None if unparseable."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo is not None else parsed.astimezone()


def format_release_at(value: str | None, now: datetime | None = None) -> str:
    """
    Render a stored release time for display, e.g. "2026-07-26 21:00 (in 5h 42m)".

    Returns "(time unknown)" when nothing is stored and "(due now)" once the time has passed.
    """
    parsed = parse_release_at(value)
    if parsed is None:
        return "(time unknown)"
    reference = now or datetime.now().astimezone()
    if reference.tzinfo is None:
        reference = reference.astimezone()
    stamp = parsed.strftime("%Y-%m-%d %H:%M")
    remaining = parsed - reference
    if remaining.total_seconds() <= 0:
        return f"{stamp} (due now)"
    total_minutes = int(remaining.total_seconds() // 60)
    days, rem_minutes = divmod(total_minutes, 1440)
    hours, minutes = divmod(rem_minutes, 60)
    if days:
        return f"{stamp} (in {days}d {hours}h)"
    if hours:
        return f"{stamp} (in {hours}h {minutes}m)"
    return f"{stamp} (in {minutes}m)"
