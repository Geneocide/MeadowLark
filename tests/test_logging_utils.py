"""Tests for src.logging_utils module."""

import re
from datetime import datetime, timezone

from src.logging_utils import get_utc_timestamp


class TestGetUtcTimestamp:
    """Tests for get_utc_timestamp() function."""

    def test_returns_string(self) -> None:
        """get_utc_timestamp() should return a string."""
        result = get_utc_timestamp()
        assert isinstance(result, str)

    def test_format_is_correct(self) -> None:
        """get_utc_timestamp() should return string in format 'YYYY-MM-DD HH:MM:SS'."""
        result = get_utc_timestamp()
        # Verify format with regex: YYYY-MM-DD HH:MM:SS
        pattern = r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$"
        assert re.match(pattern, result), (
            f"Timestamp {result} does not match expected format"
        )

    def test_timestamp_is_recent(self) -> None:
        """get_utc_timestamp() should return current time (within 1 second)."""
        before = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        result = get_utc_timestamp()
        after = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        # Result should be between before and after (allowing for rounding)
        assert before <= result <= after, (
            f"Timestamp {result} not within expected range ({before} to {after})"
        )

    def test_called_twice_increases_or_stays_same(self) -> None:
        """Sequential calls to get_utc_timestamp() should be in ascending order."""
        timestamp1 = get_utc_timestamp()
        timestamp2 = get_utc_timestamp()

        # Since both are formatted strings, simple string comparison works
        # (YYYY-MM-DD HH:MM:SS format is lexicographically sortable)
        assert timestamp1 <= timestamp2, (
            f"First timestamp {timestamp1} should be <= second timestamp {timestamp2}"
        )
