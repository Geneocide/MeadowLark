"""Unit tests for podcast_filtering helpers."""
# ruff: noqa: S101

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from src.podcast_filtering import (
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
