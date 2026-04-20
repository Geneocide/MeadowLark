"""Unit tests for podcast_filtering helpers."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from src.podcast_filtering import (
    PODCAST_MIN_DURATION_SECONDS,
    _try_parse_datetime,
    append_to_archive_and_mark_skipped,
    check_sponsorblock_for_video_id,
    format_timestamp_readable,
    load_downloaded_video_ids,
    parse_scheduled_time_from_error,
    parse_video_timestamp,
)


def test_parse_video_timestamp_uses_timestamp_field() -> None:
    entry = {"timestamp": 1710920000.0, "upload_date": "20240301"}
    assert parse_video_timestamp(entry) == 1710920000.0


def test_parse_video_timestamp_uses_upload_date_as_fallback() -> None:
    entry = {"upload_date": "20240301"}
    result = parse_video_timestamp(entry)
    assert isinstance(result, float)
    assert (
        datetime.fromtimestamp(result, tz=timezone.utc).strftime("%Y%m%d") == "20240301"
    )


def test_parse_video_timestamp_invalid_upload_date_returns_none() -> None:
    entry = {"upload_date": "invalid"}
    assert parse_video_timestamp(entry) is None


def test_format_timestamp_readable_unknown() -> None:
    assert format_timestamp_readable(None) == "(unknown)"


def test_format_timestamp_readable_valid() -> None:
    ts = datetime(2024, 3, 1, tzinfo=timezone.utc).timestamp()
    assert format_timestamp_readable(ts) == "2024-03-01"


def test_load_downloaded_video_ids_none_path() -> None:
    assert load_downloaded_video_ids(None) == set()


def test_load_downloaded_video_ids_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.txt"
    assert not missing_file.exists()
    assert load_downloaded_video_ids(str(missing_file)) == set()


def test_load_downloaded_video_ids_reads_ids(tmp_path: Path) -> None:
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text("youtube abc123\nothers 456def\n")
    ids = load_downloaded_video_ids(str(archive_file))
    assert ids == {"abc123", "456def"}


def test_parse_scheduled_time_from_error_primetime() -> None:
    err = "This live event will begin in 2 hours"
    ts = parse_scheduled_time_from_error(err)
    assert ts is not None
    assert ts > datetime.now(tz=timezone.utc).timestamp()


def test_parse_scheduled_time_from_error_scheduled() -> None:
    err = "This stream is scheduled to begin 2025-12-25 10:00"
    ts = parse_scheduled_time_from_error(err)
    assert ts is not None


def test_parse_scheduled_time_from_error_invalid() -> None:
    err = "Unknown error message"
    assert parse_scheduled_time_from_error(err) is None


@patch("src.podcast_filtering.requests.get")
def test_check_sponsorblock_for_video_id_has_segments(mock_get: Mock) -> None:
    mock_response = mock_get.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = [{"start": 0, "end": 10}]
    assert check_sponsorblock_for_video_id("abc123") is True


@patch("src.podcast_filtering.requests.get")
def test_check_sponsorblock_for_video_id_no_segments(mock_get: Mock) -> None:
    mock_response = mock_get.return_value
    mock_response.status_code = 200
    mock_response.json.return_value = []
    assert check_sponsorblock_for_video_id("abc123") is False


@patch("src.podcast_filtering.requests.get")
def test_check_sponsorblock_for_video_id_api_error(mock_get: Mock) -> None:
    mock_get.side_effect = Exception("Network error")
    assert check_sponsorblock_for_video_id("abc123") is False


def test_append_to_archive_and_mark_skipped_default_reason(tmp_path: Path) -> None:
    """Test that default reason is 'Update exception'."""
    archive_file = tmp_path / "archive.txt"
    existing_ids: set[str] = set()
    messages: list[str] = []

    append_to_archive_and_mark_skipped(
        str(archive_file),
        "vid123",
        existing_ids,
        "Test Video (Update)",
        messages,
    )

    # Check video was archived
    assert "vid123" in existing_ids
    content = archive_file.read_text()
    assert "youtube vid123" in content

    # Check message contains default reason
    assert len(messages) == 1
    assert "Update exception" in messages[0]
    assert "Test Video (Update)" in messages[0]


def test_append_to_archive_and_mark_skipped_custom_reason(tmp_path: Path) -> None:
    """Test that custom reason is used in log message."""
    archive_file = tmp_path / "archive.txt"
    existing_ids: set[str] = set()
    messages: list[str] = []

    append_to_archive_and_mark_skipped(
        str(archive_file),
        "vid456",
        existing_ids,
        "Short Episode",
        messages,
        reason="Short duration (<3 min)",
    )

    # Check video was archived
    assert "vid456" in existing_ids
    content = archive_file.read_text()
    assert "youtube vid456" in content

    # Check message contains custom reason
    assert len(messages) == 1
    assert "Short duration (<3 min)" in messages[0]
    assert "Short Episode" in messages[0]


def test_append_to_archive_and_mark_skipped_none_archive() -> None:
    """Test that it works without an archive path."""
    existing_ids: set[str] = set()
    messages: list[str] = []

    append_to_archive_and_mark_skipped(
        None,
        "vid789",
        existing_ids,
        "Test Video",
        messages,
        reason="Test reason",
    )

    # Check video was NOT added to existing_ids (since no archive)
    assert "vid789" not in existing_ids

    # Check message was still logged
    assert len(messages) == 1
    assert "Test reason" in messages[0]


def test_append_to_archive_and_mark_skipped_deduplication(tmp_path: Path) -> None:
    """Test that duplicates are not re-archived."""
    archive_file = tmp_path / "archive.txt"
    existing_ids = {"vid999"}
    messages: list[str] = []

    append_to_archive_and_mark_skipped(
        str(archive_file),
        "vid999",
        existing_ids,
        "Duplicate Video",
        messages,
        reason="Test",
    )

    # Check message was logged
    assert len(messages) == 1

    # Check archive is empty (deduplication worked)
    content = archive_file.read_text()
    assert content == ""  # File should not be written to


def test_podcast_min_duration_seconds_constant() -> None:
    """Test that the duration threshold constant is set correctly."""
    assert PODCAST_MIN_DURATION_SECONDS == 180


# ---------------------------------------------------------------------------
# load_downloaded_video_ids — blank lines and OSError (lines 69, 73-74)
# ---------------------------------------------------------------------------


def test_load_downloaded_video_ids_skips_blank_lines(tmp_path: Path) -> None:
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text("youtube abc123\n\nyoutube def456\n\n")
    ids = load_downloaded_video_ids(str(archive_file))
    assert ids == {"abc123", "def456"}


def test_load_downloaded_video_ids_oserror_returns_empty(tmp_path: Path) -> None:
    archive_file = tmp_path / "archive.txt"
    archive_file.write_text("youtube abc123\n")
    with patch("pathlib.Path.open", side_effect=OSError("permission denied")):
        result = load_downloaded_video_ids(str(archive_file))
    assert result == set()


# ---------------------------------------------------------------------------
# format_timestamp_readable — OSError/ValueError branch (lines 97-98)
# ---------------------------------------------------------------------------


def test_format_timestamp_readable_oserror_returns_unknown() -> None:
    with patch("src.podcast_filtering.datetime") as mock_dt:
        mock_dt.fromtimestamp.side_effect = OSError("invalid ts")
        result = format_timestamp_readable(12345.0)
    assert result == "(unknown)"


def test_format_timestamp_readable_value_error_returns_unknown() -> None:
    with patch("src.podcast_filtering.datetime") as mock_dt:
        mock_dt.fromtimestamp.side_effect = ValueError("out of range")
        result = format_timestamp_readable(12345.0)
    assert result == "(unknown)"


# ---------------------------------------------------------------------------
# append_to_archive_and_mark_skipped — OSError branch (lines 129-130)
# ---------------------------------------------------------------------------


def test_append_to_archive_oserror_still_appends_message(tmp_path: Path) -> None:
    archive_file = tmp_path / "archive.txt"
    existing_ids: set[str] = set()
    messages: list[str] = []
    with patch("pathlib.Path.open", side_effect=OSError("permission denied")):
        append_to_archive_and_mark_skipped(
            str(archive_file),
            "vid123",
            existing_ids,
            "Test Video",
            messages,
        )
    assert len(messages) == 1
    assert "Test Video" in messages[0]


# ---------------------------------------------------------------------------
# _try_parse_datetime — all formats fail (line 196)
# ---------------------------------------------------------------------------


def test_try_parse_datetime_no_format_matches_returns_none() -> None:
    result = _try_parse_datetime("not-a-date", ("%Y-%m-%d",))
    assert result is None
